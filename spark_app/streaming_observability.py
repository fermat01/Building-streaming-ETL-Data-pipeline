import logging
from collections import defaultdict

from pyspark.sql.streaming.listener import StreamingQueryListener

from monitoring.metrics import Metric, push_metrics

logger = logging.getLogger(__name__)


class StreamingMetricsListener(StreamingQueryListener):
    """Publish bounded Spark query and data-quality metrics."""

    def __init__(self) -> None:
        super().__init__()
        self.totals: defaultdict[str, int] = defaultdict(int)
        self.query_names: dict[str, str] = {}

    def onQueryStarted(self, event) -> None:
        query_id = str(event.id)
        query = event.name or "unnamed"

        self.query_names[query_id] = query

        push_metrics(
            "spark-streaming",
            [
                Metric(
                    "spark_query_active",
                    "gauge",
                    1,
                    {"query": query},
                )
            ],
        )

    def onQueryProgress(self, event) -> None:
        progress = event.progress
        query_id = str(progress.id)

        query = progress.name or self.query_names.get(query_id) or "unnamed"

        self.query_names[query_id] = query

        input_rows = int(progress.numInputRows or 0)
        self.totals[query] += input_rows

        duration_seconds = float(progress.durationMs.get("triggerExecution", 0)) / 1000

        metrics = [
            Metric(
                "spark_query_active",
                "gauge",
                1,
                {"query": query},
            ),
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
                    "streaming_events_processed_total",
                    "counter",
                    self.totals[query],
                )
            )
        elif query == "data_quality_quarantine":
            metrics.append(
                Metric(
                    "streaming_events_quarantined_total",
                    "counter",
                    self.totals[query],
                )
            )

        push_metrics(f"spark-{query}", metrics)

    def onQueryTerminated(self, event) -> None:
        query_id = str(event.id)
        query = self.query_names.pop(query_id, query_id)

        failed = 1 if event.exception else 0

        push_metrics(
            f"spark-{query}",
            [
                Metric(
                    "spark_query_active",
                    "gauge",
                    0,
                    {"query": query},
                ),
                Metric(
                    "spark_query_failed",
                    "gauge",
                    failed,
                    {"query": query},
                ),
            ],
        )

        if event.exception:
            logger.error(
                "Spark streaming query failed query=%s exception=%s",
                query,
                event.exception,
            )
