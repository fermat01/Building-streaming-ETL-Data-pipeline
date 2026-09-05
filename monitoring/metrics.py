"""Best-effort Pushgateway metrics for short-lived pipeline processes."""

import logging
import os
from dataclasses import dataclass
from typing import Iterable, Mapping

import requests

logger = logging.getLogger(__name__)
PUSHGATEWAY_URL = os.getenv("PUSHGATEWAY_URL", "http://pushgateway:9091").rstrip("/")


@dataclass(frozen=True)
class Metric:
    name: str
    metric_type: str
    value: float
    labels: Mapping[str, str] = ()


def _labels(labels: Mapping[str, str]) -> str:
    if not labels:
        return ""
    escaped = []
    for key, value in sorted(labels.items()):
        safe_value = (
            str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        )
        escaped.append(f'{key}="{safe_value}"')
    return "{" + ",".join(escaped) + "}"


def push_metrics(job: str, metrics: Iterable[Metric]) -> None:
    """Push bounded operational metrics without making monitoring a dependency."""
    metric_list = list(metrics)
    if not metric_list:
        return
    lines = []
    seen = set()
    for metric in metric_list:
        if metric.name not in seen:
            lines.append(f"# TYPE {metric.name} {metric.metric_type}")
            seen.add(metric.name)
        lines.append(f"{metric.name}{_labels(metric.labels)} {metric.value}")
    try:
        requests.put(
            f"{PUSHGATEWAY_URL}/metrics/job/{job}",
            data=("\n".join(lines) + "\n").encode("utf-8"),
            headers={"Content-Type": "text/plain; version=0.0.4"},
            timeout=2,
        ).raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Observability metrics unavailable: %s", exc)
