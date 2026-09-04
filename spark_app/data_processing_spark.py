import logging
import os

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import col, from_json, to_timestamp
from pyspark.sql.types import (
    FloatType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
)


# ============================================================
# Logging
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s:%(name)s:%(levelname)s:%(message)s",
)

logger = logging.getLogger("spark_structured_streaming")


# ============================================================
# Environment configuration
# ============================================================

APP_NAME = os.getenv(
    "SPARK_APP_NAME",
    "SparkStructuredStreamingToMinIO",
)

MINIO_ENDPOINT = os.getenv(
    "MINIO_ENDPOINT",
    "http://minio:9000",
)

MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD")

KAFKA_BOOTSTRAP_SERVERS = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS",
    "broker-1:9092,broker-2:9093,broker-3:9094",
)

KAFKA_TOPIC = os.getenv(
    "KAFKA_TOPIC",
    "streaming-topic",
)

MINIO_OUTPUT_PATH = os.getenv(
    "MINIO_OUTPUT_PATH",
    "s3a://streaming-data/processed/",
)

SPARK_CHECKPOINT_PATH = os.getenv(
    "SPARK_CHECKPOINT_PATH",
    "s3a://streaming-data/checkpoints/",
)


# ============================================================
# Validation
# ============================================================

def validate_configuration() -> None:
    """Validate required environment variables."""

    required_variables = {
        "MINIO_ACCESS_KEY": MINIO_ACCESS_KEY,
        "MINIO_SECRET_KEY": MINIO_SECRET_KEY,
        "KAFKA_BOOTSTRAP_SERVERS": KAFKA_BOOTSTRAP_SERVERS,
        "KAFKA_TOPIC": KAFKA_TOPIC,
        "MINIO_OUTPUT_PATH": MINIO_OUTPUT_PATH,
        "SPARK_CHECKPOINT_PATH": SPARK_CHECKPOINT_PATH,
    }

    missing_variables = [
        name
        for name, value in required_variables.items()
        if not value
    ]

    if missing_variables:
        raise ValueError(
            "Missing required environment variables: "
            + ", ".join(missing_variables)
        )


# ============================================================
# Spark Session
# ============================================================

def initialize_spark_session() -> SparkSession:
    """
    Initialize Spark session configured for MinIO/S3A.

    Spark execution mode is controlled by spark-submit.
    This application can therefore run on the Spark
    standalone cluster.
    """

    logger.info("Initializing Spark session...")
    logger.info("Application: %s", APP_NAME)
    logger.info("MinIO endpoint: %s", MINIO_ENDPOINT)
    logger.info("Kafka brokers: %s", KAFKA_BOOTSTRAP_SERVERS)
    logger.info("Kafka topic: %s", KAFKA_TOPIC)

    spark = (
        SparkSession.builder
        .appName(APP_NAME)
        .config(
            "spark.hadoop.fs.s3a.access.key",
            MINIO_ACCESS_KEY,
        )
        .config(
            "spark.hadoop.fs.s3a.secret.key",
            MINIO_SECRET_KEY,
        )
        .config(
            "spark.hadoop.fs.s3a.endpoint",
            MINIO_ENDPOINT,
        )
        .config(
            "spark.hadoop.fs.s3a.path.style.access",
            "true",
        )
        .config(
            "spark.hadoop.fs.s3a.impl",
            "org.apache.hadoop.fs.s3a.S3AFileSystem",
        )
        .config(
            "spark.hadoop.fs.s3a.connection.ssl.enabled",
            "false",
        )
        .config(
            "spark.hadoop.fs.s3a.aws.credentials.provider",
            "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider",
        )
        .getOrCreate()
    )

    # Keep Spark logs manageable.
    spark.sparkContext.setLogLevel("WARN")

    logger.info(
        "Spark session initialized successfully."
    )

    return spark


# ============================================================
# Kafka Streaming Source
# ============================================================

