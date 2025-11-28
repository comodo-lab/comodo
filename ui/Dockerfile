FROM python:3.13-slim
COPY ui/requirements.txt ./requirements.txt
RUN pip install -r ./requirements.txt
COPY ui /app
COPY utils/mqtt_clients.py /app/mqtt_clients.py
COPY utils/interpolation.py /app/interpolation.py
CMD ["python", "-u", "/app/app.py"]