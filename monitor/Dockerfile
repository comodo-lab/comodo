FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY utils/mqtt_clients.py /app/utils/mqtt_clients.py
COPY monitor/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY monitor/*.py ./
CMD ["python", "app.py"]
