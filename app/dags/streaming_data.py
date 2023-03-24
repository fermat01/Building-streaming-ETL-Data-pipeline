import time
import json
import random
from kafka import KafkaProducer, KafkaConsumer
from influxdb import InfluxDBClient

def generate_data():
    # Generate random data
    data = {
        "timestamp": int(time.time()),
        "temperature": random.uniform(20, 30),
        "humidity": random.uniform(30, 50),
        "pressure": random.uniform(1000, 1010)
    }
    return data

def produce_data():
    # Set up Kafka producer
    producer = KafkaProducer(bootstrap_servers=['kafka:9092'], value_serializer=lambda x: json.dumps(x).encode('utf-8'))

    while True:
        data = generate_data()
        producer.send('streams_topic', value=data)
        print(f"Produced data: {data}")
        time.sleep(30)

def write_to_influxdb():
    # Set up InfluxDB client
    client = InfluxDBClient(host='influxdb', port=8086)
    client.switch_database('db0-streams')

    # Set up Kafka consumer
   
    consumer = KafkaConsumer('streams_topic', bootstrap_servers=['kafka:9092'], value_deserializer=lambda x: json.loads(x.decode('utf-8')))
    
    # Write data to InfluxDB
    for message in consumer:
        data = message.value
        json_body = [
            {
                "measurement": "sensor_data",
                "time": data["timestamp"],
                "fields": {
                    "temperature": data["temperature"],
                    "humidity": data["humidity"],
                    "pressure": data["pressure"]
                }
            }
        ]
        client.write_points(json_body)
        print(f"Wrote data to InfluxDB: {data}")


# Set up Airflow DAG
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator

default_args = {
    'owner': 'vianney',
    'depends_on_past': False,
    'start_date': datetime(2023, 3, 4),
    'retries': 1,
    'retry_delay': timedelta(minutes=1),
}

dag = DAG(
    'data_pipeline',
    default_args=default_args,
    description='Data pipeline to stream data from Kafka to InfluxDB',
    schedule_interval=timedelta(minutes=1),
)

# Define tasks
produce_data_task = PythonOperator(
    task_id='produce_data',
    python_callable=produce_data,
    dag=dag
)

write_to_influxdb_task = PythonOperator(
    task_id='write_to_influxdb',
    python_callable=write_to_influxdb,
    dag=dag
)

# Define task dependencies
produce_data_task >> write_to_influxdb_task
