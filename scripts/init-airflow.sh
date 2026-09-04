#!/usr/bin/env bash

set -euo pipefail

: "${AIRFLOW_ADMIN_USERNAME:?AIRFLOW_ADMIN_USERNAME is required}"
: "${AIRFLOW_ADMIN_EMAIL:?AIRFLOW_ADMIN_EMAIL is required}"
: "${AIRFLOW_ADMIN_FIRSTNAME:?AIRFLOW_ADMIN_FIRSTNAME is required}"
: "${AIRFLOW_ADMIN_LASTNAME:?AIRFLOW_ADMIN_LASTNAME is required}"
: "${AIRFLOW_ADMIN_PASSWORD:?AIRFLOW_ADMIN_PASSWORD is required}"

echo "=============================================="
echo "Initializing Airflow database"
echo "=============================================="

airflow db migrate

echo ""
echo "Creating Airflow admin user if needed..."

if airflow users list --output json | grep -q '"username": "'"${AIRFLOW_ADMIN_USERNAME}"'"'; then
    echo "Airflow admin user already exists."
else
    airflow users create \
        --role Admin \
        --username "${AIRFLOW_ADMIN_USERNAME}" \
        --email "${AIRFLOW_ADMIN_EMAIL}" \
        --firstname "${AIRFLOW_ADMIN_FIRSTNAME}" \
        --lastname "${AIRFLOW_ADMIN_LASTNAME}" \
        --password "${AIRFLOW_ADMIN_PASSWORD}"
fi

echo ""
echo "Airflow initialization completed successfully."