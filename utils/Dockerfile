FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY utils/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY utils/mqtt_clients.py ./utils/
COPY utils/mqtt_validator.py ./utils/
COPY utils/interpolation.py ./utils/
COPY utils/comodo_config.py ./utils/
COPY utils/tests ./utils/tests/
COPY utils/pytest.ini ./pytest.ini

