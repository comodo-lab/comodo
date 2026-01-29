FROM eclipse-mosquitto:2

HEALTHCHECK --interval=1s --timeout=10s --retries=10 \
    CMD exit $(cat /tmp/mqtt-health 2>/dev/null || echo 1)

COPY ./mqtt_probe/probe.sh /probe.sh

CMD ["/bin/sh", "/probe.sh"]
