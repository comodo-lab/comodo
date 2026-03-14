FROM python:3.13-slim

WORKDIR /app

# Install Python deps
COPY ui/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r ./requirements.txt

# Copy app code
COPY ui /app
COPY utils/mqtt_clients.py /app/utils/mqtt_clients.py
COPY utils/interpolation.py /app/utils/interpolation.py
COPY utils/influx_query.py /app/utils/influx_query.py
COPY comodo.yaml /app/comodo.yaml

# Copy entrypoint that handles *_FILE secrets
COPY utils/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-u", "/app/app.py"]