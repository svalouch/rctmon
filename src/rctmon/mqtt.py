'''
MQTT integration
'''

import paho.mqtt.client as mqtt
from .config import MqttConfig
from prometheus_client.core import REGISTRY, Sample, Metric
import logging


class MqttClient():

    def __init__(self, mqtt_config: MqttConfig):
        self.conf = mqtt_config
        self.mqtt_client = self._connect()

    def _connect(self) -> 'MqttClient':
        mqtt_client = mqtt.Client()
        if self.conf.user and self.conf.auth_pass:
            mqtt_client.username_pw_set(self.conf.auth_user, self.conf.auth_pass)
        if self.conf.tls_enable:
            mqtt_client.tls_set(
                self.conf.tls_ca_cert,
                self.conf.tls_certfile,
                self.conf.tls_keyfile
            )
            mqtt_client.tls_insecure_set(self.conf.tls_insecure)
        mqtt_client.connect(self.conf.mqtt_host, self.conf.mqtt_port)
        return mqtt_client

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
