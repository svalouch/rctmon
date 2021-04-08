
# Copyright 2021, Stefan Valouch (svalouch)
# SPDX-License-Identifier: GPL-3.0-only

'''
Utility functions.
'''

from datetime import datetime, timedelta
from typing import Any, Callable, Type, TypeVar


OidHandler = Callable[[int, Any], None]

# for ensure_type
TargetType = TypeVar('TargetType')


def ensure_type(value: Any, typ: Type[TargetType]) -> TargetType:
    '''
    Raises a ``TypeError`` if ``value`` is not of the given type and returns the value if it is.
    '''
    if not isinstance(value, typ):
        raise TypeError('Input type does not match expected type')
    return value


def datetime_range(start: datetime, end: datetime, delta: timedelta):
    '''
    Generator yielding datetime object between `start` and `end` with `delta` increments.

    >>> for d in datetime_range(start=datetime(year=2020, month=6, day=10, hour=11),
    ...                         end=datetime(year=2020, month=6, day=10, hour=12),
    ...                         delta=timedelta(minutes=15)):
    ...     print(d)
    ...
    2020-06-10 11:00:00
    2020-06-10 11:15:00
    2020-06-10 11:30:00
    2020-06-10 11:45:00
    '''
    current = start
    while current < end:
        yield current
        current += delta
