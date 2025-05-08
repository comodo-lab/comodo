FROM python:3.9

WORKDIR /controller

# Setup poetry
RUN pip install poetry
COPY poetry.lock pyproject.toml /controller/
RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi

# Copy the code
COPY config/ /controller/config/
COPY schemas/ /controller/schemas/
COPY src/ /controller/src/
COPY tests/ /controller/tests/
COPY controller.py /controller/

CMD ["python", "controller.py"]
