
# Copyright 2021, Stefan Valouch (svalouch)
# SPDX-License-Identifier: GPL-3.0-only

'''
Managed Frame implementation.
'''

from datetime import datetime

from rctclient.frame import make_frame
from rctclient.registry import ObjectInfo
from rctclient.types import Command


class ManagedFrame:
    '''
    A frame with extra management infrastructure. A managed frame provides means to remember whether a frame has been
    sent but no answer received (in_flight), when it was last transmitted and so on.
    '''

    #: Information about the frame
    oinfo: ObjectInfo
    #: When the last transmit occured
    last_transmit: datetime
    #: When the last answer for this OID was received
    last_arrival: datetime
    #: Interval in seconds at which it should be queried
    interval: int
    #: Whether a request has been sent but no answer received yet
    in_flight: bool
    #: Whether the frame is used to gather inventory
    is_inventory: bool

    #: Pre-calculated frame body used for sending. Works for READ request only
    _payload: bytes

    def __init__(self, oinfo: ObjectInfo, interval: int, last_transmit: datetime = datetime.min,
                 last_arrival: datetime = datetime.min, in_flight: bool = False, is_inventory: bool = False) -> None:
        self.oinfo = oinfo
        self.last_transmit = last_transmit
        self.last_arrival = last_arrival
        self.interval = interval
        self.in_flight = in_flight
        self.is_inventory = is_inventory

        self._payload = make_frame(Command.READ, self.oinfo.object_id)

    def __repr__(self) -> str:
        return f'<ManagedFrame(message_id={self.oinfo.object_id:08X}, id=0x{self.oinfo.index:08X}, ' \
            f'name="{self.oinfo.name}", interval={self.interval}, in_flight={self.in_flight})>'

    def __lt__(self, other: 'ManagedFrame') -> bool:
        '''
        Allows sorting by last_transmit time
        '''
        return self.last_transmit < other.last_transmit

    @property
    def payload(self) -> bytes:
        '''
        Returns the byte sequence to request the frame (read command). This is ready to be put on the wire as-is.
        '''
        return self._payload
