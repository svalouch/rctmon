
#####################
Prometheus exposition
#####################

`Prometheus <https://prometheus.io/>`_ is an event monitoring and alerting system, based on a time series database. It
is commonly used to monitor IT-systems such as servers and the applications they run. If enabled through ``prometheus →
enable`` in the configuration, RctMon exposes its internal state, ready to be scraped by one or more Prometheus
servers. For a nice graphical representation of the collected data, `Grafana <https://grafana.com/>`_ is recommended.

Configuration
*************

If enabled, the endpoint can be configured using ``prometheus → bind_address`` and ``prometheus → bind_port``. For
example, to make them accessible from the same machine only, specify ``127.0.0.1`` or ``localhost`` for
``bind_address``. The port can also be changed from the default, by setting ``bind_port`` to (for example) ``8080``.
The combination will make the metrics available at ``http://localhost:8080/metrics``.

In addition to that, if both ``prometheus → enable`` **and** ``prometheus → exposition`` are enabled, the readings from
the inverter will be available here, too. The values are cached internally, as the inverters responses are too slow for
live readings. This in turn allows for redundant scraping from multiple Prometheus servers at high frequency without
affecting the inverter in any way.

Prometheus configuration
========================
In ``prometheus.yml`` (usually in ``/etc/prometheus/``), add the endpoint to the ``scrape_config``, for example like
so:

.. code-block:: yaml

   scrape_configs:
     - job_name: rctmon
       static_configs:
         - targets:
             - localhost:8080

The default place for metrics is ``/metrics``, thus specifying the host and port is enough. Note that the exposition
does not support TLS encryption or any form of authentication and adding that is **not** planed. If required, configure
a reverse proxy such as HAProxy, Nginx or Apache.

InfluxDB configuration
======================
InfluxDB 2.x is able to scrape Prometheus endpoints. This may be useful for monitoring the application state with
InfluxDB rather than Prometheus. It doesn't make sense to enable ``prometheus → exposition`` in this case as the
application can push the inverter metrics to InfluxDB just fine.

Please refer to the `Manage scrapers
<https://docs.influxdata.com/influxdb/v2.0/write-data/no-code/scrape-data/manage-scrapers/>`_ section in the InfluxDB
manual.

Application metrics / monitoring
********************************

The metrics meant for monitoring the application are always present when the Prometheus endpoint is active. Some of
them stem from the default *python* and *process* exporter built into the library that is used to create the endpoint.
They start with ``python_`` and ``process_`` and are usually of low interest.

All metrics from RctMon start with the string ``rctmon_``. Due to the design of the library, for each metric an
additional metric is created, ending in ``_created``. This is due to the OpenMetrics format supported by the library
and can't be deactivated.

As of version ``0.0.1``, the following metrics are exposed:

+----------------------------------+-------+--------------------------------------------------------------------------+
| Name                             | Type  | Description                                                              |
+==================================+=======+==========================================================================+
| ``rctmon_bytes_received_total``  | Gauge | Amount of bytes received from the inverter since start of the program    |
+----------------------------------+-------+--------------------------------------------------------------------------+
| ``rctmon_bytes_sent_total``      | Gauge | Amount of bytes sent to the inverter since the start of the program      |
+----------------------------------+-------+--------------------------------------------------------------------------+
| ``rctmon_decode_error_total``    | Gauge | Amount of errors that occured during parsing and decoding responses from |
|                                  |       | the inverter. The ``kind`` label can be ``crc`` for CRC checksum         |
|                                  |       | mismatches, ``command`` for when the command byte was invalid and the    |
|                                  |       | frame couldn't be parsed, ``payload`` when the frame was received        |
|                                  |       | correctly but the data it carried was invalid, and ``length`` indicating |
|                                  |       | that the parser overshot the end of the frame and the frame was dropped. |
+----------------------------------+-------+--------------------------------------------------------------------------+
| ``rctmon_device_up``             | Gauge | Shows if the connection to the inverter is up (``1``) or not (``0``).    |
+----------------------------------+-------+--------------------------------------------------------------------------+
| ``rctmon_frames_received_total`` | Gauge | Amount of frames received since the start of the program (not including  |
|                                  |       | decode errors)                                                           |
+----------------------------------+-------+--------------------------------------------------------------------------+
| ``rctmon_frames_sent_total``     | Gauge | Amount of frames sent since the start of the program.                    |
+----------------------------------+-------+--------------------------------------------------------------------------+
| ``rctmon_info``                  | Info  | Information about the program, such as its version.                      |
+----------------------------------+-------+--------------------------------------------------------------------------+

Inverter metrics
****************

These become available if ``prometheus → exposition`` is enabled. It may take a moment after program start for them to
appear as the inventory of the inverter needs to be queried before the values can be requested from it.

They all have a label ``inverter`` which contains the name of the inverter. This is the same name as shown in the
smartphone app made by RCT (internally called ``android_description``).

Percentages are generally in the range ``0.0`` to ``1.0``.

.. warning::

   RctMon is still in development, individual metrics may be added, removed or renamed without prior notice!

