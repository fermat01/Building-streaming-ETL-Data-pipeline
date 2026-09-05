import hashlib
import logging
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

import requests
from airflow import DAG
from airflow.operators.python import PythonOperator
from confluent_kafka import Producer

from monitoring.metrics import Metric, push_metrics

# Constants and configuration
logger = logging.getLogger(__name__)

API_ENDPOINT = os.getenv("RANDOM_USER_API_ENDPOINT", "https://randomuser.me/api/")
KAFKA_BOOTSTRAP_SERVERS = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS",
    "broker-1:9092,broker-2:9093,broker-3:9094",
).split(",")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "streaming-topic")
PAUSE_INTERVAL = int(os.getenv("API_POLL_INTERVAL_SECONDS", "10"))
STREAMING_DURATION = int(os.getenv("STREAMING_DURATION_SECONDS", "120"))
API_TIMEOUT_SECONDS = int(os.getenv("RANDOM_USER_API_TIMEOUT_SECONDS", "15"))
KAFKA_SECURITY_PROTOCOL = os.getenv("KAFKA_SECURITY_PROTOCOL", "SASL_PLAINTEXT")
KAFKA_SASL_MECHANISM = os.getenv("KAFKA_SASL_MECHANISM", "SCRAM-SHA-256")
KAFKA_PRODUCER_USERNAME = os.getenv("KAFKA_PRODUCER_USERNAME")
KAFKA_PRODUCER_PASSWORD = os.getenv("KAFKA_PRODUCER_PASSWORD")
SCHEMA_REGISTRY_URL = os.getenv("SCHEMA_REGISTRY_URL", "http://schema_registry:8081")
SCHEMA_REGISTRY_USERNAME = os.getenv("KAFKA_SCHEMA_REGISTRY_USERNAME")
SCHEMA_REGISTRY_PASSWORD = os.getenv("KAFKA_SCHEMA_REGISTRY_PASSWORD")
SCHEMA_REGISTRY_SUBJECT = os.getenv("SCHEMA_REGISTRY_SUBJECT", "streaming-topic-value")
SCHEMA_PATH = Path(
    os.getenv(
        "EVENT_SCHEMA_PATH",
        str(Path(__file__).parents[1] / "schemas" / "user_event.avsc"),
    )
)

published_events = 0
producer_errors = 0


def get_user_data(url: str = API_ENDPOINT) -> dict:
    """Fetch one user and fail clearly so Airflow can retry the task."""
    response = requests.get(url, params={"results": 1}, timeout=API_TIMEOUT_SECONDS)
    response.raise_for_status()
    results = response.json().get("results", [])
    if not results:
        raise ValueError("Random User API returned no users")
    return results[0]


def format_user_data(data_from_api: dict) -> dict:
    """Formats the fetched user data for Kafka streaming."""
    return {
        "event_id": str(uuid.uuid4()),
        "full_name": f"{data_from_api['name']['title']}. {data_from_api['name']['first']} {data_from_api['name']['last']}",
        "gender": data_from_api["gender"],
        "age": data_from_api["dob"]["age"],
        "address": f"{data_from_api['location']['street']['number']}, {data_from_api['location']['street']['name']}",
        "city": data_from_api["location"]["city"],
        "email": data_from_api["email"],
        "phone": data_from_api["phone"],
        "country": data_from_api["location"]["country"],
        "username": data_from_api["login"]["username"],
        "registered_date": data_from_api["registered"]["date"],
        "zip": encrypt_zip(data_from_api["location"]["postcode"]),
        "latitude": float(data_from_api["location"]["coordinates"]["latitude"]),
        "longitude": float(data_from_api["location"]["coordinates"]["longitude"]),
        "picture": data_from_api["picture"]["large"],
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }


def encrypt_zip(zip_code: object) -> str:
    """Hash a postcode without retaining the source value."""
    zip_str = str(zip_code)
    return hashlib.md5(zip_str.encode("utf-8")).hexdigest()


def configure_kafka(servers: List[str] = KAFKA_BOOTSTRAP_SERVERS) -> Producer:
    """Create a reliable, idempotent producer for the Kafka cluster."""
    producer_username = os.getenv("KAFKA_PRODUCER_USERNAME", KAFKA_PRODUCER_USERNAME)
    producer_password = os.getenv("KAFKA_PRODUCER_PASSWORD", KAFKA_PRODUCER_PASSWORD)
    missing = [
        name
        for name, value in {
            "KAFKA_PRODUCER_USERNAME": producer_username,
            "KAFKA_PRODUCER_PASSWORD": producer_password,
        }.items()
        if not value
    ]
    if missing:
        raise ValueError("Missing required Kafka configuration: " + ", ".join(missing))

    settings = {
        "bootstrap.servers": ",".join(servers),
        "client.id": "random-user-api-producer",
        "security.protocol": KAFKA_SECURITY_PROTOCOL,
        "sasl.mechanisms": KAFKA_SASL_MECHANISM,
        "sasl.username": producer_username,
        "sasl.password": producer_password,
        "acks": "all",
        "enable.idempotence": True,
        "retries": 5,
        "delivery.timeout.ms": 120000,
    }
    return Producer(settings)


