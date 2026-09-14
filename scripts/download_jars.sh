#!/bin/bash

set -e

# Spark 3.5.8 official Docker image
SPARK_CONTAINER="spark-master"
SPARK_JARS_DIR="/opt/spark/jars"

# Define compatible JAR files
declare -A jars
jars=(
  # Hadoop S3A support
  ["hadoop-aws-3.3.4.jar"]="https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar"
  
  # AWS SDK required by Hadoop S3A
  ["aws-java-sdk-bundle-1.12.262.jar"]="https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar"

  # S3A dependency
  ["commons-pool2-2.11.1.jar"]="https://repo1.maven.org/maven2/org/apache/commons/commons-pool2/2.11.1/commons-pool2-2.11.1.jar"

  # Spark 3.5.8 Kafka connector
  ["spark-sql-kafka-0-10_2.12-3.5.8.jar"]="https://repo1.maven.org/maven2/org/apache/spark/spark-sql-kafka-0-10_2.12/3.5.8/spark-sql-kafka-0-10_2.12-3.5.8.jar"

  # Kafka token provider for Spark 3.5.8
  ["spark-token-provider-kafka-0-10_2.12-3.5.8.jar"]="https://repo1.maven.org/maven2/org/apache/spark/spark-token-provider-kafka-0-10_2.12/3.5.8/spark-token-provider-kafka-0-10_2.12-3.5.8.jar"
)

echo "Checking Spark container..."

if ! docker ps --format '{{.Names}}' | grep -q "^${SPARK_CONTAINER}$"; then
    echo "ERROR: Container '${SPARK_CONTAINER}' is not running."
    exit 1
fi

echo "Installing Spark dependencies..."

for jar in "${!jars[@]}"; do

    if docker exec "$SPARK_CONTAINER" test -f "${SPARK_JARS_DIR}/${jar}"; then
        echo "✓ $jar already exists."

    else
        echo "↓ Downloading $jar..."

        curl -fL -o "$jar" "${jars[$jar]}"

        echo "→ Copying $jar to Spark container..."

        docker cp "$jar" \
            "${SPARK_CONTAINER}:${SPARK_JARS_DIR}/"

        rm "$jar"

        echo "✓ $jar installed."
    fi

done

echo ""
echo "Spark dependencies installed successfully."