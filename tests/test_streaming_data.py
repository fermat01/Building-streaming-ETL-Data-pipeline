import importlib
import sys
import types
import unittest
from unittest.mock import patch


def load_streaming_module():
    airflow = types.ModuleType("airflow")

    class FakeDAG:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    airflow.DAG = FakeDAG
    airflow_operators = types.ModuleType("airflow.operators")
    airflow_python = types.ModuleType("airflow.operators.python")

    class FakePythonOperator:
        def __init__(self, *args, **kwargs):
            pass

    airflow_python.PythonOperator = FakePythonOperator
    confluent_kafka = types.ModuleType("confluent_kafka")
    confluent_kafka.Producer = object

    with patch.dict(
        sys.modules,
        {
            "airflow": airflow,
            "airflow.operators": airflow_operators,
            "airflow.operators.python": airflow_python,
            "confluent_kafka": confluent_kafka,
        },
    ):
        return importlib.import_module("dags.streaming_data")


streaming_data = load_streaming_module()


class StreamingDataUnitTests(unittest.TestCase):
    def test_encrypt_zip_is_deterministic_and_does_not_expose_value(self):
        encrypted = streaming_data.encrypt_zip("75001")

        self.assertEqual(encrypted, streaming_data.encrypt_zip(75001))
        self.assertNotEqual(encrypted, "75001")
        self.assertEqual(len(encrypted), 32)

    def test_format_user_data_maps_api_response(self):
        api_user = {
            "name": {"title": "Ms", "first": "Ada", "last": "Lovelace"},
            "gender": "female",
            "dob": {"age": 36},
            "location": {
                "street": {"number": 1, "name": "Example Street"},
                "city": "London",
                "country": "United Kingdom",
                "postcode": "N1",
                "coordinates": {"latitude": "51.5", "longitude": "-0.1"},
            },
            "email": "ada@example.com",
            "phone": "12345",
            "login": {"username": "ada"},
            "registered": {"date": "1815-12-10T00:00:00Z"},
            "picture": {"large": "https://example.com/ada.jpg"},
        }

        event = streaming_data.format_user_data(api_user)

        self.assertEqual(event["full_name"], "Ms. Ada Lovelace")
        self.assertEqual(event["country"], "United Kingdom")
        self.assertEqual(event["latitude"], 51.5)
        self.assertEqual(event["longitude"], -0.1)
        self.assertEqual(len(event["event_id"]), 36)

    def test_configure_kafka_enables_reliable_delivery(self):
        producer = object()

        with patch.dict(
            "os.environ",
            {
                "KAFKA_PRODUCER_USERNAME": "producer",
                "KAFKA_PRODUCER_PASSWORD": "producer-password",
            },
        ), patch.object(streaming_data, "Producer", return_value=producer) as factory:
            result = streaming_data.configure_kafka(["broker:9092"])

        self.assertIs(result, producer)
        settings = factory.call_args.args[0]
        self.assertEqual(settings["bootstrap.servers"], "broker:9092")
        self.assertEqual(settings["acks"], "all")
        self.assertTrue(settings["enable.idempotence"])
        self.assertEqual(settings["retries"], 5)
        self.assertEqual(settings["security.protocol"], "SASL_PLAINTEXT")
        self.assertEqual(settings["sasl.mechanisms"], "SCRAM-SHA-256")
        self.assertEqual(settings["sasl.username"], "producer")

    def test_configure_kafka_requires_credentials(self):
        with patch.object(
            streaming_data, "KAFKA_PRODUCER_USERNAME", None
        ), patch.object(streaming_data, "KAFKA_PRODUCER_PASSWORD", None):
            with self.assertRaisesRegex(ValueError, "KAFKA_PRODUCER_USERNAME"):
                streaming_data.configure_kafka(["broker:9092"])


if __name__ == "__main__":
    unittest.main()
