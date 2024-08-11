#!/bin/bash

# Define the Docker container name
CONTAINER_NAME="spark_master"

# Define the path to the Spark submit command inside the container
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

# Run the Spark submit command inside the Docker container
docker exec -it $CONTAINER_NAME $SPARK_SUBMIT --master $MASTER --jars $JARS $SCRIPT
