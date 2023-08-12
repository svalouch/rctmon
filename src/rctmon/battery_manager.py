
# Copyright 2021, Stefan Valouch (svalouch)
# SPDX-License-Identifier: GPL-3.0-only

'''
Battery Manager implementation. The battery manager acts as inventory system for battery modules in the devices stack.
Depending on the available batteries, it requests values from the device via the device manager.
'''

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Generator, Optional

from influxdb_client import Point, WritePrecision as InfluxWritePrecision
from prometheus_client.core import InfoMetricFamily, CounterMetricFamily, GaugeMetricFamily
from rctclient.registry import REGISTRY as R

from .influx import InfluxDB
from .models import BatteryInfo, BatteryReadings
from .utils import ensure_type


log = logging.getLogger(__name__)

# Maps OIDs to module numbers
BAT_IDS_MODULE_SN = {0xFBF6D834: 0, 0x99396810: 1, 0x73489528: 2, 0x257B7612: 3, 0x4E699086: 4, 0x162491E8: 5,
                     0x5939EC5D: 6}
BAT_IDS_CYCLES = {0xA6C4FD4A: 0, 0xCFA8BC4: 1, 0x5BA122A5: 2, 0x89B25F4B: 3, 0x5A9EEFF0: 4, 0x2A30A97E: 5,
                  0x27C39CEA: 6}


