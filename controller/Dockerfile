FROM python:3.13-slim

COPY controller/requirements.txt ./requirements.txt
RUN pip install --no-cache -r requirements.txt

WORKDIR /controller
COPY utils/mqtt_clients.py      /controller/utils/mqtt_clients.py
COPY utils/mqtt_validator.py    /controller/utils/mqtt_validator.py
COPY utils/comodo_config.py     /controller/utils/comodo_config.py
COPY utils/interpolation.py     /controller/utils/interpolation.py
COPY utils/tests/mocks          /controller/utils/tests/mocks
COPY schemas/mqtt_schema.yaml   /schemas/mqtt_schema.yaml

COPY controller/controller.py   /controller/controller.py
COPY controller/src             /controller/src
COPY controller/tests           /controller/tests
COPY controller/pytest.ini      /controller/pytest.ini
COPY controller/README.md       /controller/README.md

CMD ["python", "-u", "controller.py"]
