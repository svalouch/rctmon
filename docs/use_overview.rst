
#####################
Overview & Quickstart
#####################

RctMon connects to a single RCT Power inverter and exposes values to other programs. It does not support plant
communication (using a inverter as a gateway to reach other inverters connected to it).

The program takes a moment to get up to speed, as it must discover the inverters inventory (e.g. are one or two solar
generators connected, is there a battery and how many units does it have, is there a Power Switch present). It starts
by requesting the device name, and if it receives an answer starts to request more information. As the information
flows in, it starts requesting metrics from various parts of the setup. These metrics are periodically sent at
different intervals (slow-changing ones more seldom than fast-changing ones).

Depending on the configuration, the information is presented via the `Prometheus <https://prometheus.io/>`_-compatible
exposition endpoint or pushed to an `InfluxDB <https://www.influxdata.com/products/influxdb/>`_ or both at the same
time.

Requirements and installation
*****************************
The program requires at least *Python 3.7* (e.g. on Debian Buster), as well as some packages from PyPI that are usually
not (yet) packaged by most Linux distributions.

Thus, the recommended way is to install it into a virtual environment. As there hasn't been a release yet (and thus no
package been pushed to PyPI), the best way is to install from the repository directly. As there are many different
flavors of virtual environments, one was chosen for these examples: `venv
<https://docs.python.org/3/library/venv.html>`_. Most distributions have this either installed by default or make it
available as a package named ``python3-venv``.

Installation from git directly
==============================
This method pulls the code into a virtualenv without cloning it first. It is pretty flexible in what version (down to
the commit) to use, but not suitable for development.

Start by creating a virtual environment at a location of your liking (adapt paths accordingly) and activate it:

.. code-block:: shell-session

   $ python3 -m venv ${HOME}/rctmon-venv
   $ source ${HOME}/rctmon-venv/bin/activate
   (rctmon-venv) $

Use ``pip`` to install the package. Depending on the URL you use, you can get different versions, here are some
examples:

* ``git+https://github.com/svalouch/rctmon`` installs the lastest commit in the default branch.
* ``git+https://github.com/svalouch/rctmon@edd645d98f6790c78d5fe9834719f17d1114fb6b`` installs the version at the
  specified commit.
* ``git+https://github.com/svalouch/rctmon@main`` installs the lastest commit in the branch ``main``.
* ``git+https://github.com/svalouch/rctmon@v0.0.1`` installs the specified tag.

Assuming you wish to get the latest version, use the first URL:

.. code-block:: shell-session

   (rctmon-venv) $ pip install git+https://github.com/svalouch/rctmon
   Collecting git+https://github.com/svalouch/rctmon
     Cloning https://github.com/svalouch/rctmon to ./pip-req-build-cf05vntg
     Running command git clone -q https://github.com/svalouch/rctmon /tmp/pip-req-build-cf05vntg
   Using legacy 'setup.py install' for rctmon, since package 'wheel' is not installed.
   Installing collected packages: rctmon
       Running setup.py install for rctmon ... done
   Successfully installed rctmon-0.0.1

The program is now installed as ``rctmon`` into the ``bin`` subfolder of the virtualenv and can be called from there.

Installation from local clone
=============================
More suitable for development, cloning the repository and installing it "editable" into a virtualenv allows for easy
modifications that are effective at the next start of the program.

Start by cloning the repository to a location of your liking:

.. code-block:: shell-session

   $ cd ${HOME}
   $ git clone https://github.com/svalouch/rctmon
   Cloning into 'rctclient'...
   remote: Enumerating objects: 327, done.
   remote: Counting objects: 100% (327/327), done.
   remote: Compressing objects: 100% (175/175), done.
   remote: Total 327 (delta 185), reused 261 (delta 119), pack-reused 0
   Receiving objects: 100% (327/327), 149.61 KiB | 1.89 MiB/s, done.
   Resolving deltas: 100% (185/185), done.

Next, create a virtualenv and activate it. It doesn't matter where, even inside the cloned repository is fine:

.. code-block:: shell-session

   $ python3 -m venv ${HOME}/rctmon-venv
   $ source ${HOME}/rctmon-venv/bin/activate
   (rctmon-venv) $

Then install it with ``pip``. Specify the path to the cloned repository and specify ``--editable``:

