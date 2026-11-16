FROM python:3.14-slim

# Install dependencies
COPY integration_tests/requirements.txt ./requirements.txt
RUN pip install --no-cache -r requirements.txt

WORKDIR /integration_tests
# Copy utils
COPY utils/comodo_config.py                 /integration_tests/utils/comodo_config.py
COPY utils/tests/mocks                      /integration_tests/utils/tests/mocks
# Copy integration tests and readme
COPY integration_tests/integration_tests.py /integration_tests/integration_tests.py
COPY integration_tests/conftest.py          /integration_tests/conftest.py
COPY integration_tests/README.md            /integration_tests/README.md

# Start integration tests
CMD ["pytest", "-x","-vv", "integration_tests.py"]
