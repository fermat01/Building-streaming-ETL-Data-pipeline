import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


class PipelineContractTests(unittest.TestCase):
    def test_ingestion_uses_reliable_kafka_settings(self):
        source = (ROOT / "dags/streaming_data.py").read_text()
        self.assertIn('"acks": "all"', source)
        self.assertIn('"enable.idempotence": True', source)
        self.assertIn('"retries": 5', source)
        self.assertIn("timeout=API_TIMEOUT_SECONDS", source)
        self.assertIn('"security.protocol": KAFKA_SECURITY_PROTOCOL', source)
        self.assertIn('"sasl.mechanisms": KAFKA_SASL_MECHANISM', source)
        self.assertIn('"sasl.username": producer_username', source)

    def test_kafka_security_contract_is_externalized(self):
        compose = (ROOT / "docker-compose.yml").read_text()
        env_example = (ROOT / ".env.example").read_text()
        self.assertIn("INTERNAL:SASL_PLAINTEXT,EXTERNAL:SASL_PLAINTEXT", compose)
        self.assertIn("KAFKA_AUTHORIZER_CLASS_NAME", compose)
        self.assertIn('KAFKA_ALLOW_EVERYONE_IF_NO_ACL_FOUND: "false"', compose)
        self.assertIn(
            "kafka.sasl.jaas.config",
            (ROOT / "spark_app/streaming_common.py").read_text(),
        )
        self.assertIn("KAFKA_CONSUMER_GROUP_ID", env_example)
        self.assertNotIn("KafkaAdminLocal2026!", env_example)
        self.assertNotIn("AirflowProducerLocal2026!", env_example)

    def test_spark_jobs_are_parseable_and_distributed(self):
        for relative_path in (
            "spark_app/streaming_common.py",
            "spark_app/data_processing_spark.py",
            "spark_app/analytics_spark.py",
        ):
            ast.parse((ROOT / relative_path).read_text())

        processing = (ROOT / "spark_app/data_processing_spark.py").read_text()
        analytics = (ROOT / "spark_app/analytics_spark.py").read_text()
        self.assertIn('format("parquet")', processing)
        self.assertIn("QUARANTINE_PATH", processing)
        self.assertIn('os.getenv("ANALYTICS_WINDOW", "1 minute")', analytics)
        self.assertIn(
            'os.getenv("ANALYTICS_WATERMARK", "1 minute 50 seconds")', analytics
        )
        self.assertIn("ANALYTICS_PATH", analytics)
        self.assertNotIn("local[", processing + analytics)

        submit_script = (ROOT / "scripts/run_spark_submit.sh").read_text()
        self.assertIn("--py-files", submit_script)
        self.assertIn("--files", submit_script)
        self.assertIn("schema_codec.py", submit_script)
        self.assertIn("user_event.avsc", submit_script)
        self.assertIn(
            "A data-quality Spark application is already active", submit_script
        )

    def test_compose_keeps_standalone_spark_topology(self):
        compose = (ROOT / "docker-compose.yml").read_text()
        for service in ("spark-master:", "spark-worker-1:", "spark-worker-2:"):
            self.assertIn(service, compose)
        self.assertIn("spark://spark-master:7077", compose)


if __name__ == "__main__":
    unittest.main()
