FROM python:3.13-slim

COPY controller/requirements.txt ./requirements.txt
RUN pip install --no-cache -r requirements.txt

WORKDIR /controller
COPY controller /controller
COPY utils/mqtt_clients.py /controller/utils/mqtt_clients.py
COPY utils/interpolation.py /controller/utils/interpolation.py

# Install envsubst
RUN apt-get update && apt-get install -y gettext-base

# Copy entrypoint
COPY controller/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-u", "controller.py"]