FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY samplenator_cli/ samplenator_cli/

RUN pip install --no-cache-dir .

ENTRYPOINT ["samplenator-cli"]
