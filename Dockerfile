FROM apache/airflow:2.7.3-python3.11

USER root

COPY --from=ghcr.io/astral-sh/uv:0.12.13 /uv /uvx /bin/

WORKDIR /opt/airflow/project

COPY pyproject.toml uv.lock ./

RUN uv sync \
    --locked \
    --no-dev \
    --extra airflow \
    --no-install-project

ENV PATH="/opt/airflow/project/.venv/bin:$PATH"

USER airflow