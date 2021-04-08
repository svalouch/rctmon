
# Copyright 2021, Stefan Valouch (svalouch)
# SPDX-License-Identifier: GPL-3.0-only

'''
Logging configuration.
'''

import logging.config
from typing import Dict

DEFAULT_CONFIG = {
    'version': 1,
    'formatters': {
        'simple': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
            'level': 'INFO',
            'stream': 'ext://sys.stdout',
        },
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console'],

    },
    # 'loggers': {
    #     'rctmon.daemon': {
    #         'handlers': ['console'],
    #     },
    # },
}


def setup_logging(config: Dict = None, debug: bool = False, frame_debug: bool = False) -> None:
    '''
    Basic logging setup.

    :param debug: If set overwrites all logging levels to DEBUG (except frame debugging).
    :param frame_debug: Whether to set rctclient frame debugging to DEBUG. If this and ``debug`` both are set sets the
       frame debug level to DEBUG.
    :param config: Optional config dict for use with ``logging.config.dictConfig``.
    '''
    if config is None:
        logging.config.dictConfig(DEFAULT_CONFIG)
    else:
        logging.config.dictConfig(config)

    if debug:
        # set the handler to DEBUG, or they'll filter the DEBUG messages from loggers
        for handler in logging.root.handlers:
            handler.setLevel(logging.DEBUG)
        logging.root.setLevel(logging.DEBUG)

        if not frame_debug:
            logging.getLogger('rctclient.frame.ReceiveFrame').setLevel(logging.INFO)
