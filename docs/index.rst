##################################
Welcome to RctMon's documentation!
##################################

The software at hand is a metric collection application querying a single solar inverter made by  RCT Power GmbH using
their proprietary *Serial Communication Protocol* (via the `rctclient <https://rctclient.readthedocs.io/en/latest/>`_
implementation). Despite its name, it does not actually alert on the retrieved values, but dispatches this to other
systems that are meant to that task, namely exposing it for `Prometheus <https://prometheus.io/>`_ and `InfluxDB
<https://www.influxdata.com/products/influxdb/>`_.

**Disclaimer**: This project is not in any way affiliated with or supported by RCT Power GmbH. Use the projects
bugtracker if there are any issues. Use at your own risk. None of the contributors can be held liable for any damage
that may occur by using the software. See also the *LICENSE* file for further information.

.. toctree::
   :maxdepth: 2
   :caption: Usage:

   use_overview
   use_prometheus
   use_influxdb


.. toctree::
   :maxdepth: 2
   :caption: Internal workings

