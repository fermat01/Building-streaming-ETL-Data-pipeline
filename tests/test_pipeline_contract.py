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

    def test_compose_keeps_standalone_spark_topology(self):
        compose = (ROOT / "docker-compose.yml").read_text()
        for service in ("spark-master:", "spark-worker-1:", "spark-worker-2:"):
            self.assertIn(service, compose)
        self.assertIn("spark://spark-master:7077", compose)


if __name__ == "__main__":
    unittest.main()
