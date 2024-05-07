import uuid
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
import requests
import json
import time
import hashlib
from confluent_kafka import Producer
import logging

# Constants and configuration
API_ENDPOINT = "https://randomuser.me/api/?results=1"
KAFKA_BOOTSTRAP_SERVERS = ['kafka_broker_1:19092',
                           'kafka_broker_2:19093', 'kafka_broker_3:19094']
KAFKA_TOPIC = "streaming-topic"
PAUSE_INTERVAL = 10
STREAMING_DURATION = 120


def get_user_data(url=API_ENDPOINT) -> dict:
    """Fetches random user data from the provided API endpoint."""
    resp = requests.get(url)
    if resp.status_code == 200:
        return resp.json()["results"][0]


def format_user_data(data_from_api: dict) -> dict:
    """Formats the fetched user data for Kafka streaming."""
    dict_resp = {
        "full_name": f"{data_from_api['name']['title']}. {data_from_api['name']['first']} {data_from_api['name']['last']}",
        "gender": data_from_api["gender"],
        "age": data_from_api['dob']["age"],
        "address": f"{data_from_api['location']['street']['number']}, {data_from_api['location']['street']['name']}",
        "city": data_from_api['location']['city'],
        "email": data_from_api['email'],
        "phone": data_from_api['phone'],
        "nation": data_from_api['location']['country'],
        "username": data_from_api['login']['username'],
        "registered_date": data_from_api['registered']['date'],
        "zip": encrypt_zip(data_from_api['location']['postcode']),
        "latitude": float(data_from_api['location']['coordinates']['latitude']),
        "longitude": float(data_from_api['location']['coordinates']['longitude']),
        "picture": data_from_api['picture']['large']
    }

    return dict_resp


def encrypt_zip(zip_code):
    """Hashes the zip code using MD5 and returns its integer representation."""
    zip_str = str(zip_code)
    return int(hashlib.md5(zip_str.encode()).hexdigest(), 16)


def configure_kafka(servers=KAFKA_BOOTSTRAP_SERVERS):
    """Creates and returns a Kafka producer instance."""
    settings = {
        'bootstrap.servers': ','.join(servers),
        'client.id': 'producer_instance'
    }
    return Producer(settings)


def publish_to_kafka(producer, topic, data):
    """Sends data to a Kafka topic."""
    producer.produce(topic, value=json.dumps(
        data).encode('utf-8'), callback=delivery_status)
    producer.flush()


def delivery_status(err, msg):
    """Reports the delivery status of the message to Kafka."""
    if err is not None:
        print('Message delivery failed:', err)
    else:
        print('Message delivered to', msg.topic(),
              '[Partition: {}]'.format(msg.partition()))


def initiate_stream():
    """Initiates the process to stream user data to Kafka."""
    kafka_producer = configure_kafka()
    for _ in range(STREAMING_DURATION // PAUSE_INTERVAL):
        raw_data = get_user_data()
        kafka_formatted_data = format_user_data(raw_data)
        publish_to_kafka(kafka_producer, KAFKA_TOPIC, kafka_formatted_data)
        time.sleep(PAUSE_INTERVAL)


if __name__ == "__main__":
    initiate_stream()


# Define airflow dag for streaming service
DAG_DEFAULT_ARGS = {
    'owner': 'Coder2f',
    'start_date': datetime(2024, 5, 3, 10, 00),  # 2024 May 03 at 10:00 AM
    'retries': 1,
    'retry_delay': timedelta(seconds=5)
}

# Creating the DAG with its configuration
with DAG(
    'streaming_etl_pepiline',
    default_args=DAG_DEFAULT_ARGS,
    schedule_interval=timedelta(minutes=5), #'0 1 * * *',
    catchup=False,
    description='Stream random user names to Kafka topic',
    max_active_runs=1
) as dag:

    # Defining the data streaming task using PythonOperator
    streaming_task = PythonOperator(
        task_id='stream_to_kafka_task',
        python_callable=initiate_stream,
        dag=dag
    )

    streaming_task
