FROM python:3.13-slim

# Install dependencies
COPY ui/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r ./requirements.txt

WORKDIR /ui
# Copy utils
COPY utils/mqtt_clients.py  /ui/utils/mqtt_clients.py
COPY utils/comodo_config.py /ui/utils/comodo_config.py
COPY utils/interpolation.py /ui/utils/interpolation.py
COPY utils/influx_query.py  /ui/utils/influx_query.py
COPY setpoint_controller/src/pid.py /ui/utils/pid.py
# Copy ui code
COPY ui/pytest.ini          /ui/pytest.ini
COPY ui/app.py              /ui/app.py
COPY ui/src                 /ui/src
# Copy ui tests and readme
COPY ui/tests               /ui/tests
COPY ui/README.md           /ui/README.md

# Start ui
CMD ["python", "-u", "/ui/app.py"]
