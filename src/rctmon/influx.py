
# Copyright 2021, Stefan Valouch (svalouch)
# SPDX-License-Identifier: GPL-3.0-only

'''
InfluxDB writer
'''

import logging
from typing import Generator, Iterable, List, Optional, Union

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import WriteApi, SYNCHRONOUS
from influxdb_client.domain.write_precision import WritePrecision
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily, REGISTRY as P_R

from .config import InfluxDBConfig


class InfluxDB:
    '''
    InfluxDB client wrapper.

    Compatible with InfluxDB 2.0 and 1.8 using batch mode. Points are added single or in bulk via ``add_points`` and
    ``flush`` pushes them to the server. Metrics may be lost when the database is not available.
    '''

    _client: Optional[InfluxDBClient]
    _write_precision = WritePrecision.S
    _buffer: List[bytes]
    _points_written = 0

    def __init__(self, config: InfluxDBConfig):
        self._config = config
        self._buffer = list()
        self._log = logging.getLogger(__name__)

        if config.enable:
            self._log.info('Enabled, creating client')
            self._client = InfluxDBClient(url=config.url, token=config.token.get_secret_value(), org=config.org)

            P_R.register(self)

    def collect(self) -> Generator:
        '''
        Prometheus custom collector.
        '''
        if self._config.enable:
            yield from ()
        else:
            yield CounterMetricFamily('rctmon_influx_points_written', 'Amount of points that were sent off since '
                                      'application startup', value=self._points_written)

    def add_points(self, data: Union[str, Iterable['str'], Point, Iterable['Point'], dict, Iterable['dict'], bytes,
                                     Iterable['bytes']]) -> None:
        '''
        Add points to the buffer.
        '''
        if self._client:
            if isinstance(data, bytes):
                self._buffer.append(data)

            elif isinstance(data, str):
                self.add_points(data.encode('utf-8'))
            elif isinstance(data, Point):
                self.add_points(data.to_line_protocol().encode('utf-8'))
            elif isinstance(data, dict):
                self.add_points(
                    Point.from_dict(data, write_precision=self._write_precision).to_line_protocol().encode('utf-8'))
            elif isinstance(data, Iterable):
                for item in data:
                    self.add_points(item)

    def flush(self) -> None:
        self._log.debug('Flushing %d entries', len(self._buffer))
        if self._client and len(self._buffer) > 0:
            with self._client.write_api() as writer:
                self._points_written += len(self._buffer)
                writer.write(bucket=self._config.bucket, org=self._config.org, record=self._buffer,
                             write_precision=self._write_precision)
                self._buffer.clear()
