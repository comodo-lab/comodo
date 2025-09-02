FROM python:3.13-slim

# Setup python environment
COPY controller/requirements.txt ./requirements.txt
RUN pip install --no-cache -r requirements.txt

# Copy the controller
WORKDIR /controller
COPY controller /controller

# Copy the utils
COPY utils/mqtt_clients.py /controller
COPY utils/interpolation.py /controller

# Load .env file from main and into local environment
COPY .env .env
RUN source .env

# Substitute env variables into the config
RUN apk add envsubst
RUN envsubst < /controller/config/config.json.template > /controller/config/config.json

# TEMP: copy copy manually modified pytest-mqtt
COPY utils/pytest-mqtt /pytest-mqtt
# RUN pip install /pytest-mqtt

# Run the controller
CMD ["python", "-u", "controller.py"]
