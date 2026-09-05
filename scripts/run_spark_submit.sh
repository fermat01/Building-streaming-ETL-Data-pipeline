#!/bin/bash

set -e

# ============================================================
# Spark Structured Streaming - Distributed Execution
# ============================================================

# Get the directory of the current script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"

# Navigate to project root
cd "$SCRIPT_DIR/.."

# ============================================================
# Spark configuration
# ============================================================

SPARK_CONTAINER="spark-master"
SPARK_CONTAINERS=(spark-master spark-worker-1 spark-worker-2)
SPARK_HOME="/opt/spark"
# Keep the data-quality job's Ivy metadata separate from analytics submissions.
IVY_CACHE="/tmp/.ivy2/data-quality"
KAFKA_CLIENT_VERSION="3.4.1"
KAFKA_CLIENT_JAR="${SPARK_HOME}/jars/kafka-clients-${KAFKA_CLIENT_VERSION}.jar"
KAFKA_CLIENT_URL="https://repo1.maven.org/maven2/org/apache/kafka/kafka-clients/${KAFKA_CLIENT_VERSION}/kafka-clients-${KAFKA_CLIENT_VERSION}.jar"

SPARK_SUBMIT="${SPARK_HOME}/bin/spark-submit"

# Distributed Spark Standalone cluster
MASTER="spark://spark-master:7077"

# ============================================================
# Spark application
# ============================================================

SCRIPT="data_processing_spark.py"

CONTAINER_SCRIPT="${SPARK_HOME}/work-dir/spark_app/${SCRIPT}"
CONTAINER_CODEC="${SPARK_HOME}/work-dir/spark_app/schema_codec.py"
CONTAINER_SCHEMA="${SPARK_HOME}/work-dir/schemas/user_event.avsc"

# ============================================================
# Dependencies
# ============================================================

# Spark 3.5.8 Kafka connector
# Hadoop AWS 3.3.4 provides S3A support for MinIO/S3.
PACKAGES="org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.8,org.apache.kafka:kafka-clients:3.4.1,org.apache.hadoop:hadoop-aws:3.3.4"

# ============================================================
# Display configuration
# ============================================================

echo "=============================================="
echo "Spark Structured Streaming"
echo "=============================================="
echo "Spark container : ${SPARK_CONTAINER}"
echo "Spark home      : ${SPARK_HOME}"
echo "Spark submit    : ${SPARK_SUBMIT}"
echo "Master          : ${MASTER}"
echo "Application     : ${CONTAINER_SCRIPT}"
echo "Packages        : ${PACKAGES}"
echo "Ivy cache       : ${IVY_CACHE}"
echo "Kafka client    : ${KAFKA_CLIENT_JAR}"
echo "=============================================="
echo ""

# ============================================================
# Verify Spark container
# ============================================================

if ! docker ps --format '{{.Names}}' | grep -q "^${SPARK_CONTAINER}$"; then
    echo "ERROR: ${SPARK_CONTAINER} is not running."
    echo ""
    echo "Start the Spark cluster with:"
    echo "  docker compose up -d spark-master spark-worker-1 spark-worker-2"
    exit 1
fi

# ============================================================
# Verify Spark Master
# ============================================================

echo "Checking Spark Master..."

if ! docker exec "${SPARK_CONTAINER}" \
    curl -sf http://spark-master:8080/json/ \
    > /dev/null 2>&1; then

    echo "WARNING: Spark Master Web UI is not responding yet."
    echo "Waiting for Spark Master..."

    sleep 5
fi

# ============================================================
# Verify application exists
# ============================================================

if ! docker exec "${SPARK_CONTAINER}" \
    test -f "${CONTAINER_SCRIPT}"; then

    echo "ERROR: Spark application not found:"
    echo "  ${CONTAINER_SCRIPT}"
    echo ""
    echo "Make sure docker-compose mounts:"
    echo "  ./spark_app:/opt/spark/work-dir/spark_app:ro"
    exit 1
fi

if ! docker exec "${SPARK_CONTAINER}" \
    test -f "${CONTAINER_CODEC}" || ! docker exec "${SPARK_CONTAINER}" \
    test -f "${CONTAINER_SCHEMA}"; then
    echo "ERROR: Spark schema decoder or canonical schema is not mounted."
    exit 1
fi

# A second data-quality application cannot share the processed/quarantine
# checkpoints. Refuse duplicate submissions before they can corrupt progress.
ACTIVE_DATA_QUALITY_APPS=$(curl -fsS http://localhost:8085/json/ | python3 -c '
import json
import sys

payload = json.load(sys.stdin)
apps = payload.get("activeapps", payload.get("activeApps", []))
for app in apps:
    if app.get("name") == "SparkStructuredStreamingDataQuality":
        print("{} ({})".format(app.get("id"), app.get("state")))
' )
if [ -n "${ACTIVE_DATA_QUALITY_APPS}" ]; then
    echo "ERROR: A data-quality Spark application is already active:"
    echo "${ACTIVE_DATA_QUALITY_APPS}"
    echo "Stop the existing application before retrying this command."
    exit 1
fi

# ============================================================
# Submit distributed Spark application
# ============================================================

echo ""
echo "Submitting Spark application..."
echo ""

for container in "${SPARK_CONTAINERS[@]}"; do
    docker exec -u 0 "${container}" mkdir -p "${SPARK_HOME}/jars"
    docker exec -u 0 "${container}" sh -c \
        "if [ ! -f '${KAFKA_CLIENT_JAR}' ]; then curl -fsSL '${KAFKA_CLIENT_URL}' -o '${KAFKA_CLIENT_JAR}'; fi"
done

docker exec -u 0 "${SPARK_CONTAINER}" sh -c \
    "mkdir -p '${IVY_CACHE}/cache' '${IVY_CACHE}/jars' && chown -R spark:spark '${IVY_CACHE}'"

docker exec "${SPARK_CONTAINER}" \
    "${SPARK_SUBMIT}" \
    --master "${MASTER}" \
    --conf "spark.cores.max=2" \
    --conf "spark.jars.ivy=${IVY_CACHE}" \
    --jars "${KAFKA_CLIENT_JAR}" \
    --packages "${PACKAGES}" \
    --py-files "${CONTAINER_CODEC}" \
    --files "${CONTAINER_SCHEMA}" \
    "${CONTAINER_SCRIPT}"

echo ""
echo "=============================================="
echo "Spark job submitted successfully."
echo "=============================================="