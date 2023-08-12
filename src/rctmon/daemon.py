
# Copyright 2021, Stefan Valouch (svalouch)
# SPDX-License-Identifier: GPL-3.0-only

'''
Daemon implementation.
'''

import errno
import logging
import select
import signal
import socket

from datetime import datetime, timedelta
from typing import List, Optional

from prometheus_client import start_http_server as prometheus_start_http_server, REGISTRY as P_R
from rctclient.exceptions import FrameCRCMismatch, InvalidCommand, FrameLengthExceeded
from rctclient.frame import ReceiveFrame
from rctclient.registry import REGISTRY as R
from rctclient.types import Command, DataType

from . import version_major, version_minor, version_patch, __version__
from .config import RctMonConfig
from .device_manager import DeviceManager
from .influx import InfluxDB
from .monitoring import MON_FRAMES_SENT, MON_FRAMES_RECEIVED, MON_DECODE_ERROR, MON_INFO
from .monitoring import MON_BYTES_SENT, MON_BYTES_RECEIVED, MON_DEVICE_UP, setup_monitoring
from .mqtt import MqttClient

try:
    import systemd.daemon  # type:ignore
    logging.getLogger('rctmon.daemon').info('Systemd module detected')
    HAVE_SYSTEMD = True
except ImportError:
    logging.getLogger('rctmon.daemon').info('Not using systemd module')
    HAVE_SYSTEMD = False


MON_INFO.info({'version': __version__, 'version_major': version_major, 'version_minor': version_minor,
               'version_patch': version_patch})

log = logging.getLogger(__name__)
socklog = logging.getLogger(__name__ + '.socket')
framelog = logging.getLogger(__name__ + '.frame')


class TSCollection:  # pylint: disable=too-few-public-methods
    '''
    Container for timestamps used by the Daemon.
    '''
    last_contact_attempt = datetime.min
    last_contect_successful = datetime.min
    last_frame_sent = datetime.min
    last_data_received = datetime.utcnow()
    last_influx_collect = datetime.utcnow()
    last_influx_flush = datetime.utcnow()  # we don't want to flush immediately
    last_mqtt_collect = datetime.utcnow()
    last_mqtt_flush = datetime.utcnow()  # we don't want to flush immediately


