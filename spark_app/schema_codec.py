"""Decode Confluent Avro payloads while retaining legacy JSON compatibility."""

import io
import json
import os
from pathlib import Path
from typing import Any

SCHEMA_PATH = Path(__file__).parents[1] / "schemas" / "user_event.avsc"
_SCHEMA = None


def _schema() -> Any:
    global _SCHEMA
    if _SCHEMA is None:
        from fastavro import parse_schema

        schema_path = os.getenv("EVENT_SCHEMA_PATH")
        if schema_path and Path(schema_path).exists():
            distributed_schema_path = Path(schema_path)
        else:
            try:
                from pyspark import SparkFiles

                distributed_schema_path = Path(SparkFiles.get("user_event.avsc"))
            except (ImportError, RuntimeError):
                distributed_schema_path = SCHEMA_PATH
        _SCHEMA = parse_schema(json.loads(distributed_schema_path.read_text()))
    return _SCHEMA


def decode_confluent_payload(payload: bytes) -> str | None:
    """Return JSON for a Confluent Avro payload or a legacy JSON payload.

    The five-byte Confluent envelope is checked before Avro decoding. A failed
    decode is represented as a small diagnostic JSON object so the existing
    Spark quality path quarantines it instead of silently dropping it.
    """
    if payload is None:
        return None
    try:
        if len(payload) >= 5 and payload[0] == 0:
            from fastavro import schemaless_reader

            record = schemaless_reader(io.BytesIO(payload[5:]), _schema())
            return json.dumps(record)
        return payload.decode("utf-8")
    except (ImportError, UnicodeDecodeError, ValueError, TypeError, EOFError) as error:
        return json.dumps({"_schema_error": str(error)})