class BatteryManager:
    '''
    Management for batteries in a stack.
    '''
    #: Whether a BMS is present. If None, then no information is known (yet).
    have_battery: Optional[bool] = None

    # Number of battery modules, None if not yet known
    num_batteries: Optional[int] = None
    batteries: Dict[int, BatteryInfo]

    readings: BatteryReadings

    def __init__(self, parent) -> None:
        log.info('BatteryManager initializing')
        # DeviceManager
        self.parent = parent
        self.readings = BatteryReadings()
        self.batteries = dict()

    def collect(self) -> Generator:
        '''
        Prometheus custom collector.
        '''
        if self.readings.bms_sn is not None:
            yield InfoMetricFamily('rctmon_bms_info', 'Information about the battery management system (BMS)',
                                   {'inverter': self.parent.name, 'serial_number': self.readings.bms_sn})
        if self.readings.soc_min is not None:
            soc_min = GaugeMetricFamily('rctmon_battery_state_of_charge_min', 'Battery minimum state of charge',
                                        labels=['inverter'], unit='percent')
            soc_min.add_metric([self.parent.name], self.readings.soc_min)
            yield soc_min
        if self.readings.battery_voltage is not None:
            battery_voltage = GaugeMetricFamily('rctmon_battery_voltage', 'Battery Voltage', labels=['inverter'])
            battery_voltage.add_metric([self.parent.name], self.readings.battery_voltage)
            yield battery_voltage
        if self.readings.battery_power is not None:
            battery_power = GaugeMetricFamily('rctmon_battery_power', 'Battery Power', labels=['inverter'])
            battery_power.add_metric([self.parent.name], self.readings.battery_power)
            yield battery_power
        if self.readings.battery_state is not None:
            battery_state = GaugeMetricFamily('rctmon_battery_state', 'Battery state machine state',
                                              labels=['inverter'])
            battery_state.add_metric([self.parent.name], self.readings.battery_state)
            yield battery_state
        if self.readings.soc_target is not None:
            battery_soc_target = GaugeMetricFamily('rctmon_battery_state_of_charge_target',
                                                   'Battery target state of charge',
                                                   labels=['inverter'], unit='percent')
            battery_soc_target.add_metric([self.parent.name], self.readings.soc_target)
            yield battery_soc_target
        if self.readings.soc is not None:
            battery_soc = GaugeMetricFamily('rctmon_battery_state_of_charge',
                                                   'Battery state of charge',
                                                   labels=['inverter'], unit='percent')
            battery_soc.add_metric([self.parent.name], self.readings.soc)
            yield battery_soc
        if self.readings.soh is not None:
            battery_soh = GaugeMetricFamily('rctmon_battery_state_of_health', 'Battery state of health',
                                            labels=['inverter'], unit='percent')
            battery_soh.add_metric([self.parent.name], self.readings.soh)
            yield battery_soh
        if self.readings.temperature is not None:
            battery_temperature = GaugeMetricFamily('rctmon_battery_temperature', 'Battery temperature',
                                                    labels=['inverter'])
            battery_temperature.add_metric([self.parent.name], self.readings.temperature)
            yield battery_temperature
        if self.readings.bat_status is not None:
            battery_bat_status = GaugeMetricFamily('rctmon_battery_bat_status', 'Battery status', labels=['inverter'])
            battery_bat_status.add_metric([self.parent.name], self.readings.bat_status)
            yield battery_bat_status
        if self.readings.impedance_fine is not None:
            battery_impedance_fine = GaugeMetricFamily('rctmon_battery_impedance_fine', 'Battery impedance (fine)',
                                                       labels=['inverter'])
            battery_impedance_fine.add_metric([self.parent.name], self.readings.impedance_fine)
            yield battery_impedance_fine
        if self.readings.discharged_amp_hours is not None:
            battery_discharge_amp_hours = CounterMetricFamily('rctmon_battery_discharge', 'Battery cumulative '
                                                              'discharge', labels=['inverter'], unit='amp_hours')
            battery_discharge_amp_hours.add_metric([self.parent.name], self.readings.discharged_amp_hours)
            yield battery_discharge_amp_hours
        if self.readings.stored_energy is not None:
            battery_stored_energy = CounterMetricFamily('rctmon_battery_stored_energy', 'Battery cumulative stored '
                                                        'energy', labels=['inverter'])
            battery_stored_energy.add_metric([self.parent.name], self.readings.stored_energy)
            yield battery_stored_energy
        if self.readings.used_energy is not None:
            battery_used_energy = CounterMetricFamily('rctmon_battery_used_energy', 'Battery cumulative used '
                                                        'energy', labels=['inverter'])
            battery_used_energy.add_metric([self.parent.name], self.readings.used_energy)
            yield battery_used_energy

        if self.num_batteries and self.num_batteries > 0:
            cycles = CounterMetricFamily('rctmon_battery_module_cycles', 'Number of cycles the battery has accumulated'
                                         ' over its lifetime', labels=['inverter', 'module'])
            for battery in self.batteries.values():
                if battery:
                    yield InfoMetricFamily('rctmon_battery_module', 'Information about individual battery modules',
                                           {'inverter': self.parent.name, 'module': str(battery.num),
                                            'serial_number': battery.serial})

                    if battery.cycle_count is not None:
                        cycles.add_metric([self.parent.name, str(battery.num)], battery.cycle_count)
            yield cycles

    def collect_influx(self, influx: InfluxDB) -> None:
        '''
        Pushes the current data to influx.
        '''
        ts = datetime.now(timezone.utc)
        wpres = InfluxWritePrecision.S

        overview_fields: Dict[str, float] = dict()
        if self.readings.battery_voltage is not None:
            overview_fields['voltage'] = self.readings.battery_voltage
        if self.readings.battery_power is not None:
            overview_fields['power'] = self.readings.battery_power
        if self.readings.battery_state is not None:
            overview_fields['state'] = self.readings.battery_state
        if self.readings.soc_min is not None:
            overview_fields['soc_min'] = self.readings.soc_min
        if self.readings.soc_target is not None:
            overview_fields['soc_target'] = self.readings.soc_target
        if self.readings.soc is not None:
            overview_fields['soc'] = self.readings.soc
        if self.readings.soh is not None:
            overview_fields['soh'] = self.readings.soh
        if self.readings.temperature is not None:
            overview_fields['temperature'] = self.readings.temperature
        if self.readings.bat_status is not None:
            overview_fields['status'] = self.readings.bat_status
        if self.readings.impedance_fine is not None:
            overview_fields['impedance_fine'] = self.readings.impedance_fine
        if self.readings.discharged_amp_hours is not None:
            overview_fields['discharged_amp_hours'] = self.readings.discharged_amp_hours
        if self.readings.stored_energy is not None:
            overview_fields['stored_energy'] = self.readings.stored_energy
        if len(overview_fields) > 0:
            overview = Point('battery_overview').tag('inverter', self.parent.name).time(ts, write_precision=wpres)
            for ov_name, ov_value in overview_fields.items():
                overview = overview.field(ov_name, ov_value)
            influx.add_points(overview)

        if len(self.batteries) > 0:
            modules: Dict[int, Point] = dict()

            for battery in self.batteries.values():
                if battery:
                    if battery.cycle_count is not None and battery.num not in modules:  # add not none checks for all!
                        modules[battery.num] = Point('battery_module').tag('inverter', self.parent.name) \
                            .tag('module', battery.num)

                    if battery.cycle_count is not None:
                        modules[battery.num] = modules[battery.num].field('cycles', battery.cycle_count)

            influx.add_points(modules.values())

    def cb_battery_type(self, oid: int, value: Any) -> None:
        '''
        Handles 0x682CDDA1 power_mng.battery_type
        '''
        assert oid == 0x682CDDA1
        log.info('Got battery type: {%d}', value)
        # TODO check if type == 3 (RCTs own batteries?)
        if value > 0:
            self.have_battery = True
            # Collect which modules are present as well as the BMS S/N
            self.parent.add_ids('battery.bms_sn', interval=0, is_inventory=True, handler=self._cb_inventory)
            self.parent.add_ids(['battery.module_sn[0]', 'battery.module_sn[1]', 'battery.module_sn[2]',
                                 'battery.module_sn[3]', 'battery.module_sn[4]', 'battery.module_sn[5]',
                                 'battery.module_sn[6]'], interval=0, is_inventory=True,
                                handler=self._cb_battery_module_sn)
            # Settings, generally not changing or very seldomly
            self.parent.add_ids(['power_mng.soc_min', 'power_mng.soc_min_island', 'power_mng.soc_max',
                                 'battery.soh'], interval=300, handler=self._cb_readings)

            # Slow-changing values
            self.parent.add_ids(['battery.soc', 'battery.soc_target', 'adc.u_acc',
                                 'battery.temperature', 'acc_conv.i_acc_lp_fast', 'battery.bat_status',
                                 'battery.bat_impedance.impedance_fine', 'battery.discharged_amp_hours',
                                 'battery.stored_energy', 'battery.used_energy', 'battery.efficiency',
                                 'battery.cycles'], interval=60, handler=self._cb_readings)
            # Fast-changing values
            self.parent.add_ids(['g_sync.p_acc_lp', 'battery.voltage', 'adc.u_acc', 'power_mng.u_acc_mix_lp',
                                 'power_mng.battery_power', 'battery.current', 'battery.status', 'battery.status2',
                                 'power_mng.state'], interval=10, handler=self._cb_readings)
        else:
            self.have_battery = False

    def _cb_inventory(self, oid: int, value: Any) -> None:
        '''
        Callback for inventory stuff.
        '''
        # battery.bms_sn
        if oid == 0x16A1F844:
            self.readings.bms_sn = ensure_type(value, str)

    def _cb_battery_module_sn(self, oid: int, value: Any) -> None:
        '''
        Handles 0x682CDDA1 battery.module_sn[X]

        The code assumes that there won't ever be double-digit battery stacks!
        '''
        try:
            bat_id = BAT_IDS_MODULE_SN[oid]
        except KeyError:
            log.error('battery.module_sn: Got unknown OID 0x%X', oid)
        else:
            if value == '':
                log.info('BatteryManager: Received empty S/N for battery module %d, module not present', bat_id)
            else:

                # We know that we have some batteries now

                if bat_id in self.batteries.keys():
                    log.warning('Attempt to add existing battery #%d ignored', bat_id)
                else:
                    log.info('BatteryManager: Received S/N for battery module %d: %s', bat_id, value)

                self.batteries[bat_id] = BatteryInfo(bat_id, value)
                # request the modules cycle count from now on
                self.parent.add_ids([f'battery.stack_cycles[{bat_id}]'], interval=300, handler=self._cb_battery_cycles)

    def _cb_battery_cycles(self, oid: int, value: Any) -> None:
        '''
        Handler for ``battery.stack_cycles[X]``.
        '''
        try:
            bat_id = BAT_IDS_CYCLES[oid]
        except KeyError:
            log.error('battery.stack_cycles: Got unknown OID 0x%X', oid)
        else:
            try:
                self.batteries[bat_id].cycle_count = ensure_type(value, int)
            except KeyError:
                log.warning('BatteryManager: Attempt to set cycle count for unknown battery #%d', bat_id)
            except TypeError:
                log.warning('Got wrong type %s for %s', type(value), R.get_by_id(oid).name)

    def _cb_readings(self, oid: int, value: Any) -> None:
        try:
            # battery.soh
            if oid == 0x381B8BF9:
                self.readings.soh = ensure_type(value, float)
            # battery.soc
            elif oid == 0x959930BF:
                self.readings.soc = ensure_type(value, float)
            # battery.soc_target
            elif oid == 0x8B9FF008:
                self.readings.soc_target = ensure_type(value, float)
            # battery.temperature
            elif oid == 0x902AFAFB:
                self.readings.temperature = ensure_type(value, float)
            # battery.bat_status
            elif oid == 0x70A2AF4F:
                self.readings.bat_status = ensure_type(value, int)
            # battery.status
            elif oid == 0x71765BD8:
                self.readings.status = ensure_type(value, int)
            # battery.status2
            elif oid == 0xDE3D20D:
                self.readings.status2 = ensure_type(value, int)
            # battery.bat_impedance.impedance_fine
            elif oid == 0xE7B0E692:
                self.readings.impedance_fine = ensure_type(value, float)
            # battery.discharged_amp_hours
            elif oid == 0x2BC1E72B:
                self.readings.discharged_amp_hours = ensure_type(value, float)
            # battery.stored_energy
            elif oid == 0x5570401B:
                self.readings.stored_energy = ensure_type(value, float)
            # battery.used_energy
            elif oid == 0xA9033880:
                self.readings.used_energy = ensure_type(value, float)
            # battery.efficiency
            elif oid == 0xACF7666B:
                self.readings.efficiency = ensure_type(value, float)
            # battery.voltage
            elif oid == 0x65EED11B:
                self.readings.voltage = ensure_type(value, float)
            # battery.current
            elif oid == 0x21961B58:
                self.readings.current = ensure_type(value, float)
            # power_mng.soc_min
            elif oid == 0xCE266F0F:
                self.readings.soc_min = ensure_type(value, float)
            # power_mng.power_mng.u_acc_mix_lp
            elif oid == 0xA7FA5C5D:
                self.readings.battery_voltage = ensure_type(value, float)
            # power_mng.battery_power
            elif oid == 0x400F015B:
                self.readings.battery_power = ensure_type(value, float)
            # power_mng.state
            elif oid == 0xDC667958:
                self.readings.battery_state = ensure_type(value, int)
            # battery.cycles
            elif oid == 0xC0DF2978:
                self.readings.cycles = ensure_type(value, int)
            else:
                log.warning('_cb_readings: unhandled oid 0x%X', oid)
        except TypeError:
            log.warning('Got wrong type %s for %s', type(value), R.get_by_id(oid).name)
