#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$SCRIPT_DIR/.."

SPARK_CONTAINER="spark-master"
SPARK_HOME="/opt/spark"
MASTER="spark://spark-master:7077"
SCRIPT="analytics_spark.py"
CONTAINER_SCRIPT="${SPARK_HOME}/work-dir/spark_app/${SCRIPT}"
# Keep the analytics job's Ivy metadata separate from data-quality submissions.
IVY_CACHE="/tmp/.ivy2/analytics"
PACKAGES="org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.8,org.apache.kafka:kafka-clients:3.4.1,org.apache.hadoop:hadoop-aws:3.3.4"

if ! docker ps --format '{{.Names}}' | grep -q "^${SPARK_CONTAINER}$"; then
    echo "ERROR: ${SPARK_CONTAINER} is not running."
    echo "Start it with: docker compose up -d spark-master spark-worker-1 spark-worker-2"
    exit 1
fi

docker exec "${SPARK_CONTAINER}" test -f "${CONTAINER_SCRIPT}"
docker exec -u 0 "${SPARK_CONTAINER}" sh -c \
    "mkdir -p '${IVY_CACHE}/cache' '${IVY_CACHE}/jars' && chown -R spark:spark '${IVY_CACHE}'"

docker exec "${SPARK_CONTAINER}" \
    "${SPARK_HOME}/bin/spark-submit" \
    --master "${MASTER}" \
    --conf "spark.cores.max=2" \
    --conf "spark.jars.ivy=${IVY_CACHE}" \
    --packages "${PACKAGES}" \
    "${CONTAINER_SCRIPT}"
