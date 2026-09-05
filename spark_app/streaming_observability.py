import logging
from collections import defaultdict

from pyspark.sql.streaming import StreamingQueryListener

from monitoring.metrics import Metric, push_metrics

logger = logging.getLogger(__name__)


class StreamingMetricsListener(StreamingQueryListener):
    """Publish bounded Spark query and data-quality metrics."""

    def __init__(self):
        super().__init__()
        self.totals = defaultdict(int)

    def onQueryStarted(self, event):
        push_metrics(
            "spark-streaming",
            [Metric("spark_query_active", "gauge", 1, {"query": event.name})],
        )

    def onQueryProgress(self, event):
        progress = event.progress
        query = progress.name or "unnamed"
        input_rows = int(progress.numInputRows or 0)
        self.totals[query] += input_rows
        duration_seconds = float(progress.durationMs.get("triggerExecution", 0)) / 1000
        metrics = [
            Metric("spark_query_active", "gauge", 1, {"query": query}),
            Metric(
                "spark_query_input_rate_rows_per_second",
                "gauge",
                float(progress.inputRowsPerSecond or 0),
                {"query": query},
            ),
            Metric(
                "spark_query_processing_rate_rows_per_second",
                "gauge",
                float(progress.processedRowsPerSecond or 0),
                {"query": query},
            ),
            Metric(
                "spark_query_batch_duration_seconds",
                "gauge",
                duration_seconds,
                {"query": query},
            ),
            Metric(
                "spark_query_processed_records_total",
                "counter",
                self.totals[query],
                {"query": query},
            ),
        ]
        if query == "data_quality_valid":
            metrics.append(
                Metric(
                    "streaming_events_processed_total", "counter", self.totals[query]
                )
            )
        elif query == "data_quality_quarantine":
            metrics.append(
                Metric(
                    "streaming_events_quarantined_total", "counter", self.totals[query]
                )
            )
        push_metrics(f"spark-{query}", metrics)

    def onQueryTerminated(self, event):
        query = event.name or "unnamed"
        failed = 1 if event.exception else 0
        push_metrics(
            f"spark-{query}",
            [
                Metric("spark_query_active", "gauge", 0, {"query": query}),
                Metric("spark_query_failed", "gauge", failed, {"query": query}),
            ],
        )
        if event.exception:
            logger.error("Spark streaming query failed query=%s", query)
