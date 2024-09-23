#!/bin/bash

# Get the directory of the current script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Navigate to the parent directory of the scripts folder
cd "$SCRIPT_DIR/.."

# Define the path to the Spark submit command
SPARK_SUBMIT="/opt/bitnami/spark/bin/spark-submit"

# Define the master
MASTER="local[2]"

# Define the JAR files
JARS="/opt/bitnami/spark/jars/hadoop-aws-3.2.0.jar,\
/opt/bitnami/spark/jars/aws-java-sdk-s3-1.11.375.jar,\
/opt/bitnami/spark/jars/commons-pool2-2.11.0.jar,\
/opt/bitnami/spark/jars/spark-streaming_2.12-3.3.0.jar,\
/opt/bitnami/spark/jars/kafka-clients-7.7.0-ce.jar,\
/opt/bitnami/spark/jars/spark-sql-kafka-0-10_2.12-3.3.0.jar,\
/opt/bitnami/spark/jars/spark-token-provider-kafka-0-10_2.12-3.3.0.jar"

# Define the Python script to run
SCRIPT="data_processing_spark.py"

# Copy the Python script from spark_app folder to the spark_master container
docker cp ./spark_app/$SCRIPT spark_master:/opt/bitnami/spark/

# Run the Spark submit command inside the spark_master container
docker exec spark_master $SPARK_SUBMIT --master $MASTER --jars $JARS /opt/bitnami/spark/$SCRIPT
