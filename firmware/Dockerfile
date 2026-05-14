FROM python:3.13-slim

# Install required packages
COPY ./firmware/requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Set the app dir
WORKDIR /app

# Copy the application code

COPY ./firmware/main.py ./
COPY ./firmware/src ./src

# Copy the uitls
COPY utils ./utils

# Copy the tests
COPY ./firmware/tests ./tests

# Set the entry point
CMD ["python3", "-u", "main.py"]
