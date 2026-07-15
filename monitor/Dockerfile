FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY utils/mqtt_clients.py /app/utils/mqtt_clients.py
COPY utils/mqtt_validator.py /app/utils/mqtt_validator.py
COPY utils/tests /app/utils/tests
COPY monitor/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY monitor/*.py ./
COPY monitor/tests /app/tests
COPY monitor/pytest.ini /app/pytest.ini
CMD ["python", "app.py"]
