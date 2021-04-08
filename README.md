# Metrics extractor for RCT Inverters

Tool to extract metrics from a single solar inverter by RCT Power GmbH, using their proprietary Serial Communication
Protocol. The project is not in any way affiliated with or supported by RCT Power GmbH. Use at your own risk.

It extracts a subset of the metrics available, mainly the most interesting ones that are presented to users in the
official RCT smartphone apps overview screen.

Data can be exposed via a [Prometheus](https://prometheus.io/) compatible endpoint or pushed to an
[InfluxDB](https://www.influxdata.com/products/influxdb/) (versions 1.8 and 2.x), or both at the same time. The
smartphone app can be used at the same time it is running, but both parties will start to receive invalid frames, so
updating the view in the app and updating metrics in rctmon will slow down because of that. The application should be
stopped during firmware update as a precautionary measure.

The project is still in its early stages of development. Metric names in the Prometheus export as well as measurement
and field names pushed to InfluxDB may change without notice.

## Installation

Install and update using [pip](https://pip.pypa.io/en/stable/quickstart/):
```
$ pip install -U git+https://github.com/svalouch/rctmon
```

## Configuration example

See the `config.example.yml` in the projects root folder. As an InfluxDB setup requires some more moving parts, the
setup for that is in the documentation. Here is a minimal version to get going with a Prometheus endpoint that is far
easier to configure.

Assuming the inverter is at `192.168.0.1:8899`, a minimal configuration could look like this:

```yaml
---
device:
  host: 192.168.0.1
  port: 8899

prometheus:
  enable: true
  exposition: true

influxdb:
  enable: false
```

Then start the application: `rctmon -c <configfile.yml> daemon`

Quick peek at the metrics: `curl localhost:8082/metrics`. Note that the application needs to discover the inverters
setup first (how many batteries, is a power switch available and so on) and thus takes a moment for all the metrics to
appear.

## Debugging

For most problems, starting the application in Debug Mode is sufficient. Simply add `--debug`, like so: `rctmon --debug
-c <configfile.yml> daemon` and watch the output. Another way is to configure the Python logging infrastructure, see
the `logging` key in the `config.example.yml` example config file.

To figure out what's going on on the wire, capture the packets with `tcpdump` or `wireshark`, if other devices such as
smartphones are accessing the inverter at the same time it may be required to capture the data at a point where these
flows are visible too, such as the router. The dump can then be viewed using the `read_pcap.py` tool from the
[rctclient](https://github.com/svalouch/python-rctclient) project.
