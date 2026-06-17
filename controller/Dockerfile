FROM python:3.13-slim

COPY controller/requirements.txt ./requirements.txt
RUN pip install --no-cache -r requirements.txt

WORKDIR /controller
COPY controller/controller.py /controller/controller.py
COPY controller/src /controller/src
COPY controller/tests /controller/tests
COPY controller/pytest.ini /controller/pytest.ini
COPY controller/README.md /controller/README.md
COPY utils/mqtt_clients.py /controller/utils/mqtt_clients.py
COPY utils/mqtt_validator.py /controller/utils/mqtt_validator.py
COPY utils/tests/mocks/mock_mqtt_clients.py /controller/utils/tests/mocks/mock_mqtt_clients.py
COPY utils/interpolation.py /controller/utils/interpolation.py

CMD ["python", "-u", "controller.py"]