class Daemon:
    '''
    Daemon implementation. The daemon runs continuously in a 1 second tight loop. It requests payloads from the
    DeviceManager at periodic intervals and dispatches the received frames back to it.
    '''

    #: Set this to True to stop the loop (e.g. to terminate the program).
    _stop: bool
    #: timestamp when the last set of frames was assembled by the device manager and put into the send buffer
    _ts_last_frame_sent: datetime
    #: communication socket, do not use if _connected is False
    _socket: socket.socket
    #: Device manager
    _device_manager: DeviceManager

    #: Whether debug mode is on
    _debug: bool
    #: Buffer for to-be-sent data
    _send_buf: bytes
    #: Buffer for received data
    _recv_buf: bytes
    #: Whether the connection to the device is established
    _connected: bool
    #: Buffer for decoding received data
    _current_frame: Optional[ReceiveFrame]

    #: Instance of the settings
    _settings: RctMonConfig

    _influx: InfluxDB
    _mqtt: MqttClient

    def __init__(self, settings: RctMonConfig, debug: bool = False) -> None:
        log.info('Daemon initializing')

        self._settings = settings
        self._debug = debug
        self._stop = False
        self._send_buf = b''
        self._recv_buf = b''
        self._current_frame = None
        self._connected = False

        self._influx = InfluxDB(self._settings.influxdb)
        self._device_manager = DeviceManager(self._influx)

        self._ts = TSCollection()

        signal.signal(signal.SIGTERM, self.signal_handler)

        if self._settings.prometheus.exposition:
            self._settings.prometheus.enable = True

        if self._settings.prometheus.enable:
            log.info('Prometheus endpoint is at http://%s:%d/metrics', self._settings.prometheus.bind_address,
                     self._settings.prometheus.bind_port)
            setup_monitoring(self._settings.prometheus)

        if self._settings.mqtt.enable:
            log.info('Mqtt endpoint is at %s', self._settings.mqtt.mqtt_host)
            self._mqtt = MqttClient(self._settings.mqtt)

        if HAVE_SYSTEMD:
            log.info('Signaling readiness')
            systemd.daemon.notify('READY=1')

        log.info('Ready to start the main loop')

    def signal_handler(self, signum, _frame):
        '''
        Signal handler, called by the interpreter if a signal is received which was selected using the
        ``signal.signal`` function before.

        * ``SIGTERM`` causes the main loop to terminate gracefully.
        '''

        if signum == signal.SIGTERM:
            log.info('Caught SIGTERM, shutting down')
            if HAVE_SYSTEMD:
                systemd.daemon.notify('STOPPING=1')
            self._stop = True
        else:
            log.warning('Caught signal %d, no handler, ignoring', signum)

    def cleanup(self) -> None:
        '''
        Cleanup code. This is called after the main loop ends before the program terminates.
        '''
        self._socket_disconnect()

    def _socket_connect(self) -> None:

        self._ts.last_contact_attempt = datetime.utcnow()
        log.debug('Creating socket: %s:%d', self._settings.device.host, self._settings.device.port)
        self._connected = False

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setblocking(False)
        err = self._socket.connect_ex((self._settings.device.host, self._settings.device.port))
        if err != errno.EINPROGRESS:
            if err == errno.ECONNREFUSED:
                socklog.warning('Connection refused')
            else:
                socklog.warning('Socket error: %s', err)
        else:
            socklog.debug('Connection established')
            self._connected = True
            self._ts.last_data_received = datetime.utcnow()

    def _socket_disconnect(self) -> None:

        self._connected = False
        self._send_buf = b''
        if self._socket:
            # self._socket.shutdown(socket.SHUT_RDWR)
            self._socket.close()
            socklog.info('Socket disconnected')
        self._connected = False

    def _handle_socket_read(self) -> None:
        '''
        Handles reading from the socket. Called when select() returns our socket as having data to read.
        '''
        socklog.debug('socket is readable')
        try:
            recv_data = self._socket.recv(4096)
        except ConnectionRefusedError:
            socklog.warning('Socket receive: Connection refused')
            self._socket_disconnect()
        except ConnectionResetError:
            socklog.warning('Socket receive: Connection reset')
            self._socket_disconnect()
        except TimeoutError:
            socklog.warning('Socket receive: Connection timed out')
            self._socket_disconnect()
        except ConnectionError:
            socklog.warning('Socket receive: Connection error')
            self._socket_disconnect()
        else:
            recv_len = len(recv_data)
            socklog.debug('Got %d from socket', recv_len)
            if recv_len == 0:
                socklog.warning('Socket disconnected (empty recv)')
                self._socket_disconnect()
            else:
                MON_BYTES_RECEIVED.inc(len(recv_data))
                self._recv_buf += recv_data

    def _handle_socket_writable(self) -> None:
        '''
        Handles writing data from the buffer to the socket. Called when select indicates that the socket can be written
        to.
        '''
        socklog.debug('socket is writable')
        if len(self._send_buf) > 0:
            socklog.debug('send buf contains %d bytes', len(self._send_buf))
            try:
                num_sent = self._socket.send(self._send_buf)
                MON_BYTES_SENT.inc(num_sent)
                socklog.debug('Sent %d bytes via socket', num_sent)
                if num_sent == 0:
                    socklog.warning('Socket disconnected (no data was sent)')
                    self._socket_disconnect()
                else:
                    # total_sent += num_sent
                    self._send_buf = self._send_buf[num_sent:]
                    socklog.debug('After sending, buffer contains %d bytes', len(self._send_buf))
            except socket.error as exc:
                if exc.errno != errno.EAGAIN:
                    socklog.exception(exc)
                    socklog.error('Got unexpected exception when sending: errno=%d: %s', exc.errno, str(exc))
                    self._socket_disconnect()

    def run(self) -> None:
        '''
        Main loop implementation. Set ``self._stop`` to `False` to have it terminate at the next iteration. This
        function does not return unless an exception is not caught or ``self._stop`` is set to false. It calls the
        cleanup function before returning.
        '''
        log.info('Starting main loop')

        sockets_read: List[socket.socket] = list()
        sockets_write: List[socket.socket] = list()
        sockets_exc: List[socket.socket] = list()

        while not self._stop:
            sockets_read.clear()
            sockets_write.clear()
            sockets_exc.clear()

            if not self._connected:
                MON_DEVICE_UP.set(0)
                if self._ts.last_contact_attempt < datetime.utcnow() - timedelta(seconds=60):
                    self._ts.last_contact_attempt = datetime.utcnow()
                    log.info('Time to attempt reconnection')
                    self._socket_connect()
            elif self._ts.last_data_received < datetime.utcnow() - timedelta(seconds=180):
                socklog.warning('No data received for 180 seconds, disconnecting')
                self._socket_disconnect()
            else:
                MON_DEVICE_UP.set(1)
                sockets_read = [self._socket]
                sockets_exc = [self._socket]

                if self._ts.last_frame_sent <= datetime.utcnow() - timedelta(seconds=1):
                    self._ts.last_frame_sent = datetime.utcnow()

                    # TODO change to request "the next" OID and enforce a limit here
                    # while i < 5:
                    #     next_frame = self._device_manager.next_frame_to_send()
                    #     MON_FRAMES_SENT.inc()
                    #     # done in next_frame: next_frame.in_flight = True
                    #     self._send_buf += next_frame.payload()
                    self._send_buf += self._device_manager.payloads()
                    # print(f'send_buf: {self._send_buf.hex()}')

                if len(self._send_buf) > 0:
                    sockets_write = [self._socket]

            try:
                sock_readable, sock_writable, sock_exceptions = select.select(
                    sockets_read, sockets_write, sockets_exc, 1)
            except KeyboardInterrupt:
                # this is reached when someone presses Ctrl+c at the terminal
                log.info('Got keyboard interrupt, shutting down')
                self._stop = True

            if self._socket in sock_exceptions:
                socklog.warning('Got socket exception from select(), disconnecting')
                self._socket_disconnect()
                sockets_read.clear()
                sockets_write.clear()
                sockets_exc.clear()
                continue

            if self._socket in sock_readable:
                self._handle_socket_read()

            if self._socket in sock_writable and self._connected:
                self._handle_socket_writable()

            if len(self._recv_buf) > 0:
                self._ts.last_data_received = datetime.utcnow()
                self._handle_received_data()

            if self._ts.last_influx_collect < datetime.utcnow() - timedelta(seconds=5):
                self._ts.last_influx_collect = datetime.utcnow()
                self._device_manager.collect_influx(self._influx)

            if self._ts.last_influx_flush < datetime.utcnow() - timedelta(seconds=5):
                self._ts.last_influx_flush = datetime.utcnow()
                self._influx.flush()

            if self._ts.last_mqtt_flush < datetime.utcnow() - timedelta(seconds=self._settings.mqtt.flush_interval_seconds):
                self._ts.last_mqtt_flush = datetime.utcnow()
                self._mqtt.flush()

        log.info('End main loop, shutting down')

        if HAVE_SYSTEMD:
            systemd.daemon.notify('STOPPING=1')
        self.cleanup()

    def _handle_received_data(self) -> None:
        while len(self._recv_buf) > 0:
            if not self._current_frame:
                self._current_frame = ReceiveFrame()
            try:
                consumed = self._current_frame.consume(self._recv_buf)
            except FrameCRCMismatch as exc:
                framelog.warning('CRC mismatch received, consumed %d bytes. Got %s but calculated %s',
                                 exc.consumed_bytes, exc.received_crc, exc.calculated_crc)
                self._current_frame = None
                consumed = exc.consumed_bytes
                MON_DECODE_ERROR.labels('crc').inc()
            except InvalidCommand as exc:
                framelog.warning('Invalid command 0x%x received, consumed %d bytes', exc.command, exc.consumed_bytes)
                self._current_frame = None
                consumed = exc.consumed_bytes
                MON_DECODE_ERROR.labels('command').inc()
            except FrameLengthExceeded as exc:
                framelog.warning('Frame consumed more than its advertised length, dropping')
                self._current_frame = None
                consumed = exc.consumed_bytes
                MON_DECODE_ERROR.labels('length').inc()

            if self._current_frame:
                if self._current_frame.complete():
                    framelog.debug('Frame complete, consumed %d bytes', consumed)
                    MON_FRAMES_RECEIVED.inc()
                    # frame complete
                    self._device_manager.on_frame(self._current_frame)
                    self._current_frame = None
                else:
                    framelog.debug('Frame consumed %d bytes, not complete. id: 0x%x, length: %d, command: %02x',
                                   consumed, self._current_frame.id, self._current_frame.frame_length,
                                   self._current_frame.command)

                    # filter frames that are broken, invalid or not of interest.

                    # test 1: unsupported frames (plant communication) and commands we're not interested in
                    if self._current_frame.command != Command._NONE:  # pylint: disable=protected-access
                        # filter frame types we are not interested in as early as possible
                        if Command.is_plant(self._current_frame.command):
                            framelog.warning('Received plant command %s (0x%x), not supporting these, aborting frame',
                                             self._current_frame.command.name, self._current_frame.command)
                            self._current_frame = None
                        elif self._current_frame.command not in (Command.RESPONSE, Command.LONG_RESPONSE):
                            framelog.warning('Received non-response command %s (0x%x), aborting frame',
                                             self._current_frame.command.name, self._current_frame.command)
                            self._current_frame = None
                    if self._current_frame and self._current_frame.id > 0:
                        try:
                            dtype = R.get_by_id(self._current_frame.id).response_data_type
                        except KeyError:
                            # test 2: OID has been parsed (>0) and is not in REGISTRY
                            framelog.warning('Incomplete frame has unknown oid 0x%X, aborting frame',
                                             self._current_frame.id)
                            self._current_frame = None
                        # test 3: try to find frames that are advertising extensive lengths for their type
                        else:
                            if dtype in (DataType.UINT8, DataType.INT8, DataType.UINT16, DataType.INT16,
                                         DataType.UINT32, DataType.INT32, DataType.FLOAT):
                                if self._current_frame.frame_length > 30:
                                    # max frame size for these types is 18 (PLANT frames with float). Give it some
                                    # leeway to account for previous InvalidCommands that only consumed two bytes.
                                    framelog.warning('Numbers frame is suspiciously long (length %d > 30), aborting '
                                                     'frame and skipping 2 bytes ahead',
                                                     self._current_frame.frame_length)
                                    self._current_frame = None
                                    consumed = 2
                                elif self._current_frame.consumed_bytes > 30:
                                    # frame has consumed way too much data
                                    framelog.warning('Numbers frame consumed suspicious amounts of data (%d > 30), '
                                                     'aborting frame and skipping 2 bytes ahead',
                                                     self._current_frame.consumed_bytes)
                                    self._current_frame = None
                                    consumed = 2
                            elif dtype == DataType.STRING and not Command.is_long(self._current_frame.command) and \
                                    self._current_frame.frame_length > 251:
                                # long replies are allowed to return more than 251 bytes
                                framelog.warning('String frame is suspiciously long (%s > 251 and not LONG command), '
                                                 'aborting frame and skipping 2 bytes ahead',
                                                 self._current_frame.frame_length)
                                self._current_frame = None
                                consumed = 2
                            # not checking for types we aren't using (yet): time series and event table
            self._recv_buf = self._recv_buf[consumed:]
