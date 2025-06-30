FROM python:3.13-slim

WORKDIR /controller
ENV PYTHONPATH=/controller

# Setup python environment
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache -r requirements.txt

# Copy the code
COPY config/ /controller/config/
COPY schemas/ /controller/schemas/
COPY src/ /controller/src/
COPY tests/ /controller/tests/
COPY controller.py /controller/

# TEMP: copy copy manually modified pytest-mqtt
COPY pytest-mqtt /pytest-mqtt
RUN pip install /pytest-mqtt

# Run the controller
CMD ["python", "-u", "controller.py"]
