FROM python:3.13-slim

# Install required packages
COPY ./firmware/requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY ./firmware /app
WORKDIR /app

# Copy the uitls
COPY utils /app/utils

# Set the entry point
CMD ["python3", "-u", "main.py"]
