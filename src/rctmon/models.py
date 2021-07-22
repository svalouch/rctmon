
# Copyright 2021, Stefan Valouch (svalouch)
# SPDX-License-Identifier: GPL-3.0-only

'''
Models and dataclasses.
'''

# pylint: disable=too-many-instance-attributes

from dataclasses import dataclass
from typing import Generator, Optional

from prometheus_client.core import GaugeMetricFamily, InfoMetricFamily


class BatteryInfo:
    '''
    Information about a single battery in the stack.
    '''
    #: Number in the stack
    num: int
    serial: str
    cycle_count: Optional[int] = None

    def __init__(self, num: int, serial: str) -> None:
        self.num = num
        self.serial = serial

    def __repr__(self) -> str:
        return f'<BatteryInfo({self.num}, "{self.serial}")>'

    def is_complete(self) -> bool:
        '''
        Returns whether the information is complete.
        '''
        return self.cycle_count is not None


@dataclass
class BatteryReadings:
    '''
    Container for battery readings that are not specific to a stack member.
    '''
    #: battery.bms_sn
    bms_sn: Optional[str] = None
    #: power_mng.soc_min
    soc_min: Optional[float] = None
    #: power_mng.power_mng.u_acc_mix_lp
    battery_voltage: Optional[float] = None
    #: power_mng.battery_power
    battery_power: Optional[float] = None
    #: power_mng.state
    battery_state: Optional[int] = None
    #: battery.soc
    soc: Optional[float] = None
    #: battery.soh
    soh: Optional[float] = None
    #: battery.soc_target
    soc_target: Optional[float] = None
    #: battery.temperature
    temperature: Optional[float] = None
    #: battery.bat_status
    bat_status: Optional[int] = None
    #: battery.bat_impedance.impedance_fine
    impedance_fine: Optional[float] = None
    #: battery.discharged_amp_hours
    discharged_amp_hours: Optional[float] = None
    #: battery.stored_energy
    stored_energy: Optional[float] = None
    #: battery.used_energy
    used_energy: Optional[float] = None
    #: battery.efficiency
    efficiency: Optional[float] = None
    #: battery.voltage
    voltage: Optional[float] = None
    #: battery.current
    current: Optional[float] = None
    #: battery.cycles
    cycles: Optional[int] = None
    #: battery.status
    status: Optional[int] = None
    #: battery.status2
    status2: Optional[int] = None


@dataclass
class SolarGeneratorReadings:
    '''
    Container for readings from a single solar generator.
    '''
    # g_sync.u_sg_avg[0]
    voltage: Optional[float] = None
    # dc_conv.dc_conv_struct[0].p_dc_lp
    power: Optional[float] = None
    # dc_conv.dc_conv_struct[0].u_target
    mpp_target_voltage: Optional[float] = None
    # dc_conv.dc_conv_struct[0].mpp.mpp_step
    mpp_search_step: Optional[float] = None


@dataclass
class PowerSwitchReadings:
    '''
    Container for readings from the power switch / power sensor.
    '''
    #: rb485.version_main
    software_version: Optional[int] = None
    #: rb485.version_boot
    bootloader_version: Optional[int] = None

    #: rb485.u_l_grid[0]
    grid_voltage_l1: Optional[float] = None
    #: rb485.u_l_grid[1]
    grid_voltage_l2: Optional[float] = None
    #: rb485.u_l_grid[2]
    grid_voltage_l3: Optional[float] = None
    #: rb485.f_grid[0]
    grid_frequency_l1: Optional[float] = None
    #: rb485.f_grid[1]
    grid_frequency_l2: Optional[float] = None
    #: rb485.f_grid[1]
    grid_frequency_l3: Optional[float] = None
    #: rb485.f_wr[0]
    power_storage_frequency_l1: Optional[float] = None
    #: rb485.f_wr[1]
    power_storage_frequency_l2: Optional[float] = None
    #: rb485.f_wr[2]
    power_storage_frequency_l3: Optional[float] = None

    def collect(self, name: str) -> Generator:
        '''
        Yields metrics for the grid
        '''
        if self.software_version is not None and self.bootloader_version is not None:
            yield InfoMetricFamily('rctmon_powerswitch', 'Information about the Power Switch',
                                   {'inverter': name, 'software_version': str(self.software_version),
                                    'bootloader_version': str(self.bootloader_version)})

        grid_voltage = GaugeMetricFamily('rctmon_grid_voltage', 'Grid voltage by phase', labels=['inverter', 'phase'],
                                         unit='volt')
        if self.grid_voltage_l1 is not None:
            grid_voltage.add_metric([name, 'l1'], self.grid_voltage_l1)
        if self.grid_voltage_l2 is not None:
            grid_voltage.add_metric([name, 'l2'], self.grid_voltage_l2)
        if self.grid_voltage_l3 is not None:
            grid_voltage.add_metric([name, 'l3'], self.grid_voltage_l3)
        yield grid_voltage

        grid_frequency = GaugeMetricFamily('rctmon_grid_frequency', 'Grid frequency by phase',
                                           labels=['inverter', 'phase'], unit='hertz')
        if self.grid_frequency_l1 is not None:
            grid_frequency.add_metric([name, 'l1'], self.grid_frequency_l1)
        if self.grid_frequency_l2 is not None:
            grid_frequency.add_metric([name, 'l2'], self.grid_frequency_l2)
        if self.grid_frequency_l3 is not None:
            grid_frequency.add_metric([name, 'l3'], self.grid_frequency_l3)
        yield grid_frequency

        ps_frequency = GaugeMetricFamily('rctmon_powerstorage_frequency', 'Power Storage frequency by phase',
                                         labels=['inverter', 'phase'], unit='hertz')
        if self.power_storage_frequency_l1 is not None:
            ps_frequency.add_metric([name, 'l1'], self.power_storage_frequency_l1)
        if self.power_storage_frequency_l2 is not None:
            ps_frequency.add_metric([name, 'l2'], self.power_storage_frequency_l2)
        if self.power_storage_frequency_l3 is not None:
            ps_frequency.add_metric([name, 'l3'], self.power_storage_frequency_l3)
        yield ps_frequency


