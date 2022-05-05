
# Copyright 2021, Stefan Valouch (svalouch)
# SPDX-License-Identifier: GPL-3.0-only

'''
Device Manager implementation. The device manager collects inventory data from the device and decides which values to
request based on the gathered information.
'''

import logging
import struct

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Generator, Iterable, List, Optional, Union

from influxdb_client import Point, WritePrecision as InfluxWritePrecision
from prometheus_client.core import InfoMetricFamily, CounterMetricFamily, GaugeMetricFamily, REGISTRY as P_R
from rctclient.frame import ReceiveFrame
from rctclient.utils import decode_value
from rctclient.registry import REGISTRY as R

from .battery_manager import BatteryManager
from .influx import InfluxDB
from .managed_frame import ManagedFrame
from .models import Readings
from .monitoring import MON_DECODE_ERROR, MON_FRAMES_SENT, MON_FRAMES_LOST
from .utils import ensure_type, OidHandler


log = logging.getLogger(__name__)


class DeviceManager:
    #: Container for managed frames
    _frames: Dict[int, ManagedFrame]

    readings: Readings
    # inverter

    name: Optional[str]  # android_description
    have_name: bool = False

    battery_manager: BatteryManager

    # IDs that are added when the inventory was built, used to clear the dynamic ones
    _inventory_ids: List[int]

    _influx: InfluxDB

    def __init__(self, influx: InfluxDB) -> None:
        log.info('DeviceManager initializing')
        self._frames = dict()
        self._inventory_ids = list()
        self._influx = influx
        self.name = None
        self._callbacks: Dict[int, OidHandler] = dict()

        self.readings = Readings()

        # get the name at first, it is used everywhere to identify it
        self.add_ids('android_description', interval=0, inventory=False, is_inventory=True,
                     handler=self._cb_android_description)

        self.battery_manager = BatteryManager(parent=self)

        P_R.register(self)
        P_R.register(self.battery_manager)

    def add_callback(self, oid: int, handler: OidHandler) -> None:
        '''
        Add a callback to be called when a frame with a matchin OID is received. Only one callback can be set for an
        OID, adding another will overwrite the first one after printing a warning.

        :param oid: OID to add a callback for.
        :param handler: Function to call.
        '''
        if oid in self._callbacks:
            log.warning('Overwriting callback for 0x%X')
        log.debug('Adding callback for 0x%X to %s.%s', oid, handler.__class__.__name__, handler.__name__)
        self._callbacks[oid] = handler

    def collect(self) -> Generator:
        '''
        Custom collector for prometheus, called by the prometheus client uppon scrape request.
        '''
        # frames_in_flight = GaugeMetricFamily('rctmon_frames_in_flight', 'Amount of frames sent but not yet received',
        #                                      labels=['kind'])
        # frames_in_flight.add_metric(['normal'], len([oid for oid, frame in self._frames.items()
        #                                              if frame.in_flight and frame.is_inventory is False]))
        # frames_in_flight.add_metric(['inventory'], len([oid for oid, frame in self._frames.items()
        #                                                 if frame.in_flight and frame.is_inventory is True]))
        # yield frames_in_flight

        # The following need the name of the inverter set
        if not self.name:
            return

        inventory = GaugeMetricFamily('rctmon_inventory', 'Shows attached components',
                                      labels=['inverter', 'component'])
        if self.readings.have_generator_a is not None:
            inventory.add_metric([self.name, 'generator_a'], int(self.readings.have_generator_a))
        if self.readings.have_generator_b is not None:
            inventory.add_metric([self.name, 'generator_b'], int(self.readings.have_generator_b))
        if self.readings.power_switch_available is not None:
            inventory.add_metric([self.name, 'power_switch'], int(self.readings.power_switch_available))
        yield inventory

        yield from self.readings.collect(self.name)
        yield from self.battery_manager.collect()

    def collect_influx(self, influx: InfluxDB) -> None:
        '''
        Pushes data to InfluxDB.
        '''
        if not self.name:
            return

        self.battery_manager.collect_influx(influx)

        ts = datetime.now(timezone.utc)

        temp_point = Point('temperature').tag('inverter', self.name).time(ts, write_precision=InfluxWritePrecision.S)
        have_temp = False
        if self.readings.temperature_heatsink is not None:
            have_temp = True
            temp_point = temp_point.field('heatsink', self.readings.temperature_heatsink)
        if self.readings.temperature_heatsink_batt is not None:
            have_temp = True
            temp_point = temp_point.field('heatsink_battery_actuator', self.readings.temperature_heatsink_batt)
        if self.readings.temperature_core is not None:
            have_temp = True
            temp_point = temp_point.field('core', self.readings.temperature_core)
        if self.battery_manager.readings.temperature is not None:
            have_temp = True
            temp_point = temp_point.field('battery', self.battery_manager.readings.temperature)
        if have_temp:
            influx.add_points(temp_point)

    def _influx_raw(self, oid: int, value: Union[bool, str, float, int]) -> None:
        '''
        Dispatches raw data to InfluxDB.

        Assumes that the devices name has been retrieved.
        '''
        if isinstance(value, float):
            type_field = 'value_float'
        elif isinstance(value, bool):
            type_field = 'value_bool'
        elif isinstance(value, str):
            type_field = 'value_string'
        elif isinstance(value, int):
            type_field = 'value_int'
        else:
            # values like time series or event data
            log.debug('influx_raw: type %s can\'t be saved, ignoring oid 0x%X', type(value), oid)
            return
        try:
            name = R.get_by_id(oid).name
        except KeyError:
            log.warning('influx_raw: registry does not know OID 0x%X', oid)
        else:
            self._influx.add_points(
                Point('raw_data').tag('inverter', self.name).tag('oid', f'0x{oid:X}').tag('name', name)
                .time(datetime.now(timezone.utc), write_precision=InfluxWritePrecision.S)
                .field(type_field, value)
            )

    def payloads(self) -> bytes:
        '''
        Returns the payloads of the frames that should be queried now.
        '''
        data = b''
        staging: List[ManagedFrame] = list()
        now = datetime.utcnow()
        # for _, mframe in {k: v for k, v in sorted(self._frames.items(), key=lambda item: item[1])}.items():
        for _, mframe in sorted(self._frames.items(), key=lambda item: item[1]):
            if not mframe.is_inventory:
                # reset the in_flight property if the frame is in_flight (since last_transmit) for three times its
                # interval (arbitrary value)
                if mframe.in_flight and mframe.last_transmit <= now - timedelta(seconds=3 * mframe.interval):
                    log.debug('Frame 0x%X %s is in flight for too long, resetting', mframe.oinfo.object_id,
                              mframe.oinfo.name)
                    MON_FRAMES_LOST.labels('normal').inc()
                    mframe.in_flight = False

                if mframe.last_transmit <= now - timedelta(seconds=mframe.interval) and not mframe.in_flight:
                    log.debug('Adding %s', mframe)
                    staging.append(mframe)

            else:
                # skip frames that have had an arrival and are inventory frames
                if mframe.last_arrival > datetime.min:
                    continue
                # inventory frames are re-sent some time after they have been sent originally
                if mframe.last_arrival == datetime.min and mframe.last_transmit < now - timedelta(seconds=30):
                    if not mframe.in_flight:
                        log.debug('Adding inventory frame %s', mframe)
                    else:
                        MON_FRAMES_LOST.labels('inventory').inc()
                        log.debug('Inventory frame %s overdue, resending', mframe)
                    staging.append(mframe)

        for st_frame in staging:
            st_frame.last_transmit = now
            data += st_frame.payload
        MON_FRAMES_SENT.inc(len(staging))

        return data

    def mark_arrival(self, oid: int) -> None:
        '''
        Marks the arrival of a frame.
        '''
        try:
            log.debug('Marking frame 0x%X as arrived', oid)
            self._frames[oid].last_arrival = datetime.utcnow()
            self._frames[oid].in_flight = False
        except KeyError:
            log.warning('Got unexpected frame 0x%X in mark_arrival', oid)

    def on_frame(self, frame: ReceiveFrame) -> None:
        '''
        Handles decoding of frame content and dispatches the frame to registered callbacks.
        '''

        log.debug('got frame %s', repr(frame))
        if frame.id not in self._frames:
            log.warning('Index 0x%x not in frames list', frame.id)
        else:
            try:
                value: Any = decode_value(self._frames[frame.id].oinfo.response_data_type, frame.data)
            except struct.error as exc:
                MON_DECODE_ERROR.labels('payload').inc()
                log.warning('Got unpack error in frame 0x%x %s: %s', frame.id, self._frames[frame.id].oinfo.name,
                            str(exc))
            else:
                self.mark_arrival(frame.id)
                log.debug('frame arrived: %s = %s', self._frames[frame.id].oinfo.name, str(value))

                if self.have_name:
                    self._influx_raw(frame.id, value)

                # dispatch reading to to the callback registered for it
                try:
                    self._callbacks[frame.id](frame.id, value)
                except KeyError:
                    log.warning('Unhandled frame %s', R.get_by_id(frame.id).name)

    def _cb_power_switch(self, oid: int, value: Union[str, float, bool]) -> None:
        '''
        Callback for power switch, both inventory and metrics.
        '''
        try:
            # rb485.u_l_grid[0]
            if oid == 0x93F976AB:
                self.readings.power_switch_readings.grid_voltage_l1 = ensure_type(value, float)
            # rb485.u_l_grid[1]
            elif oid == 0x7A9091EA:
                self.readings.power_switch_readings.grid_voltage_l2 = ensure_type(value, float)
            # rb485.u_l_grid[3]
            elif oid == 0x21EE7CBB:
                self.readings.power_switch_readings.grid_voltage_l3 = ensure_type(value, float)
            # rb485.f_grid[0]
            elif oid == 0x9558AD8A:
                self.readings.power_switch_readings.grid_frequency_l1 = ensure_type(value, float)
            # rb485.f_grid[1]
            elif oid == 0xFAE429C5:
                self.readings.power_switch_readings.grid_frequency_l2 = ensure_type(value, float)
            # rb485.f_grid[2]
            elif oid == 0x104EB6A:
                self.readings.power_switch_readings.grid_frequency_l3 = ensure_type(value, float)
            # rb485.f_wr[0]
            elif oid == 0x3B5F6B9D:
                self.readings.power_switch_readings.power_storage_frequency_l1 = ensure_type(value, float)
            # rb485.f_wr[1]
            elif oid == 0x6FD36B32:
                self.readings.power_switch_readings.power_storage_frequency_l2 = ensure_type(value, float)
            # rb485.f_wr[2]
            elif oid == 0x905F707B:
                self.readings.power_switch_readings.power_storage_frequency_l3 = ensure_type(value, float)
            else:
                log.warning('_cb_power_switch: unhandled oid 0x%X', oid)
        except TypeError:
            # oid is known at this point, as the else above catches unknowns without raising
            log.warning('Got wrong type %s for %s', type(value), R.get_by_id(oid).name)

    def _cb_inventory(self, oid: int, value: Any) -> None:
        '''
        Handler for inventory data.
        '''
        try:
            # rb485.available
            if oid == 0x437B8122:
                self.readings.power_switch_available = ensure_type(value, bool) is True
                if self.readings.power_switch_available:
                    self.add_ids(['rb485.version_main', 'rb485.version_boot'], interval=0, is_inventory=True,
                                 handler=self._cb_inventory)
                    self.add_ids(['rb485.u_l_grid[0]', 'rb485.u_l_grid[1]', 'rb485.u_l_grid[2]', 'rb485.f_grid[0]',
                                  'rb485.f_grid[1]', 'rb485.f_grid[2]', 'rb485.f_wr[0]', 'rb485.f_wr[1]',
                                  'rb485.f_wr[2]'], interval=10, handler=self._cb_power_switch)
            # inverter_sn
            elif oid == 0x7924ABD9:
                self.readings.serial_number = ensure_type(value, str)
            # svnversion
            elif oid == 0xDDD1C2D0:
                self.readings.control_software_version = ensure_type(value, str)
            # parameter_file
            elif oid == 0x68BC034D:
                self.readings.parameter_file = ensure_type(value, str)
            # rb485.version_main
            elif oid == 0x27650FE2:
                self.readings.power_switch_readings.software_version = ensure_type(value, int)
            # rb485.version_boot
            elif oid == 0x173D81E4:
                self.readings.power_switch_readings.bootloader_version = ensure_type(value, int)
            # check for solar generator A
            elif oid == 0x701A0482:
                self.readings.have_generator_a = ensure_type(value, bool) is True
                if value is True:
                    # insert IDs for the generator
                    self.add_ids(['g_sync.u_sg_avg[0]', 'dc_conv.dc_conv_struct[0].p_dc_lp'], interval=10,
                                 handler=self._cb_solar_generator)
                    self.add_ids(['dc_conv.dc_conv_struct[0].u_target', 'dc_conv.dc_conv_struct[0].mpp.mpp_step'],
                                 interval=120, handler=self._cb_solar_generator)
                    self.add_ids(['energy.e_dc_total[0]'], interval=300, handler=self._cb_energy)
            # check for solar generator B
            elif oid == 0xFED51BD2:
                self.readings.have_generator_b = ensure_type(value, bool) is True
                if value is True:
                    self.add_ids(['g_sync.u_sg_avg[1]', 'dc_conv.dc_conv_struct[1].p_dc_lp'], interval=10,
                                 handler=self._cb_solar_generator)
                    self.add_ids(['dc_conv.dc_conv_struct[1].u_target', 'dc_conv.dc_conv_struct[1].mpp.mpp_step'],
                                 interval=120, handler=self._cb_solar_generator)
                    self.add_ids(['energy.e_dc_total[1]'], interval=300, handler=self._cb_energy)
            else:
                log.warning('_cb_inventory: unhandled oid 0x%X', oid)
        except TypeError:
            log.warning('Got wrong type %s for %s', type(value), R.get_by_id(oid).name)

    def _cb_android_description(self, oid: int, value: str) -> None:
        '''
        Called when the name of the device is received. It kicks the rest of the system into motion.
        '''
        if self.have_name:
            log.warning('Got android_description besides it being already stored')
            if self.name != value:
                log.warning('android_description "%s" differs from stored "%s"', value, self.name)
                self.set_name(value)
        else:
            self.set_name(value)
            # the name is set, now complete the inventory and request IDs that are always there

            self.add_ids(['inverter_sn', 'svnversion', 'parameter_file',
                          'dc_conv.dc_conv_struct[0].enabled', 'dc_conv.dc_conv_struct[1].enabled',
                          'rb485.available'], interval=0, inventory=False, is_inventory=True,
                         handler=self._cb_inventory)
            self.add_ids(['power_mng.battery_type'], interval=0, inventory=False, is_inventory=True,
                         handler=self.battery_manager.cb_battery_type)

            self.add_ids(['g_sync.p_ac_load_sum_lp', 'g_sync.p_ac_load[0]', 'g_sync.p_ac_load[1]',
                          'g_sync.p_ac_load[2]'], interval=10, inventory=False, handler=self._cb_household)
            self.add_ids(['g_sync.p_ac_grid_sum_lp', 'g_sync.p_ac_sc[0]', 'g_sync.p_ac_sc[1]', 'g_sync.p_ac_sc[2]',
                          'g_sync.u_l_rms[0]', 'g_sync.u_l_rms[1]', 'g_sync.u_l_rms[2]', 'g_sync.u_ptp_rms[0]',
                          'g_sync.u_ptp_rms[1]', 'g_sync.u_ptp_rms[2]', 'grid_pll[0].f'], interval=10,
                         inventory=False, handler=self._cb_grid)

            self.add_ids(['db.temp1', 'db.temp2', 'db.core_temp'], interval=60, inventory=False, handler=self._cb_sensors)
            self.add_ids(['prim_sm.state', 'prim_sm.island_flag', 'fault[0].flt', 'fault[1].flt', 'fault[2].flt',
                          'fault[3].flt', 'iso_struct.Riso', 'iso_struct.Rp', 'iso_struct.Rn'],
                          interval=10, inventory=False, handler=self._cb_inverter)
            self.add_ids(['energy.e_ac_day', 'energy.e_ac_month', 'energy.e_ac_year', 'energy.e_ac_total',
                          'energy.e_grid_feed_total', 'energy.e_grid_load_total','energy.e_load_total'],
                         interval=300, inventory=False, handler=self._cb_energy)

    def _cb_inverter(self, oid: int, value: Any) -> None:
        try:
            # prim_sm.state
            if oid == 0x5F33284E:
                self.readings.inverter_status = ensure_type(value, int)
            # prim_sm.island_flag
            elif oid == 0x3623D82A:
                self.readings.inverter_grid_separated = ensure_type(value, int)
            # fault[0].flt
            elif oid == 0x37F9D5CA:
                self.readings.fault0 = ensure_type(value, int)
            # fault[1].flt
            elif oid == 0x234B4736:
                self.readings.fault1 = ensure_type(value, int)
            # fault[2].flt
            elif oid == 0x3B7FCD47:
                self.readings.fault2 = ensure_type(value, int)
            # fault[3].flt
            elif oid == 0x7F813D73:
                self.readings.fault3 = ensure_type(value, int)
            # iso_struct.Riso
            elif oid == 0xC717D1FB:
                self.readings.inverter_insulation_total = ensure_type(value, float)
            # iso_struct.Rp
            elif oid == 0x8E41FC47:
                self.readings.inverter_insulation_positive = ensure_type(value, float)
            # iso_struct.Rn
            elif oid == 0x474F80D5:
                self.readings.inverter_insulation_negative = ensure_type(value, float)
            else:
                log.warning('_cb_inverter: unhandled oid 0x%X', oid)
        except TypeError:
            log.warning('Got wrong type %s for %s', type(value), R.get_by_id(oid).name)

    def _cb_household(self, oid: int, value: Any) -> None:
        try:
            # g_sync.p_ac_load_sum_lp
            if oid == 0x1AC87AA0:
                self.readings.household.load_total = ensure_type(value, float)
            # g_sync.p_ac_load[0]
            elif oid == 0x3A39CA2:
                self.readings.household.load_l1 = ensure_type(value, float)
            # g_sync.p_ac_load[1]
            elif oid == 0x2788928C:
                self.readings.household.load_l2 = ensure_type(value, float)
            # g_sync.p_ac_load[2]
            elif oid == 0xF0B436DD:
                self.readings.household.load_l3 = ensure_type(value, float)
            else:
                log.warning('_cb_household: unhandled oid 0x%X', oid)
        except TypeError:
            log.warning('Got wrong type %s for %s', type(value), R.get_by_id(oid).name)

    def _cb_grid(self, oid: int, value: Any) -> None:
        try:
            # g_sync.p_ac_grid_sum_lp
            if oid == 0x91617C58:
                self.readings.grid.power_total = ensure_type(value, float)
            # g_sync.p_ac_sc[0]
            elif oid == 0x27BE51D9:
                self.readings.grid.power_l1 = ensure_type(value, float)
            # g_sync.p_ac_sc[2]
            elif oid == 0xF5584F90:
                self.readings.grid.power_l2 = ensure_type(value, float)
            # g_sync.p_ac_sc[2]
            elif oid == 0xB221BCFA:
                self.readings.grid.power_l3 = ensure_type(value, float)
            # g_sync.u_l_rms[0]
            elif oid == 0xCF053085:
                self.readings.grid.voltage_l1 = ensure_type(value, float)
            # g_sync.u_l_rms[1]
            elif oid == 0x54B4684E:
                self.readings.grid.voltage_l2 = ensure_type(value, float)
            # g_sync.u_l_rms[2]
            elif oid == 0x2545E22D:
                self.readings.grid.voltage_l3 = ensure_type(value, float)
            else:
                log.warning('_cb_grid: unhandled oid 0x%X', oid)
        except TypeError:
            log.warning('Got wrong type %s for %s', type(value), R.get_by_id(oid).name)

    def _cb_solar_generator(self, oid: int, value: Union[float, bool]) -> None:
        '''
        Callback for storing solar generator information.
        '''
        try:
            # g_sync.u_sg_avg[0]
            if oid == 0xB55BA2CE:
                self.readings.solar_generator_a.voltage = ensure_type(value, float)
            # dc_conv.dc_conv_struct[0].p_dc_lp
            elif oid == 0xDB11855B:
                self.readings.solar_generator_a.power = ensure_type(value, float)
            # dc_conv.dc_conv_struct[0].u_target
            elif oid == 0x226A23A4:
                self.readings.solar_generator_a.mpp_target_voltage = ensure_type(value, float)
            # dc_conv.dc_conv_struct[0].mpp.mpp_step
            elif oid == 0xBA8B8515:
                self.readings.solar_generator_a.mpp_search_step = ensure_type(value, float)
            # g_sync.u_sg_avg[1]
            elif oid == 0xB0041187:
                self.readings.solar_generator_b.voltage = ensure_type(value, float)
            # dc_conv.dc_conv_struct[1].p_dc_lp
            elif oid == 0xCB5D21B:
                self.readings.solar_generator_b.power = ensure_type(value, float)
            # dc_conv.dc_conv_struct[1].u_target
            elif oid == 0x675776B1:
                self.readings.solar_generator_b.mpp_target_voltage = ensure_type(value, float)
            # dc_conv.dc_conv_struct[1].mpp.mpp_step
            elif oid == 0x4AE96C12:
                self.readings.solar_generator_b.mpp_search_step = ensure_type(value, float)
        except TypeError:
            log.warning('Got wrong type %s for %s', type(value), R.get_by_id(oid).name)

    def _cb_sensors(self, oid: int, value: Union[float, bool]) -> None:
        '''
        Callback for storing sensors information.
        '''
        try:
            # db.temp1
            if oid == 0xF79D41D9:
                self.readings.temperature_heatsink = ensure_type(value, float)
            # db.temp2
            elif oid == 0x4F735D10:
                self.readings.temperature_heatsink_batt = ensure_type(value, float)
            # db.core_temp
            elif oid == 0xC24E85D0:
                self.readings.temperature_core = ensure_type(value, float)
        except TypeError:
            log.warning('Got wrong type %s for %s', type(value), R.get_by_id(oid).name)

    def _cb_energy(self, oid: int, value: Union[float, bool]) -> None:
        '''
        Callback for storing energy information.
        '''
        try:
            # energy.e_ac_total
            if oid == 0xB1EF67CE:
                self.readings.energy.ac_sum = ensure_type(value, float)
            # energy.e_load_total
            elif oid == 0xEFF4B537:
                self.readings.energy.household_sum = ensure_type(value, float)
            # energy.e_grid_feed_total
            elif oid == 0x44D4C533:
                self.readings.energy.grid_feed_sum = ensure_type(value, float)
            # energy.e_grid_load_total
            elif oid == 0x62FBE7DC:
                self.readings.energy.grid_load_sum = ensure_type(value, float)
            # energy.e_dc_total[0]
            elif oid == 0xFC724A9E:
                self.readings.energy.solar_generator_a_sum = ensure_type(value, float)
            # energy.e_dc_total[1]
            elif oid == 0x68EEFD3D:
                self.readings.energy.solar_generator_b_sum = ensure_type(value, float)
            else:
                log.warning('_cb_energy: unhandled oid 0x%X', oid)
        except TypeError:
            log.warning('Got wrong type %s for %s', type(value), R.get_by_id(oid).name)


    def set_name(self, name: str) -> None:
        '''
        Sets the inverter name. Leading and trailing whitespace is stripped, if the name is empty it is replaced by
        ``UNKNOWN``.
        '''
        n_name = name.strip()
        if n_name == '':
            self.name = 'UNKNOWN'
        else:
            self.name = n_name
        self.have_name = True

    def add_ids(self, ids: Union[str, List[str]], interval: int = 60, inventory: bool = True,
                is_inventory: bool = False, handler: OidHandler = None) -> None:
        '''
        Adds managed frames to the list.

        :param ids: List of names or an individual name.
        :param interval: Interval at which the OID should be checked.
        :param inventory: Whether the OID is considered to be for building the inventory.
        :param cb_fun: Optional callback, if set it is registered to be called when the OID is received.
        '''
        if isinstance(ids, List):
            for oid in ids:
                self.add_ids(oid, interval, inventory, is_inventory, handler)
        else:
            try:
                tmp_oinfo = R.get_by_name(ids)
            except KeyError:
                log.error('Failed to add OID %s: Not found in registry', ids)
            else:
                self._frames[tmp_oinfo.object_id] = ManagedFrame(oinfo=tmp_oinfo, interval=interval,
                                                                 is_inventory=is_inventory)
                if inventory:
                    self._inventory_ids.append(tmp_oinfo.object_id)

                if handler is not None:
                    self.add_callback(tmp_oinfo.object_id, handler)

    def clear_inventory(self) -> None:
        '''
        Clears inventory information and removes IDs that were added to the list by the inventory system.
        '''
        for i_id in self._inventory_ids:
            del self._frames[i_id]
        self.battery_manager.clear_inventory()
        self.readings.have_generator_a = None
        self.readings.have_generator_b = None
        self.readings.power_switch_available = None

        self.name = ''
        self.readings.serial_number = ''
        self.readings.parameter_file = ''
        self.readings.control_software_version = ''
        self.readings.power_switch_software_version = ''
        self.readings.power_switch_bootloader_version = ''
