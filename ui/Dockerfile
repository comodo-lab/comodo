FROM python:3.13-slim

# Install dependencies
COPY ui/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r ./requirements.txt

WORKDIR /ui
# Copy utils
COPY utils/mqtt_clients.py  /ui/utils/mqtt_clients.py
COPY utils/interpolation.py /ui/utils/interpolation.py
COPY utils/influx_query.py  /ui/utils/influx_query.py
# Copy ui code
COPY ui /ui
# Copy ui tests and readme

# Copy entrypoint that handles *_FILE secrets
COPY ui/entrypoint.sh       /entrypoint.sh
RUN chmod +x /entrypoint.sh
# Start ui
ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-u", "/ui/app.py"]
