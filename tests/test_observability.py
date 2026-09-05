import json
import unittest
from pathlib import Path
from unittest.mock import patch

from monitoring.metrics import Metric, push_metrics

ROOT = Path(__file__).parents[1]


class ObservabilityContractTests(unittest.TestCase):
    def test_prometheus_configuration_scrapes_required_sources(self):
        config = (ROOT / "monitoring/prometheus/prometheus.yml").read_text()
        for target in (
            "kafka-exporter:9308",
            "airflow-statsd-exporter:9102",
            "spark-master:8080",
            "pushgateway:9091",
            "cadvisor:8080",
            "minio:9000",
        ):
            self.assertIn(target, config)

    def test_dashboards_are_valid_json_and_provisioned(self):
        dashboards = ROOT / "monitoring/grafana/dashboards"
        files = sorted(dashboards.glob("*.json"))
        self.assertEqual(len(files), 5)
        for dashboard in files:
            payload = json.loads(dashboard.read_text())
            self.assertIn("title", payload)
            self.assertIn("panels", payload)

    @patch("monitoring.metrics.requests.put")
    def test_metric_push_is_best_effort_and_has_no_event_labels(self, put):
        put.return_value.raise_for_status.return_value = None
        push_metrics(
            "test-job",
            [Metric("streaming_events_processed_total", "counter", 3)],
        )
        body = put.call_args.kwargs["data"].decode()
        self.assertIn("streaming_events_processed_total 3", body)
        self.assertNotIn("email", body)
        self.assertNotIn("event_id", body)

    @patch(
        "monitoring.metrics.requests.put",
        side_effect=__import__("requests").ConnectionError("down"),
    )
    def test_metric_push_does_not_raise_when_monitoring_is_down(self, put):
        push_metrics(
            "test-job", [Metric("streaming_processing_errors_total", "counter", 1)]
        )


if __name__ == "__main__":
    unittest.main()
