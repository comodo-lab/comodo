FROM python:3.13-slim
RUN pip install paho-mqtt pytest pytest-timeout pytest-order
COPY runner.py /app/runner.py
CMD ["pytest", "-vv", "/app/runner.py"]