@dataclass
class HouseholdReadings:
    #: g_sync.p_ac_load_sum_lp
    load_total: Optional[float] = None
    #: g_sync.p_ac_load[0]
    load_l1: Optional[float] = None
    #: g_sync.p_ac_load[1]
    load_l2: Optional[float] = None
    #: g_sync.p_ac_load[2]
    load_l3: Optional[float] = None

    def collect(self, name: str) -> Generator:
        if self.load_total is not None:
            load_t = GaugeMetricFamily('rctmon_household_load', 'Household load (sum over phases)',
                                       labels=['inverter'])
            load_t.add_metric([name], self.load_total)
            yield load_t
        if self.load_l1 is not None or self.load_l2 is not None or self.load_l3 is not None:
            load = GaugeMetricFamily('rctmon_household_load_phase', 'Household load by phase',
                                     labels=['inverter', 'phase'])
            if self.load_l1 is not None:
                load.add_metric([name, 'l1'], self.load_l1)
            if self.load_l2 is not None:
                load.add_metric([name, 'l2'], self.load_l2)
            if self.load_l3 is not None:
                load.add_metric([name, 'l3'], self.load_l3)
            yield load


@dataclass
class GridReadings:
    #: g_sync.p_ac_grid_sum_lp
    power_total: Optional[float] = None
    #: g_sync.p_ac_sc[0]
    power_l1: Optional[float] = None
    #: g_sync.p_ac_sc[1]
    power_l2: Optional[float] = None
    #: g_sync.p_ac_sc[2]
    power_l3: Optional[float] = None
    #: g_sync.u_l_rms[0]
    voltage_l1: Optional[float] = None
    #: g_sync.u_l_rms[1]
    voltage_l2: Optional[float] = None
    #: g_sync.u_l_rms[2]
    voltage_l3: Optional[float] = None
    #: g_sync.u_ptp_rms[0]
    phase_to_phase_voltage_1: Optional[float] = None
    #: g_sync.u_ptp_rms[1]
    phase_to_phase_voltage_2: Optional[float] = None
    #: g_sync.u_ptp_rms[2]
    phase_to_phase_voltage_3: Optional[float] = None
    # grid_pll[0].f
    frequency: Optional[float] = None

    def collect(self, name: str) -> Generator:
        if self.power_total is not None:
            pass

        power = GaugeMetricFamily('rctmon_grid_power', 'Power to or from the grid by phase',
                                  labels=['inverter', 'phase'], unit='watt')
        if self.power_l1 is not None:
            power.add_metric([name, 'l1'], self.power_l1)
        if self.power_l2 is not None:
            power.add_metric([name, 'l2'], self.power_l2)
        if self.power_l3 is not None:
            power.add_metric([name, 'l3'], self.power_l3)
        yield power

        voltage = GaugeMetricFamily('rctmon_grid_voltage', 'Grid voltage by phase', labels=['inverter', 'phase'],
                                    unit='volt')
        if self.voltage_l1 is not None:
            voltage.add_metric([name, 'l1'], self.voltage_l1)
        if self.voltage_l2 is not None:
            voltage.add_metric([name, 'l2'], self.voltage_l2)
        if self.voltage_l3 is not None:
            voltage.add_metric([name, 'l3'], self.voltage_l3)
        yield voltage

        p2p_voltage = GaugeMetricFamily('rctmon_grid_voltage_phase_to_phase', 'Grid voltage phase to phase',
                                        labels=['inverter', 'measurement'], unit='volt')
        if self.phase_to_phase_voltage_1 is not None:
            p2p_voltage.add_metric([name, '1'], self.phase_to_phase_voltage_1)
        if self.phase_to_phase_voltage_2 is not None:
            p2p_voltage.add_metric([name, '2'], self.phase_to_phase_voltage_2)
        if self.phase_to_phase_voltage_3 is not None:
            p2p_voltage.add_metric([name, '3'], self.phase_to_phase_voltage_3)
        yield p2p_voltage

        frequency = GaugeMetricFamily('rctmon_grid_frequency', 'Grid frequency', labels=['inverter'], unit='hertz')
        if self.frequency is not None:
            frequency.add_metric([name], self.frequency)
        yield frequency


