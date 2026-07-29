FROM python:3.11-slim

COPY utils/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /utils
COPY utils/__init__.py          /utils/__init__.py
COPY utils/comodo_config.py     /utils/comodo_config.py
COPY utils/interpolation.py     /utils/interpolation.py
COPY utils/mqtt_clients.py      /utils/mqtt_clients.py
COPY utils/mqtt_validator.py    /utils/mqtt_validator.py
COPY utils/pytest.ini           /utils/pytest.ini
COPY utils/tests                /utils/tests