def configure_schema_serializer():
    """Create an Avro serializer backed by the governed Schema Registry subject."""
    from confluent_kafka.schema_registry import SchemaRegistryClient
    from confluent_kafka.schema_registry import topic_subject_name_strategy
    from confluent_kafka.schema_registry.avro import AvroSerializer

    missing = [
        name
        for name, value in {
            "SCHEMA_REGISTRY_URL": SCHEMA_REGISTRY_URL,
            "KAFKA_SCHEMA_REGISTRY_USERNAME": SCHEMA_REGISTRY_USERNAME,
            "KAFKA_SCHEMA_REGISTRY_PASSWORD": SCHEMA_REGISTRY_PASSWORD,
        }.items()
        if not value
    ]
    if missing:
        raise ValueError(
            "Missing required schema registry configuration: " + ", ".join(missing)
        )

    schema_client = SchemaRegistryClient(
        {
            "url": SCHEMA_REGISTRY_URL,
            "basic.auth.user.info": f"{SCHEMA_REGISTRY_USERNAME}:{SCHEMA_REGISTRY_PASSWORD}",
        }
    )
    schema_string = SCHEMA_PATH.read_text(encoding="utf-8")
    return AvroSerializer(
        schema_client,
        schema_string,
        conf={"subject.name.strategy": topic_subject_name_strategy},
    )


def publish_to_kafka(producer: Producer, topic: str, data: dict, serializer) -> None:
    """Send one event and raise if Kafka cannot deliver it."""
    from confluent_kafka.serialization import MessageField, SerializationContext

    producer.produce(
        topic,
        key=data["event_id"],
        value=serializer(data, SerializationContext(topic, MessageField.VALUE)),
        callback=delivery_status,
    )
    producer.poll(0)
    remaining = producer.flush(30)
    if remaining:
        raise RuntimeError(f"Kafka delivery timed out for {remaining} message(s)")


def delivery_status(err, msg) -> None:
    """Reports the delivery status of the message to Kafka."""
    global published_events, producer_errors
    if err is not None:
        producer_errors += 1
        logger.error("Kafka message delivery failed: %s", err)
    else:
        published_events += 1
        logger.info(
            "Kafka message delivered topic=%s partition=%s offset=%s",
            msg.topic(),
            msg.partition(),
            msg.offset(),
        )


def initiate_stream():
    """Initiates the process to stream user data to Kafka."""
    kafka_producer = configure_kafka()
    schema_serializer = configure_schema_serializer()
    events_to_publish = max(1, STREAMING_DURATION // PAUSE_INTERVAL)
    logger.info(
        "Starting API ingestion events=%s topic=%s", events_to_publish, KAFKA_TOPIC
    )
    for event_number in range(events_to_publish):
        raw_data = get_user_data()
        event = format_user_data(raw_data)
        publish_to_kafka(kafka_producer, KAFKA_TOPIC, event, schema_serializer)
        logger.info(
            "Published API event number=%s event_id=%s",
            event_number + 1,
            event["event_id"],
        )
        time.sleep(PAUSE_INTERVAL)
    kafka_producer.flush(30)
    push_metrics(
        "airflow-producer",
        [
            Metric("streaming_events_produced_total", "counter", published_events),
            Metric("streaming_producer_errors_total", "counter", producer_errors),
        ],
    )


if __name__ == "__main__":
    initiate_stream()


# Define airflow dag for streaming service
DAG_DEFAULT_ARGS = {
    "owner": "Coder2f",
    "start_date": datetime(2024, 5, 3, 10, 00),  # 2024 May 03 at 10:00 AM
    "retries": 1,
    "retry_delay": timedelta(seconds=5),
}

# Creating the DAG with its configuration
with DAG(
    "streaming_etl_pepiline",
    default_args=DAG_DEFAULT_ARGS,
    schedule_interval=timedelta(minutes=5),  #'0 1 * * *',
    catchup=False,
    description="Stream random user names to Kafka topic",
    max_active_runs=1,
) as dag:

    # Defining the data streaming task using PythonOperator
    streaming_task = PythonOperator(
        task_id="stream_to_kafka_task", python_callable=initiate_stream, dag=dag
    )

    streaming_task
