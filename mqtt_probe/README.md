# MQTT Probe

The mqtt probe is used as a lightweight check to make sure the credentials and connection to the MQTT broker are working properly.

The service is used in each of the compose files (other than the mqtt broker) to provide a health check for the MQTT broker connection.

It periodically attempts to connect to the broker using the provided credentials and reports its status via a health check.
