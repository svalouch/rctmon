
########
InfluxDB
########

RctMon uses the official InfluxDB Python module, which supports the "new" API introduced with InfluxDB 2.x only.
Luckily, that API was backported to version 1.8 to ease transition.

.. warning::

   As of version ``0.0.1``, RctMon blocks if it can't reach the InfluxDB. This will be addressed in a later release.

Configuration
*************
In the configuration, the ``influxdb`` section needs to be configured to enable RctMon to push to an InfluxDB.

+------------+-----------------------+-------------------------------------+
| Setting    | V1.8                  | V2.x                                |
+============+=======================+=====================================+
| ``enable`` | Whether to enable pushing to InfluxDB                       |
+------------+-----------------------+-------------------------------------+
| ``url``    | URL to connect to, e.g. ``http://localhost:8086``           |
+------------+-----------------------+-------------------------------------+
| ``token``  | ``username:password`` | Access token                        |
+------------+-----------------------+-------------------------------------+
| ``org``    | ignored               | Organization name, e.g. ``rct-org`` |
+------------+-----------------------+-------------------------------------+
| ``bucket`` | ``database`` name     | Bucket name, e.g. ``mybucket``      |
+------------+-----------------------+-------------------------------------+

InfluxDB 1.8 setup
==================

InfluxDB 2.x setup
===================

Setting this up is rather complicated compared to earlier versions. Assuming you have access to an almighty admin user,
let's create the full set of structures:

#. An *organization*: ``influx org create -n rct-org``
#. Create a user in that organization: ``influx user create -n rctmon -o rct-org``
#. A bucket: ``influx bucket create -n rct-inverter -o rct-org``
#. Get the bucket id: ``influx bucket list -o rct-inverter``
#. Create an access token for the user, allowing it to write to the bucket: ``influx auth create -o rct-org --user
   rctmon --write-bucket <bucket id from previous command>``

Measurements
************

All measurements have a field ``inverter`` that bears the name of the inverter, the same name as displayed in the app.

rct_raw
=======
All of the data that is received is written to this measurement immediately. Fields are used to record the different
data types:

* ``value_bool``
* ``value_float``
* ``value_int``
* ``value_string``

The raw name of the frame (such as ``dc_conv.dc_conv_struct[1].p_dc``, which is the power in watt of the second solar
generator)) is in the field ``name``, and the corresponding OID (such as ``0xAA9AA253``) is in the ``oid`` field.

Some fields are seldomly or never queried appart from the start of the application, especially the string and boolean
fields that are used to query the inventory of the device.

battery_module
==============

battery_overview
================

temperature
===========

