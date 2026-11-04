FROM python:3.14-slim

# Install dependencies
COPY /setpoint_controller/requirements.txt ./requirements.txt
RUN pip install --no-cache -r requirements.txt

WORKDIR /setpoint_controller
# Copy utils and schemas
COPY utils/mqtt_clients.py                          /setpoint_controller/utils/mqtt_clients.py
COPY utils/mqtt_validator.py                        /setpoint_controller/utils/mqtt_validator.py
COPY utils/tests/mocks                              /setpoint_controller/utils/tests/mocks
COPY schemas/mqtt_schema.yaml                       /schemas/mqtt_schema.yaml
# Copy setpoint_controller code
COPY setpoint_controller/pytest.ini                 /setpoint_controller/
COPY setpoint_controller/setpoint_controller.py     /setpoint_controller/
COPY setpoint_controller/src                        /setpoint_controller/src
# Copy setpoint_controller tests and readme
COPY setpoint_controller/tests                      /setpoint_controller/tests
COPY setpoint_controller/README.md                  /setpoint_controller/

# Start setpoint_controller
CMD ["python", "-u", "setpoint_controller.py"]
