FROM apache/airflow:2.7.3
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    vim \
    && apt-get autoremove -yqq --purge \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
USER airflow
RUN pip install --upgrade pip
COPY requirements.txt /
RUN  pip install --no-cache-dir -r /requirements.txt
USER airflow