
# Copyright 2021, Stefan Valouch (svalouch)
# SPDX-License-Identifier: GPL-3.0-only

'''
Command Line Interface
'''

# pylint: disable=import-outside-toplevel

import sys

import click
import yaml

from .config import RctMonConfig
from .logging import setup_logging


@click.group()
@click.pass_context
@click.option('-d', '--debug', is_flag=True, default=False, help='Enable debug output')
@click.option('--frame-debug', is_flag=True, default=False, help='Enable frame debugging (requires --debug)')
@click.option('-c', '--config', type=click.File(mode='r', lazy=False), default='/etc/rctmon.yml',
              help='Configuration file')
def cli(ctx, debug: bool, frame_debug: bool, config) -> None:
    '''
    Entry point. Set general options here.
    '''
    ctx.ensure_object(dict)
    ctx.obj['DEBUG'] = debug

    config_data = yaml.safe_load(config.read())
    ctx.obj['CONFIG'] = config_data

    try:
        setup_logging(config_data['logging'] if 'logging' in config_data else None, debug, frame_debug)
    except (ValueError, AttributeError) as exc:
        print(f'Could not load logging configuration: {str(exc)}', file=sys.stderr)
        sys.exit(1)


@cli.command('daemon')
@click.pass_context
def daemon(ctx) -> None:
    '''
    Start the monitoring daemon.
    '''

    settings = RctMonConfig(**ctx.obj['CONFIG'])

    from .daemon import Daemon
    Daemon(settings).run()
