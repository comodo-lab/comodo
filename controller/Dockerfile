FROM python:3.13-slim

WORKDIR /controller

# Setup python environment
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache -r requirements.txt

# Copy the code
COPY config/ /controller/config/
COPY schemas/ /controller/schemas/
COPY src/ /controller/src/
COPY tests/ /controller/tests/
COPY controller.py /controller/

CMD ["python", "-u", "controller.py"]
