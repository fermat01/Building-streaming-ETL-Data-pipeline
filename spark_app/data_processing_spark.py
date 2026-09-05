import logging

from pyspark.sql import DataFrame
from pyspark.sql.functions import (
    coalesce,
    col,
    current_timestamp,
    from_json,
    length,
    lit,
    to_date,
    to_timestamp,
    trim,
    when,
)

from streaming_common import (
    CHECKPOINT_ROOT,
    PROCESSED_PATH,
    QUARANTINE_PATH,
    create_spark_session,
    kafka_stream,
    user_schema,
    validate_configuration,
)

logger = logging.getLogger("spark_data_quality")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)


def parse_and_validate(stream: DataFrame) -> tuple[DataFrame, DataFrame]:
    """Parse Kafka JSON and split malformed or invalid events from valid data."""
    parsed = (
        stream.select(col("value").cast("string").alias("raw_json"))
        .withColumn("data", from_json(col("raw_json"), user_schema()))
        .select("raw_json", "data.*")
        .withColumn("country", coalesce(col("country"), col("nation")))
        .withColumn("registered_timestamp", to_timestamp("registered_date"))
        .withColumn("processing_timestamp", current_timestamp())
        .withColumn("ingestion_date", to_date("processing_timestamp"))
    )

    def non_empty(field: str):
        return length(trim(coalesce(col(field), lit("")))) > 0

    valid_condition = coalesce(
        (
            col("event_id").isNotNull()
            & non_empty("full_name")
            & non_empty("gender")
            & col("age").between(0, 120)
            & non_empty("email")
            & non_empty("city")
            & non_empty("country")
            & col("latitude").between(-90.0, 90.0)
            & col("longitude").between(-180.0, 180.0)
        ),
        lit(False),
    )
    quality_reason = (
        when(col("event_id").isNull(), lit("malformed_json_or_missing_event_id"))
        .when(~col("age").between(0, 120), lit("age_out_of_range"))
        .when(~non_empty("email"), lit("email_missing"))
        .when(~non_empty("city") | ~non_empty("country"), lit("location_missing"))
        .when(
            ~col("latitude").between(-90.0, 90.0)
            | ~col("longitude").between(-180.0, 180.0),
            lit("coordinates_invalid"),
        )
        .otherwise(lit("validation_failed"))
    )
    valid = parsed.where(valid_condition).drop("raw_json", "nation")
    invalid = (
        parsed.where(~valid_condition)
        .withColumn("quarantine_reason", quality_reason)
        .select(
            "raw_json", "quarantine_reason", "processing_timestamp", "ingestion_date"
        )
    )
    return valid, invalid


def write_streams(valid: DataFrame, invalid: DataFrame) -> None:
    valid_query = (
        valid.writeStream.format("parquet")
        .outputMode("append")
        .option("path", PROCESSED_PATH)
        .option("checkpointLocation", f"{CHECKPOINT_ROOT}/processed")
        .option("retention", "7d")
        .option("maxRecordsPerFile", 10000)
        .partitionBy("ingestion_date")
        .trigger(processingTime="10 seconds")
        .start()
    )
    quarantine_query = (
        invalid.writeStream.format("parquet")
        .outputMode("append")
        .option("path", QUARANTINE_PATH)
        .option("checkpointLocation", f"{CHECKPOINT_ROOT}/quarantine")
        .option("maxRecordsPerFile", 10000)
        .partitionBy("ingestion_date")
        .trigger(processingTime="10 seconds")
        .start()
    )
    logger.info("Valid output=%s quarantine output=%s", PROCESSED_PATH, QUARANTINE_PATH)
    valid_query.awaitTermination()
    quarantine_query.stop()


def main() -> None:
    validate_configuration()
    spark = create_spark_session("SparkStructuredStreamingDataQuality")
    try:
        valid, invalid = parse_and_validate(kafka_stream(spark))
        write_streams(valid, invalid)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
