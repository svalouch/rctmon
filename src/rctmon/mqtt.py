'''
MQTT integration
'''

import paho.mqtt.client as mqtt
from .config import MqttConfig
from .event_processor import EventConsumer, Event
import logging
from ssl import VerifyMode

log = logging.getLogger(__name__)

class MqttClient(EventConsumer):

    is_connected: bool
    conf: MqttConfig
    topic_prefix: list
    mqtt_client: mqtt.Client

    def __init__(self, mqtt_config: MqttConfig):
        self.conf = mqtt_config
        self.topic_prefix = [self.conf.topic_prefix.strip("/")]
        if self.conf.enable:
            self.mqtt_client = self._connect()

    def _connect(self) -> mqtt.Client:
        log.info('Mqtt endpoint is at %s', self.conf.mqtt_host)
        mqtt_client = mqtt.Client(client_id=self.conf.client_name, callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        mqtt_client.enable_logger()

        if self.conf.auth_user and self.conf.auth_pass:
            mqtt_client.username_pw_set(self.conf.auth_user, self.conf.auth_pass)
        if self.conf.tls_enable:
            mqtt_client.tls_set(
                ca_certs=self.conf.tls_ca_cert,
                certfile=self.conf.tls_certfile,
                keyfile=self.conf.tls_keyfile,
                cert_reqs=VerifyMode.CERT_NONE if self.conf.tls_insecure else VerifyMode.CERT_REQUIRED
            )
            mqtt_client.tls_insecure_set(self.conf.tls_insecure)

        log.info("Connecting to mqtt server")
        mqtt_client.connect(host=self.conf.mqtt_host, port=self.conf.mqtt_port)
        mqtt_client.loop_start()

        return mqtt_client

    def _publish(self, topic, payload: str):
        log.debug("Publishing new value to " + topic)
        if self.mqtt_client.is_connected():
            self.mqtt_client.publish(topic=topic, payload=payload, retain=self.conf.mqtt_retain)
        else:
            log.warn("Not connected currently, skipping publish")

    def publish(self, topic: list, value):
        if self.conf.enable:
            topic = "/".join(self.topic_prefix + topic)
            if isinstance(value, float):
                value = "{:f}".format(value)
            self._publish(topic=topic, payload=value)
        else:
            log.debug("mqtt not enabled")

    def receive_event(self, event: Event):
        self.publish(list(event.key), event.payload)
