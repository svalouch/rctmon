from dataclasses import dataclass
from typing import Union

@dataclass
class Event:
    key: tuple
    payload: Union[float, int, str]

class EventConsumer:

    def receive_event(self, event: Event):
        pass

class EventBroadcaster():

    consumers = set[EventConsumer]()

    @classmethod
    def register_consumer(cls, consumer: EventConsumer):
        cls.consumers.add(consumer)

    @classmethod
    def submit_event(cls, event: Event):
        for consumer in cls.consumers:
            consumer.receive_event(event)
