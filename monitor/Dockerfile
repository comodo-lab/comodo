FROM python:3.11-slim

COPY monitor/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /monitor
COPY utils/mqtt_clients.py      /monitor/utils/mqtt_clients.py
COPY utils/mqtt_validator.py    /monitor/utils/mqtt_validator.py
COPY utils/tests/mocks          /monitor/utils/tests/mocks
COPY schemas/mqtt_schema.yaml   /schemas/mqtt_schema.yaml

COPY monitor/monitor.py /monitor/monitor.py
COPY monitor/tests      /monitor/tests
COPY monitor/pytest.ini /monitor/pytest.ini

CMD ["python", "monitor.py"]
