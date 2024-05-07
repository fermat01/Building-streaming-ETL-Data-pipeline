#!/usr/bin/env bash
airflow db init
airflow users create -r Admin -u airflow01 -e admin@example.com -f admin -l user -p airflow01
airflow webserver