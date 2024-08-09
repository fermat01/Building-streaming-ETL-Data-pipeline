import logging
import sys
import traceback
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, FloatType
from pyspark import SparkConf, SparkContext
from pyspark.sql.types import LongType, TimestampType, BinaryType

# Initialize logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s:%(funcName)s:%(levelname)s:%(message)s')
logger = logging.getLogger("spark_structured_streaming")


def initialize_spark_session(app_name, access_key, secret_key):
    """
    Initialize the Spark Session with provided configurations.

    :param app_name: Name of the spark application.
    :param access_key: Access key for S3.
    :param secret_key: Secret key for S3.
    :return: Spark session object or None if there's an error.
    """
    try:
        spark = SparkSession \
            .builder \
            .appName(app_name) \
            .config("spark.hadoop.fs.s3a.access.key", access_key) \
            .config("spark.hadoop.fs.s3a.secret.key", secret_key) \
            .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000")\
            .config("spark.hadoop.fs.s3a.path.style.access", "true") \
            .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
            .getOrCreate()

        spark.sparkContext.setLogLevel("ERROR")
        logger.info('Spark session initialized successfully')
        return spark

    except Exception as e:
        logger.error(f"Spark session initialization failed. Error: {e}")
        return None


def get_streaming_dataframe(spark, brokers, topic):
    """
    Get a streaming dataframe from Kafka.

    :param spark: Initialized Spark session.
    :param brokers: Comma-separated list of Kafka brokers.
    :param topic: Kafka topic to subscribe to.
    :return: Dataframe object or None if there's an error.
    """
    try:
        df = spark \
            .readStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", brokers) \
            .option("subscribe", topic) \
            .option("delimiter", ",") \
            .option("startingOffsets", "earliest") \
            .option("failOnDataLoss", "false") \
            .option("mode", "PERMISSIVE") \
            .option("truncate", False) \
            .load()
        logger.info("Streaming dataframe fetched successfully")
        return df

    except Exception as e:
        logger.warning(f"Failed to fetch streaming dataframe. Error: {e}")
        return None


def transform_streaming_data(df):
    """
    Transform the initial dataframe to get the final structure.

    :param df: Initial dataframe with raw data.
    :return: Transformed dataframe.
    """
    schema = StructType([
        StructField("full_name", StringType(), False),
        StructField("gender", StringType(), False),
        StructField("age", StringType(), False),
        StructField("address", StringType(), False),
        StructField("city", StringType(), False),
        StructField("email", StringType(), False),
        StructField("phone", StringType(), False),
        StructField("nation", StringType(), False),
        StructField("username", StringType(), False),
        StructField("registered_date", TimestampType(), False),
        StructField("zip", LongType(), False),
        StructField("latitude", FloatType(), False),
        StructField("longitude", FloatType(), False),
        StructField("picture", BinaryType(), False)
    ])

    transformed_df = df.selectExpr("CAST(value AS STRING)") \
        .select(from_json(col("value"), schema).alias("data")) \
        .select("data.*")
    return transformed_df


def initiate_streaming_to_bucket(df, path, checkpoint_location):
    """
    Start streaming the transformed data to the specified S3 bucket in parquet format.

    :param df: Transformed dataframe.
    :param path: S3 bucket path.
    :param checkpoint_location: Checkpoint location for streaming.
    :return: None
    """
    logger.info("Initiating streaming process to minio object storage...")
    stream_query = (df.writeStream
                    .format("parquet")
                    .outputMode("append")
                    .trigger(processingTime='1 second') \
                    .option("path", path)
                    .option("checkpointLocation", checkpoint_location)
                    .start())
    stream_query.awaitTermination()

def main():
   
    app_name = "SparkStructuredStreamingToMinioS3"
    access_key = "ENTER_YOUR_MINIO_ACCESS_KEY"
    secret_key = "ENTER_YOUR_MINIO_SECRET_KEY"
    brokers = "broker-1:9092,broker-2:9093,broker-3:9094"
    topic = "ENTER_CREATED_KAFKA_TOPIC_NAME"
    path = "ENETER_YOUR_BUCKET_PATH"
    checkpoint_location = "ENETER_YOUR_CHECKPOINT_LOCATION"

    spark = initialize_spark_session(app_name, access_key, secret_key)
    if spark:
        df = get_streaming_dataframe(spark, brokers, topic)
        if df:
            transformed_df = transform_streaming_data(df)
            initiate_streaming_to_bucket(
                transformed_df, path, checkpoint_location)


# Execute the main function if this script is run as the main module
if __name__ == '__main__':
    main()
