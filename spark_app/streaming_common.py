import logging
import os
from typing import Optional

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import col
from pyspark.sql.types import (
    DoubleType,
    IntegerType,
    StringType,
    StructField,
    StructType,
)

logger = logging.getLogger(__name__)

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD")
KAFKA_BOOTSTRAP_SERVERS = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS",
    "broker-1:9092,broker-2:9093,broker-3:9094",
)
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "streaming-topic")
PROCESSED_PATH = os.getenv("MINIO_OUTPUT_PATH", "s3a://streaming-data/processed/")
QUARANTINE_PATH = os.getenv("MINIO_QUARANTINE_PATH", "s3a://streaming-data/quarantine/")
ANALYTICS_PATH = os.getenv("MINIO_ANALYTICS_PATH", "s3a://streaming-data/analytics/")
CHECKPOINT_ROOT = os.getenv(
    "SPARK_CHECKPOINT_PATH", "s3a://streaming-data/checkpoints/"
).rstrip("/")


def user_schema() -> StructType:
    """Schema for the JSON event produced by the Airflow ingestion DAG."""
    return StructType(
        [
            StructField("event_id", StringType(), True),
            StructField("full_name", StringType(), True),
            StructField("gender", StringType(), True),
            StructField("age", IntegerType(), True),
            StructField("address", StringType(), True),
            StructField("city", StringType(), True),
            StructField("country", StringType(), True),
            StructField("email", StringType(), True),
            StructField("phone", StringType(), True),
            StructField("username", StringType(), True),
            StructField("registered_date", StringType(), True),
            StructField("ingested_at", StringType(), True),
            StructField("zip", StringType(), True),
            StructField("latitude", DoubleType(), True),
            StructField("longitude", DoubleType(), True),
            StructField("picture", StringType(), True),
            # Keep old events readable while the topic is being drained.
            StructField("nation", StringType(), True),
        ]
    )


def validate_configuration() -> None:
    missing = [
        name
        for name, value in {
            "MINIO_ROOT_USER": MINIO_ACCESS_KEY,
            "MINIO_ROOT_PASSWORD": MINIO_SECRET_KEY,
            "KAFKA_BOOTSTRAP_SERVERS": KAFKA_BOOTSTRAP_SERVERS,
        }.items()
        if not value
    ]
    if missing:
        raise ValueError("Missing required configuration: " + ", ".join(missing))


def create_spark_session(app_name: str) -> SparkSession:
    logger.info("Starting distributed Spark application=%s", app_name)
    spark = (
        SparkSession.builder.appName(app_name)
        .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY)
        .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY)
        .config("spark.hadoop.fs.s3a.endpoint", MINIO_ENDPOINT)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        .config(
            "spark.hadoop.fs.s3a.aws.credentials.provider",
            "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider",
        )
        .config("spark.sql.files.maxRecordsPerFile", 10000)
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    return spark


def kafka_stream(spark: SparkSession) -> DataFrame:
    return (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS)
        .option("subscribe", KAFKA_TOPIC)
        .option("startingOffsets", "earliest")
        .option("failOnDataLoss", "false")
        .load()
    )


def processed_stream_schema() -> StructType:
    schema = user_schema()
    return StructType(
        schema.fields
        + [
            StructField("registered_timestamp", StringType(), True),
            StructField("processing_timestamp", StringType(), True),
            StructField("ingestion_date", StringType(), True),
        ]
    )
