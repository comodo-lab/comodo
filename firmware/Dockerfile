FROM python:3.13-slim

# Install dependencies
COPY firmware/requirements.txt ./requirements.txt
RUN pip install --no-cache -r requirements.txt

WORKDIR /firmware
# Copy utils and schemas
COPY utils/mqtt_clients.py      /firmware/utils/mqtt_clients.py
COPY utils/mqtt_validator.py    /firmware/utils/mqtt_validator.py
COPY utils/tests/mocks          /firmware/utils/tests/mocks
COPY schemas/mqtt_schema.yaml   /schemas/mqtt_schema.yaml
# Copy firmware code
COPY firmware/pytest.ini        /firmware/pytest.ini
COPY firmware/main.py           /firmware/main.py
COPY firmware/src               /firmware/src
# Copy firmware tests and readme
COPY firmware/tests             /firmware/tests
COPY firmware/README.md         /firmware/README.md

# Start firmware
CMD ["python3", "-u", "main.py"]
