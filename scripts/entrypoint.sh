#!/usr/bin/env bash
airflow db init
airflow db upgrade 
airflow users create -r Admin -u airflow01 -p airflow01 -e data_eng@gmail.com -f Vianney -l Vianney
airflow scheduler & airflow webserver 