def get_streaming_dataframe(
    spark: SparkSession,
) -> DataFrame:
    """
    Create a streaming DataFrame from Kafka.
    """

    logger.info("Connecting to Kafka...")
    logger.info(
        "Bootstrap servers: %s",
        KAFKA_BOOTSTRAP_SERVERS,
    )
    logger.info("Topic: %s", KAFKA_TOPIC)

    df = (
        spark.readStream
        .format("kafka")
        .option(
            "kafka.bootstrap.servers",
            KAFKA_BOOTSTRAP_SERVERS,
        )
        .option(
            "subscribe",
            KAFKA_TOPIC,
        )
        .option(
            "startingOffsets",
            "earliest",
        )
        .option(
            "failOnDataLoss",
            "true",
        )
        .load()
    )

    logger.info(
        "Kafka streaming DataFrame created successfully."
    )

    return df


# ============================================================
# Data Schema
# ============================================================

def get_user_schema() -> StructType:
    """
    Define the schema of messages produced by the Airflow
    Kafka producer.
    """

    return StructType(
        [
            StructField(
                "full_name",
                StringType(),
                True,
            ),
            StructField(
                "gender",
                StringType(),
                True,
            ),
            StructField(
                "age",
                IntegerType(),
                True,
            ),
            StructField(
                "address",
                StringType(),
                True,
            ),
            StructField(
                "city",
                StringType(),
                True,
            ),
            StructField(
                "email",
                StringType(),
                True,
            ),
            StructField(
                "phone",
                StringType(),
                True,
            ),
            StructField(
                "nation",
                StringType(),
                True,
            ),
            StructField(
                "username",
                StringType(),
                True,
            ),
            StructField(
                "registered_date",
                StringType(),
                True,
            ),
            StructField(
                "zip",
                LongType(),
                True,
            ),
            StructField(
                "latitude",
                FloatType(),
                True,
            ),
            StructField(
                "longitude",
                FloatType(),
                True,
            ),
            StructField(
                "picture",
                StringType(),
                True,
            ),
        ]
    )


# ============================================================
# Transformation
# ============================================================

def transform_streaming_data(
    df: DataFrame,
) -> DataFrame:
    """
    Deserialize Kafka JSON messages and transform them into
    the final structured schema.
    """

    logger.info("Transforming streaming data...")

    schema = get_user_schema()

    transformed_df = (
        df
        # Kafka value is binary → convert to JSON string.
        .select(
            col("value")
            .cast("string")
            .alias("json_value")
        )

        # Deserialize JSON.
        .select(
            from_json(
                col("json_value"),
                schema,
            ).alias("data")
        )

        # Flatten the struct.
        .select("data.*")

        # Convert ISO timestamp string to Spark timestamp.
        .withColumn(
            "registered_date",
            to_timestamp(
                col("registered_date")
            ),
        )
    )

    logger.info(
        "Streaming transformation configured successfully."
    )

    return transformed_df


# ============================================================
# MinIO / Parquet Sink
# ============================================================

def initiate_streaming_to_bucket(
    df: DataFrame,
) -> None:
    """
    Write transformed streaming data to MinIO in Parquet
    format with checkpointing.
    """

    logger.info(
        "Starting streaming sink..."
    )

    logger.info(
        "Output path: %s",
        MINIO_OUTPUT_PATH,
    )

    logger.info(
        "Checkpoint path: %s",
        SPARK_CHECKPOINT_PATH,
    )

    stream_query = (
        df.writeStream
        .format("parquet")
        .outputMode("append")
        .option(
            "path",
            MINIO_OUTPUT_PATH,
        )
        .option(
            "checkpointLocation",
            SPARK_CHECKPOINT_PATH,
        )
        .trigger(
            processingTime="5 seconds"
        )
        .start()
    )

    logger.info(
        "Streaming query started successfully."
    )

    # Keep the streaming application alive.
    stream_query.awaitTermination()


# ============================================================
# Main
# ============================================================

def main() -> None:
    """
    Application entry point.
    """

    logger.info(
        "Starting %s",
        APP_NAME,
    )

    validate_configuration()

    spark = initialize_spark_session()

    try:
        kafka_df = get_streaming_dataframe(spark)

        transformed_df = transform_streaming_data(
            kafka_df
        )

        initiate_streaming_to_bucket(
            transformed_df
        )

    except Exception:
        logger.exception(
            "Spark Structured Streaming application failed."
        )
        raise

    finally:
        spark.stop()

        logger.info(
            "Spark session stopped."
        )


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    main()