FROM python:3.13-slim


COPY integration_tests/requirements.txt ./requirements.txt
RUN pip install --no-cache -r requirements.txt

WORKDIR /integration_tests

COPY utils/comodo_config.py     /integration_tests/utils/comodo_config.py
COPY utils/tests/mocks          /integration_tests/utils/tests/mocks

COPY integration_tests/runner.py    /integration_tests/runner.py

CMD ["pytest", "-x","-vv", "runner.py"]
