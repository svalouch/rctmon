
# Copyright 2021, Stefan Valouch (svalouch)
# SPDX-License-Identifier: GPL-3.0-only

'''
Definitions and functions for basic prometheus monitoring.
'''

from http.server import ThreadingHTTPServer
from threading import Thread
from urllib.parse import urlparse
from prometheus_client import Counter, Gauge, Info, MetricsHandler

from .config import PrometheusConfig


MON_BYTES_RECEIVED = Counter('rctmon_bytes_received', 'Amount of bytes received since the start of the application')
MON_BYTES_SENT = Counter('rctmon_bytes_sent', 'Amount of bytes sent since the start of the application')
MON_DECODE_ERROR = Counter('rctmon_decode_error', 'Amount of times the decoding of data failed', ['kind'])
MON_DEVICE_UP = Gauge('rctmon_device_up', 'Whether the connection to the device is established')
# MON_FRAMES_IN_FLIGHT = Gauge('rctmon_frames_in_flight', 'Amount of frames sent but not yet received', ['kind'])
MON_FRAMES_LOST = Counter('rctmon_frames_lost', 'Amount of frames that were sent but not received in time', ['kind'])
MON_FRAMES_RECEIVED = Counter('rctmon_frames_received', 'Amount of frames received since the start of the application')
MON_FRAMES_SENT = Counter('rctmon_frames_sent', 'Amount of frames sent since the start of the application')
MON_INFO = Info('rctmon', 'Information about the application')


class MainHandler(MetricsHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path == '/':
                self.send_error(404)
                # self.send_html_main()
            elif path == '/metrics':
                super().do_GET()
            else:
                self.send_error(404)
        except Exception:  # pylint: disable=broad-except
            self.send_error(500, 'Internal error')

    def send_html_main(self) -> None:
        '''
        Renders a basic main page
        '''
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(b'<html><head><title>RCTMon</title></head><body><h1>RCTMon</h1></body></html>')


def setup_monitoring(config: PrometheusConfig) -> None:
    '''
    Starts a basic HTTP handler in a thread, serving the metrics.
    '''

    httpd = ThreadingHTTPServer((config.bind_address, config.bind_port), MainHandler)
    thr = Thread(target=httpd.serve_forever)
    thr.daemon = True
    thr.start()
