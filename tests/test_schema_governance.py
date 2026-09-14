import json
import os
import sys
import unittest
from pathlib import Path

import requests

ROOT = Path(__file__).parents[1]
SCHEMA_PATH = ROOT / "schemas/user_event.avsc"
SPARK_APP = ROOT / "spark_app"
if str(SPARK_APP) not in sys.path:
    sys.path.insert(0, str(SPARK_APP))

from schema_codec import decode_confluent_payload  # noqa: E402


class SchemaContractTests(unittest.TestCase):
    def test_canonical_contract_has_expected_v1_fields(self):
        contract = json.loads(SCHEMA_PATH.read_text())
        self.assertEqual(contract["name"], "UserEvent")
        self.assertEqual(contract["fields"][0], {"name": "event_id", "type": "string"})
        fields = {field["name"]: field for field in contract["fields"]}
        self.assertEqual(fields["age"]["type"], ["null", "int"])
        self.assertEqual(len(fields), 16)

    def test_legacy_json_is_still_decoded(self):
        payload = b'{"event_id":"legacy-event","age":36}'
        self.assertEqual(decode_confluent_payload(payload), payload.decode())

    def test_malformed_binary_payload_becomes_diagnostic_json(self):
        diagnostic = json.loads(decode_confluent_payload(b"\x00\x00\x00\x00\x01bad"))
        self.assertIn("_schema_error", diagnostic)

    @unittest.skipUnless(
        __import__("importlib.util").util.find_spec("fastavro"),
        "fastavro is installed in the Spark image, "
        "not the lightweight unit-test environment",
    )
    def test_avro_wire_payload_round_trips_to_logical_json(self):
        import io

        from fastavro import parse_schema, schemaless_writer

        schema = parse_schema(json.loads(SCHEMA_PATH.read_text()))
        event = {"event_id": "event-1", "age": 36}
        for field in schema["fields"]:
            event.setdefault(field["name"], None)
        encoded = io.BytesIO()
        schemaless_writer(encoded, schema, event)
        payload = b"\x00\x00\x00\x00\x01" + encoded.getvalue()
        decoded = json.loads(decode_confluent_payload(payload))
        self.assertEqual(decoded["event_id"], "event-1")
        self.assertEqual(decoded["age"], 36)


@unittest.skipUnless(
    os.getenv("SCHEMA_REGISTRY_INTEGRATION") == "1",
    "set SCHEMA_REGISTRY_INTEGRATION=1 to run against a live Schema Registry",
)
class SchemaRegistryIntegrationTests(unittest.TestCase):
    subject = os.getenv("SCHEMA_REGISTRY_TEST_SUBJECT", "streaming-topic-value")
    registry_url = os.getenv("SCHEMA_REGISTRY_URL", "http://localhost:8081")

    @classmethod
    def setUpClass(cls):
        cls.auth = (
            os.getenv("KAFKA_SCHEMA_REGISTRY_USERNAME"),
            os.getenv("KAFKA_SCHEMA_REGISTRY_PASSWORD"),
        )
        cls.schema = json.loads(SCHEMA_PATH.read_text())

    def _register(self, schema):
        response = requests.post(
            f"{self.registry_url}/subjects/{self.subject}/versions",
            auth=self.auth,
            json={"schema": json.dumps(schema)},
            timeout=10,
        )
        return response

    def test_registration_and_retrieval(self):
        response = self._register(self.schema)
        self.assertEqual(response.status_code, 200, response.text)
        retrieved = requests.get(
            f"{self.registry_url}/subjects/{self.subject}/versions/latest",
            auth=self.auth,
            timeout=10,
        )
        self.assertEqual(retrieved.status_code, 200, retrieved.text)
        self.assertEqual(json.loads(retrieved.json()["schema"]), self.schema)

    def test_compatible_evolution_is_accepted(self):
        evolved = json.loads(json.dumps(self.schema))
        evolved["fields"].append(
            {"name": "middle_name", "type": ["null", "string"], "default": None}
        )
        response = self._register(evolved)
        self.assertEqual(response.status_code, 200, response.text)

    def test_incompatible_type_change_is_rejected(self):
        incompatible = json.loads(json.dumps(self.schema))
        for field in incompatible["fields"]:
            if field["name"] == "age":
                field["type"] = ["null", "string"]
                break
        response = self._register(incompatible)
        self.assertEqual(response.status_code, 409, response.text)


if __name__ == "__main__":
    unittest.main()
