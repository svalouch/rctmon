'''
MQTT integration
'''

from time import sleep
import paho.mqtt.client as mqtt
from .config import MqttConfig
from prometheus_client.core import REGISTRY, Sample, Metric
import logging

log = logging.getLogger(__name__)


class MqttClient():

    is_connected: bool
    conf: MqttConfig
    topic_prefix: str
    mqtt_client: mqtt.Client

    def __init__(self, mqtt_config: MqttConfig):
        self.conf = mqtt_config
        self.is_connected = False
        self.topic_prefix = [self.conf.topic_prefix.strip("/")]
        self.mqtt_client = self._setup_client()
        self._connect()

    def _setup_client(self) -> mqtt.Client:
        mqtt_client = mqtt.Client(client_id=self.conf.client_name)
        mqtt_client.enable_logger()
        mqtt_client.on_connect = self.__cb_on_connect
        mqtt_client.on_disconnect = self.__cb_on_disconnect

        if self.conf.auth_user and self.conf.auth_pass:
            mqtt_client.username_pw_set(
                self.conf.auth_user, self.conf.auth_pass)
        if self.conf.tls_enable:
            mqtt_client.tls_set(
                self.conf.tls_ca_cert,
                self.conf.tls_certfile,
                self.conf.tls_keyfile
            )
            mqtt_client.tls_insecure_set(self.conf.tls_insecure)

        mqtt_client.loop_start()

        return mqtt_client

    def _connect(self):
        log.info("MQTT reconnecting")
        if self.is_connected:
            log.warn("MQTT already connected, skipping reconnect")
        else:
            self.mqtt_client.connect(self.conf.mqtt_host, self.conf.mqtt_port)

    def __cb_on_connect(self, mqttc, obj, flags, rc):
        log.debug("Received onConnect callback")
        if rc == 0:
            log.info("MQTT connection established")
            self.is_connected = True
        else:
            log.warning("Couldn't connect to mqtt because of rc %d", rc)

    def __cb_on_disconnect(self, mqttc, obj, rc):
        log.debug("Received onDisconnect callback")
        self.is_connected = False

    def publish(self, topic, payload):
        if self.is_connected:
            self.mqtt_client.publish(
                topic=topic, payload=payload, retain=self.conf.mqtt_retain)
        else:
            log.warn("MQTT not connected, skipping publishing")

    def flush(self):
        """Flush all metrics from the registry to the mqtt server."""
        ignored_labels = ('inverter')  # ignore the generic inverter label

        log.debug("Flushing metrics")
        if not self.is_connected:
            self._connect()

        metric: Metric = None
        sample: Sample = None

        for metric in REGISTRY.collect():
            if not metric.name.startswith("rctmon"):
                # ignore all additional non-functional metrics
                continue

            base_topic = "/".join(self.topic_prefix +
                                  (metric.name.split("_")[1:]))
            for sample in metric.samples:
                topic = base_topic
                for label in sample.labels.keys():
                    if label in ignored_labels:
                        continue
                    else:
                        segment = "{}_{}".format(label, sample.labels[label])
                        topic += "/" + segment

                self.publish(topic=topic, payload=sample.value)
