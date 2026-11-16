FROM eclipse-mosquitto:2

COPY ./mqtt_probe/probe.sh /probe.sh

HEALTHCHECK --start-period=3s --start-interval=1s --interval=5s --timeout=5s --retries=5 \
    CMD ["/bin/sh", "/probe.sh"]

CMD ["sleep", "infinity"]
