'''
MQTT integration
'''

import paho.mqtt.client as mqtt
from .config import MqttConfig
from prometheus_client.core import REGISTRY, Sample, Metric
import logging


class MqttClient():

    mqtt_host = None
    mqtt_port = None

    mqtt_client = None

    def __init__(self, mqtt_config: MqttConfig):
        self.mqtt_host = mqtt_config.mqtt_host
        self.mqtt_port = mqtt_config.mqtt_port

        self._connect()

    def _connect(self):
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.connect(self.mqtt_host, self.mqtt_port)

    def flush(self):
        """Flush all metrics from the registry to the mqtt server."""
        ignored_labels = ('inverter')  # ignore the generic inverter label

        metric: Metric = None
        sample: Sample = None

        for metric in REGISTRY.collect():
            if not metric.name.startswith("rctmon"):
                # ignore all additional non-functional metrics
                continue

            base_topic = metric.name.replace("_", "/")
            for sample in metric.samples:
                topic = base_topic
                for label in sample.labels.keys():
                    if label in ignored_labels:
                        continue
                    else:
                        segment = "{}_{}".format(label, sample.labels[label])
                        topic += "/" + segment

                self.mqtt_client.publish(
                    topic=topic, payload=sample.value, retain=True)
