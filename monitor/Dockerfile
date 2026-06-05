FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY utils/mqtt_clients.py /app/utils/mqtt_clients.py
COPY utils/message_spec.py /app/utils/message_spec.py
COPY utils/tests /app/utils/tests
COPY monitor/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY monitor/*.py ./
COPY monitor/tests /app/tests
COPY monitor/pytest.ini /app/pytest.ini
COPY messageSpec.yaml /app/asyncapi.yaml
CMD ["python", "app.py"]
