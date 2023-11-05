
# Copyright 2021, Stefan Valouch (svalouch)
# SPDX-License-Identifier: GPL-3.0-only

'''
Configuration management.
'''

# pylint: disable=too-few-public-methods  # configuration declarations don't contain methods

from typing import Optional, Union

from pydantic import BaseModel, SecretStr


class DeviceConfig(BaseModel):
    '''
    Settings for the device.
    '''
    #: Address of the device to monitor
    host: str = 'localhost'
    #: Port on the device to connect to
    port: int = 8899


class InfluxDBConfig(BaseModel):
    '''
    InfluxDB configuration.
    '''
    #: Whether to enable pushing to InfluxDB
    enable: bool = False
    #: URL to connect to
    url: str = 'http://localhost:8086'
    #: Token that allows access
    token: SecretStr = SecretStr('')
    #: Organization to use
    org: str = 'rctmon'
    #: Database to use
    bucket: str = 'rctmon'


class PrometheusConfig(BaseModel):
    '''
    Prometheus configuration.
    '''
    #: Whether to enable the prometheus endpoint for monitoring and potentially value exposition
    enable: bool = True
    #: Enable exposition of device metrics
    exposition: bool = False
    #: Address to bind to
    bind_address: str = '127.0.0.1'
    #: Port to bind to
    bind_port: int = 9831


class MqttConfig(BaseModel):
    '''
    Mqtt Configuration.
    for details about the tls config see:
    https://eclipse.dev/paho/index.php?page=clients/python/docs/index.php#option-functions
    look for `tls_set` and `tls_insecure_set`
    '''
    enable: bool = False
    mqtt_host: str
    mqtt_port: int = 1883
    mqtt_retain: bool = True
    client_name: str = 'rctmon'
    flush_interval_seconds: int = 30
    topic_prefix: str = "rctmon"
    auth_user: Union[str, None] = None
    auth_pass: Union[str, None] = None
    tls_enable: bool = False
    tls_insecure: bool = False
    tls_ca_cert: Union[str, None] = None
    tls_certfile: Union[str, None] = None
    tls_keyfile: Union[str, None] = None

class RctMonConfig(BaseModel):
    '''
    Main settings container.
    '''
    device: DeviceConfig
    prometheus: PrometheusConfig
    influxdb: InfluxDBConfig
    mqtt: MqttConfig