+---------------------------------------------------+-----------------------------------------------------------------+
| Name                                              | Description                                                     |
+===================================================+=================================================================+
| ``rctmon_inventory``                              | A ``component`` label shows that a component was detected, such |
|                                                   | as ``generator_a`` and ``generator_b`` for the solar strings or |
|                                                   | ``power_switch`` for the Power Switch component.                |
+---------------------------------------------------+-----------------------------------------------------------------+
| ``rctmon_inverter_info``                          | Shows static info such as the ``control_software_version``, the |
|                                                   | ``serial_number`` and ``parameter_file``.                       |
+---------------------------------------------------+-----------------------------------------------------------------+
| ``rctmon_generator_voltage_volt``                 | Voltage, label ``generator`` is ``a`` or ``b``.                 |
+---------------------------------------------------+-----------------------------------------------------------------+
| ``rctmon_generator_power_watt``                   | Watt, label ``generator`` (``a``, ``b``).                       |
+---------------------------------------------------+-----------------------------------------------------------------+
| ``rctmon_generator_mpp_target_voltage_volt``      | MPP target voltage, label ``generator`` (``a``, ``b``).         |
+---------------------------------------------------+-----------------------------------------------------------------+
| ``rctmon_generator_mpp_search_step_volt``         | MPP search step, label ``generator`` (``a``, ``b``).            |
+---------------------------------------------------+-----------------------------------------------------------------+
| ``rctmon_temperature``                            | Component temperature for builtin components                    |
+---------------------------------------------------+-----------------------------------------------------------------+
| ``rctmon_household_load``                         | Household load over all phases                                  |
+---------------------------------------------------+-----------------------------------------------------------------+
| ``rctmon_household_load_phase``                   | Single-phase load, label ``phase`` is ``l1`` to ``l3``.         |
+---------------------------------------------------+-----------------------------------------------------------------+
| ``rctmon_grid_power_watt``                        | Grid power, label ``phase`` is ``l1`` to ``l3``.                |
+---------------------------------------------------+-----------------------------------------------------------------+
| ``rctmon_grid_voltage_volt``                      | Grid voltage, label ``phase`` is ``l1`` to ``l3``.              |
+---------------------------------------------------+-----------------------------------------------------------------+
| ``rctmon_grid_voltage_phase_to_phase_volt``       | Phase-to-phase voltage                                          |
+---------------------------------------------------+-----------------------------------------------------------------+
| ``rctmon_powerswitch_info``                       | Information about the Power Switch component if detected, such  |
|                                                   | as the ``bootloader_version`` and ``software_version``          |
+---------------------------------------------------+-----------------------------------------------------------------+
| ``rctmon_grid_voltage_volt``                      | Grid voltage, ``phase`` is ``l1`` to ``l3``.                    |
+---------------------------------------------------+-----------------------------------------------------------------+
| ``rctmon_grid_frequency_hertz``                   | Grid frequency, ``phase`` is ``l1`` to ``l3``.                  |
+---------------------------------------------------+-----------------------------------------------------------------+
| ``rctmon_powerstorage_frequency_hertz``           | Inverter frequency if active, ``phase`` is ``l1`` to ``l3``.    |
+---------------------------------------------------+-----------------------------------------------------------------+
| ``rctmon_bms_info``                               | Information about the BMS if detected, ``serial_number``        |
+---------------------------------------------------+-----------------------------------------------------------------+
| ``rctmon_battery_state_of_charge_min_percent``    | Battery, minimum soc                                            |
+---------------------------------------------------+-----------------------------------------------------------------+
| ``rctmon_battery_voltage``                        | Battery voltage                                                 |
+---------------------------------------------------+-----------------------------------------------------------------+
| ``rctmon_battery_power``                          | Battery power                                                   |
+---------------------------------------------------+-----------------------------------------------------------------+
| ``rctmon_battery_state``                          | Battery state (state machine position)                          |
+---------------------------------------------------+-----------------------------------------------------------------+
| ``rctmon_battery_state_of_charge_target_percent`` | Battery target SOC                                              |
+---------------------------------------------------+-----------------------------------------------------------------+
| ``rctmon_battery_state_of_health_percent``        | Battery health                                                  |
+---------------------------------------------------+-----------------------------------------------------------------+
| ``rctmon_battery_temperature``                    | Battery temperature                                             |
+---------------------------------------------------+-----------------------------------------------------------------+
| ``rctmon_battery_bat_status``                     | Battery status                                                  |
+---------------------------------------------------+-----------------------------------------------------------------+
| ``rctmon_battery_impedance_fine``                 | Battery impedance                                               |
+---------------------------------------------------+-----------------------------------------------------------------+
| ``rctmon_battery_discharge_amp_hours_total``      | Total amount of discharged energy                               |
+---------------------------------------------------+-----------------------------------------------------------------+
| ``rctmon_battery_stored_energy_total``            | Total amount of charged energy                                  |
+---------------------------------------------------+-----------------------------------------------------------------+
| ``rctmon_battery_state_of_charge_min_percent``    |                                                                 |
+---------------------------------------------------+-----------------------------------------------------------------+
