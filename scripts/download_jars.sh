#!/bin/bash

# Define the list of JAR files and their URLs
declare -A jars
jars=(
  ["hadoop-aws-3.2.0.jar"]="https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.2.0/hadoop-aws-3.2.0.jar"
  ["aws-java-sdk-s3-1.11.375.jar"]="https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-s3/1.11.375/aws-java-sdk-s3-1.11.375.jar"
  ["commons-pool2-2.11.0.jar"]="https://repo1.maven.org/maven2/org/apache/commons/commons-pool2/2.11.0/commons-pool2-2.11.0.jar"
  ["spark-streaming_2.12-3.3.0.jar"]="https://repo1.maven.org/maven2/org/apache/spark/spark-streaming_2.12/3.3.0/spark-streaming_2.12-3.3.0.jar"
  ["kafka-clients-7.7.0-ce.jar"]="https://packages.confluent.io/maven/org/apache/kafka/kafka-clients/7.7.0-ce/kafka-clients-7.7.0-ce.jar"
  ["spark-sql-kafka-0-10_2.12-3.3.0.jar"]="https://repo1.maven.org/maven2/org/apache/spark/spark-sql-kafka-0-10_2.12/3.3.0/spark-sql-kafka-0-10_2.12-3.3.0.jar"
  ["spark-token-provider-kafka-0-10_2.12-3.3.0.jar"]="https://repo1.maven.org/maven2/org/apache/spark/spark-token-provider-kafka-0-10_2.12/3.3.0/spark-token-provider-kafka-0-10_2.12-3.3.0.jar"
)

# Loop through each JAR file
for jar in "${!jars[@]}"; do
  # Check if the JAR file does not exist in the spark_master container's jars folder
  if ! docker exec spark_master test -f "/opt/bitnami/spark/jars/$jar"; then
    echo "Downloading $jar..."
    # Download the JAR file using curl
    curl -O "${jars[$jar]}"
    # Copy the downloaded JAR file to the spark_master container's jars folder
    docker cp "$jar" spark_master:/opt/bitnami/spark/jars/
    # Remove the local copy of the JAR file
    rm "$jar"
  else
    echo "$jar already exists in the spark_master container."
  fi
done