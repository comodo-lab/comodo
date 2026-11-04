FROM python:3.14-slim

# Install dependencies
COPY monitor/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /monitor
# Copy utils and schemas
COPY utils/mqtt_clients.py      /monitor/utils/mqtt_clients.py
COPY utils/mqtt_validator.py    /monitor/utils/mqtt_validator.py
COPY utils/tests/mocks          /monitor/utils/tests/mocks
COPY schemas/mqtt_schema.yaml   /schemas/mqtt_schema.yaml
# Copy monitor code
COPY monitor/pytest.ini         /monitor/pytest.ini
COPY monitor/monitor.py         /monitor/monitor.py
# Copy monitor tests and readme
COPY monitor/tests              /monitor/tests
COPY monitor/README.md          /monitor/README.md

# Start monitor
CMD ["python", "monitor.py"]
