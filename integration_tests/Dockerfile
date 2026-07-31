FROM python:3.13-slim

# Install dependencies
COPY integration_tests/requirements.txt ./requirements.txt
RUN pip install --no-cache -r requirements.txt

WORKDIR /integration_tests
# Copy utils
COPY utils/comodo_config.py         /integration_tests/utils/comodo_config.py
COPY utils/tests/mocks              /integration_tests/utils/tests/mocks
# Copy integration tests
COPY integration_tests/runner.py    /integration_tests/runner.py

# Start integration tests
CMD ["pytest", "-x","-vv", "runner.py"]
