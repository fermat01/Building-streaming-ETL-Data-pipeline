FROM apache/airflow:slim-latest-python3.9
USER root
ARG AIRFLOW_HOME=/opt/airflow
ADD app/  /opt/airflow/
COPY requirements.txt /
COPY scripts scripts
RUN chmod +x scripts
RUN chown -R airflow: ${AIRFLOW_HOME}
USER airflow
RUN pip install --upgrade pip
RUN  pip install --no-cache-dir -r /requirements.txt
USER ${AIRFLOW_UID}
