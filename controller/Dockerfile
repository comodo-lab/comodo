FROM python:3.13-slim

# Setup python environment
COPY controller/requirements.txt ./requirements.txt
RUN pip install --no-cache -r requirements.txt

# Copy the code
COPY controller /controller
WORKDIR /controller

# TEMP: copy manually modified pytest-mqtt
RUN pip install /controller/pytest-mqtt

# Run the controller
CMD ["python", "-u", "controller.py"]
