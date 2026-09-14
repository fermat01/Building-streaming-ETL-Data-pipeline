import logging
import os
import time

from pyspark.sql import DataFrame
from pyspark.sql.functions import avg, col, count, window
from pyspark.sql.types import (
    DateType,
    DoubleType,
    IntegerType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)
from streaming_common import (
    ANALYTICS_PATH,
    CHECKPOINT_ROOT,
    PROCESSED_PATH,
    create_spark_session,
    validate_configuration,
)
from streaming_observability import StreamingMetricsListener

logger = logging.getLogger("spark_streaming_analytics")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

ANALYTICS_WINDOW = os.getenv("ANALYTICS_WINDOW", "1 minute")
ANALYTICS_WATERMARK = os.getenv("ANALYTICS_WATERMARK", "1 minute 50 seconds")
INPUT_WAIT_SECONDS = int(os.getenv("ANALYTICS_INPUT_WAIT_SECONDS", "60"))


PROCESSED_SCHEMA = StructType(
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
        StructField("registered_timestamp", TimestampType(), True),
        StructField("ingested_at", StringType(), True),
        StructField("zip", StringType(), True),
        StructField("latitude", DoubleType(), True),
        StructField("longitude", DoubleType(), True),
        StructField("picture", StringType(), True),
        StructField("processing_timestamp", TimestampType(), True),
        StructField("ingestion_date", DateType(), True),
    ]
)


def analytics_stream(spark) -> DataFrame:
    """Read validated Parquet and aggregate event-time windows."""
    hadoop_configuration = spark._jsc.hadoopConfiguration()
    processed_path = spark._jvm.org.apache.hadoop.fs.Path(PROCESSED_PATH)
    processed_filesystem = spark._jvm.org.apache.hadoop.fs.FileSystem.get(
        processed_path.toUri(), hadoop_configuration
    )
    for _ in range(INPUT_WAIT_SECONDS):
        if processed_filesystem.exists(processed_path):
            break
        time.sleep(1)
    users = (
        spark.readStream.schema(PROCESSED_SCHEMA)
        .format("parquet")
        .load(PROCESSED_PATH)
        .withWatermark("processing_timestamp", ANALYTICS_WATERMARK)
    )
    return (
        users.groupBy(
            window(col("processing_timestamp"), ANALYTICS_WINDOW),
            col("ingestion_date"),
            col("country"),
            col("gender"),
        )
        .agg(
            count("event_id").alias("event_count"),
            avg("age").alias("average_age"),
        )
        .select(
            col("window.start").alias("window_start"),
            col("window.end").alias("window_end"),
            "ingestion_date",
            "country",
            "gender",
            "event_count",
            "average_age",
        )
    )


def main() -> None:
    validate_configuration()
    spark = create_spark_session("SparkStructuredStreamingAnalytics")
    try:
        spark.streams.addListener(StreamingMetricsListener())
        query = (
            analytics_stream(spark)
            .writeStream.format("parquet")
            .queryName("analytics")
            .outputMode("append")
            .option("path", ANALYTICS_PATH)
            .option("checkpointLocation", f"{CHECKPOINT_ROOT}/analytics")
            .option("maxRecordsPerFile", 10000)
            .partitionBy("ingestion_date")
            .trigger(processingTime="30 seconds")
            .start()
        )
        logger.info("Analytics output=%s", ANALYTICS_PATH)
        query.awaitTermination()
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