.. code-block:: shell-session

   (rctmon-venv) $ pip install -e ${HOME}/rctmon/
   Obtaining file:///home/user/rctmon
   Installing collected packages: rctmon
     Running setup.py develop for rctmon
   Successfully installed rctmon-0.0.1

.. hint::

   There are two additional targets ``dev`` and ``docs`` which install additional dependencies for development. Specify
   one or both in square brakets at the end of the path in the ``pip install`` command: ``pip install -e
   rctmon[dev,docs]`` to have them installed automatically.

Configuration
*************
A configuration file is provided as an example in the repository as ``config.example.yml``. As the name implies, the
software expects a file in the *YAML* format for its configuration. The example file shows all the settings at their
default values (unless otherwise noted). The sections need to exist, but may be empty to take the defaults.

.. literalinclude:: ../config.example.yml
   :language: yaml
   :linenos:

Do not be afraid of the large ``logging``-section, it can be left out entirely. The section just shows what the
internal defaults are and hint at how to refine it if needed.

Section "device"
================
This section defines the address of the inverter (referenced as "device" throughout the codebase) to connect to, and
which port to use. The port most likely doesn't need to be changed.

Section "prometheus"
====================
Prometheus is a metrics-based monitoring system. RctMon provides a compatible endpoint, which is bound to
``http://127.0.0.1:9831/metrics`` by default (and can be viewed in a browser) if ``enable`` is *true*. It will expose
various details about the process and the Python interpreter itself, as well as providing a view into the internal
state of the running application. This is useful for setting up alerting, e.g. if it can't reach the inverter.

If ``exposition`` is enabled as well, it will also export all the metrics it collects at the aforementioned endpoint.

Section "influxdb"
==================
The time series database InfluxDB is supported in versions *1.8* and *2.x*, due to the usage of the new API, which was
added to 1.8 to ease transition.

.. note::

   Appart from writing measurements, RctMon won't create any structures. The database (1.8) or bucket (2.x) as well as
   the user (1.8) or access token (2.x) needs to be supplied by the user.

Not creating structures allows the application to focus on its main tasks and limits the damange greatly should
something go wrong. It only requires ``write``-permission to the database or bucket.

The ``url`` defines the place where the write API can be reached. The database (1.8) or bucket (2.x) is specified in
the ``bucket`` field. The ``org`` is only required for version 2.x and ignored in 1.8. The ``token`` needs to be set to
``<username>:<password>`` of the user for version 1.8 and the access token string for 2.x.

.. warning::

   As of version ``0.0.1``, the application will hang if the InfluxDB cannot be reached. This will be addresses in
   later releases.

Section "mqtt"
==============
MQTT is a lightweight publish/subscribe machine-to-machine messaging protocol. All functional metrics exposed for
prometheus can be published into respective mqtt topics, when MQTT support is enabled by setting ``enable`` to *true*
and the MQTT server is configured as ``mqtt_host`` and optionally ``mqtt_port`` to use a non-default port.
If MQTT Server use encryption use ``tls_enable: true`` to activate TLS/SSL connection. Use ``tls_insecure`` and 
``tls_ca_cert`` for fine tuning. For authentication ``mqtt_user`` + ``mqtt_pass`` or/and ``tls_certfile`` + ``tls_keyfile`` 
can be used. If values should not persis in the MQTT server set ``mqtt_retain: false``. By default the topic prefix is 
"rctmon", "topic_prefix" will overwrite it. 

Section "logging"
=================
This section can be omitted entirely, it just shows the internal defaults which log to ``stdout`` by default, suitable
for the journal to pick it up. It is directly passed to `logging.config.dictConfig
<https://docs.python.org/3/library/logging.config.html#logging-config-dictschema>`_ to allow for maximum flexibility.

Note that this doesn't need to be touched to enable debug mode: Specify ``--debug`` on the command line will set
(almost) all loggers to ``DEBUG`` level.

Running
*******
With a config file at hand and an activated virtualenv, simply run ``rctmon -c config.yml daemon``. It will stay in
foreground and (by default) log to standard output.

Optional: SystemD
=================
If ``python3-systemd`` is installed in the virtualenv, the daemon will communicate its state to *systemd*, allowing for
``type=notify`` service units to be used. This is optional, without that module it can still be run as a simple service
just fine.