@dataclass
class Readings:
    '''
    Container for general readings from the device.
    '''
    temperature_heatsink: Optional[float] = None
    temperature_heatsink_batt: Optional[float] = None
    temperature_core: Optional[float] = None
    temperature_battery: Optional[float] = None

    #: inverter_sn
    serial_number: Optional[str] = None
    #: parameter_file
    parameter_file: Optional[str] = None
    #: svnversion
    control_software_version: Optional[str] = None

    # solar generators
    #: dc_conv.dc_conv_struct[0].enabled
    have_generator_a: Optional[bool] = None
    solar_generator_a = SolarGeneratorReadings()
    #: dc_conv.dc_conv_struct[1].enabled
    have_generator_b: Optional[bool] = None
    solar_generator_b = SolarGeneratorReadings()

    #: prim_sm.state
    inverter_status: Optional[int] = None
    #: prim_sm.island_flag
    inverter_grid_separated: Optional[int] = None

    household = HouseholdReadings()
    grid = GridReadings()

    # power switch / power sensor
    #: rb485.available
    power_switch_available: Optional[bool] = False
    power_switch_readings = PowerSwitchReadings()

    def collect(self, name: str) -> Generator:
        '''
        Yields metrics for all managed readings.

        :param name: Name of the inverter'
        '''

        if self.serial_number is not None and self.parameter_file is not None and \
                self.control_software_version is not None:
            yield InfoMetricFamily('rctmon_inverter', 'Information about the inverter',
                                   {'inverter': name, 'serial_number': self.serial_number,
                                    'parameter_file': self.parameter_file,
                                    'control_software_version': self.control_software_version})
        # Generators
        if self.have_generator_a or self.have_generator_b:
            gen_voltage = GaugeMetricFamily('rctmon_generator_voltage', 'Solar generator voltage',
                                            labels=['inverter', 'generator'], unit='volt')
            gen_power = GaugeMetricFamily('rctmon_generator_power', 'Solar generator power',
                                          labels=['inverter', 'generator'], unit='watt')
            gen_mpp_tgt_volts = GaugeMetricFamily('rctmon_generator_mpp_target_voltage', 'Target voltage of MPP '
                                                  'tracker', labels=['inverter', 'generator'], unit='volt')
            gen_mpp_search_stp = GaugeMetricFamily('rctmon_generator_mpp_search_step', 'MPP search step',
                                                   labels=['inverter', 'generator'], unit='volt')

            def collect_gen(gen: SolarGeneratorReadings, name: str, gen_name: str) -> None:
                if gen.voltage is not None:
                    gen_voltage.add_metric([name, gen_name], gen.voltage)
                if gen.power is not None:
                    gen_power.add_metric([name, gen_name], gen.power)
                if gen.mpp_target_voltage is not None:
                    gen_mpp_tgt_volts.add_metric([name, gen_name], gen.mpp_target_voltage)
                if gen.mpp_search_step is not None:
                    gen_mpp_search_stp.add_metric([name, gen_name], gen.mpp_search_step)

            if self.have_generator_a:
                collect_gen(self.solar_generator_a, name, 'a')
            if self.have_generator_b:
                collect_gen(self.solar_generator_b, name, 'b')
            yield gen_voltage
            yield gen_power
            yield gen_mpp_tgt_volts
            yield gen_mpp_search_stp

        temp = GaugeMetricFamily('rctmon_temperature', 'Temperature values in °C', labels=['inverter', 'sensor'])
        if self.temperature_heatsink is not None:  # db.temp1
            temp.add_metric([name, 'heatsink'], self.temperature_heatsink)
        if self.temperature_heatsink_batt is not None:  # db.temp2
            temp.add_metric([name, 'heatsink_battery_actuator'], self.temperature_heatsink_batt)
        if self.temperature_core is not None:  # db.core_temp
            temp.add_metric([name, 'core'], self.temperature_core)
        if self.temperature_battery is not None: # battery.temperature
            temp.add_metric([name, 'battery'], self.temperature_battery)
        yield temp

        if self.inverter_status is not None:
            ivs = GaugeMetricFamily('rctmon_inverter_status', 'Status of the inverter', labels=['inverter'])
            ivs.add_metric([name], self.inverter_status)
            yield ivs

        if self.inverter_grid_separated is not None:
            igs = GaugeMetricFamily('rctmon_inverter_grid_separated', 'Status of the island mode', labels=['inverter', 'grid'])
            igs.add_metric([name], self.inverter_grid_separated)
            yield igs
        
        yield from self.household.collect(name)
        yield from self.grid.collect(name)

        if self.power_switch_available:
            yield from self.power_switch_readings.collect(name)
