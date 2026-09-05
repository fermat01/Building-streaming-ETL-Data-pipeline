#!/usr/bin/env bash

set -euo pipefail

: "${KAFKA_ADMIN_USERNAME:?KAFKA_ADMIN_USERNAME is required}"
: "${KAFKA_ADMIN_PASSWORD:?KAFKA_ADMIN_PASSWORD is required}"
: "${KAFKA_PRODUCER_USERNAME:?KAFKA_PRODUCER_USERNAME is required}"
: "${KAFKA_PRODUCER_PASSWORD:?KAFKA_PRODUCER_PASSWORD is required}"
: "${KAFKA_CONSUMER_USERNAME:?KAFKA_CONSUMER_USERNAME is required}"
: "${KAFKA_CONSUMER_PASSWORD:?KAFKA_CONSUMER_PASSWORD is required}"
: "${KAFKA_CONNECT_USERNAME:?KAFKA_CONNECT_USERNAME is required}"
: "${KAFKA_CONNECT_PASSWORD:?KAFKA_CONNECT_PASSWORD is required}"
: "${KAFKA_SCHEMA_REGISTRY_USERNAME:?KAFKA_SCHEMA_REGISTRY_USERNAME is required}"
: "${KAFKA_SCHEMA_REGISTRY_PASSWORD:?KAFKA_SCHEMA_REGISTRY_PASSWORD is required}"
: "${KAFKA_UI_USERNAME:?KAFKA_UI_USERNAME is required}"
: "${KAFKA_UI_PASSWORD:?KAFKA_UI_PASSWORD is required}"

for attempt in $(seq 1 36); do
    if cub zk-ready zookeeper:2181 10 >/dev/null 2>&1; then
        break
    fi
    if [ "${attempt}" -eq 36 ]; then
        echo "ERROR: ZooKeeper did not become ready within three minutes."
        exit 1
    fi
    sleep 5
done

set_scram_password() {
    local username="$1"
    local password="$2"
    kafka-configs \
        --zookeeper zookeeper:2181 \
        --alter \
        --add-config "SCRAM-SHA-256=[password=${password}]" \
        --entity-type users \
        --entity-name "${username}"
}

set_scram_password "${KAFKA_ADMIN_USERNAME}" "${KAFKA_ADMIN_PASSWORD}"
set_scram_password "${KAFKA_PRODUCER_USERNAME}" "${KAFKA_PRODUCER_PASSWORD}"
set_scram_password "${KAFKA_CONSUMER_USERNAME}" "${KAFKA_CONSUMER_PASSWORD}"
set_scram_password "${KAFKA_CONNECT_USERNAME}" "${KAFKA_CONNECT_PASSWORD}"
set_scram_password "${KAFKA_SCHEMA_REGISTRY_USERNAME}" "${KAFKA_SCHEMA_REGISTRY_PASSWORD}"
set_scram_password "${KAFKA_UI_USERNAME}" "${KAFKA_UI_PASSWORD}"

echo "Kafka SCRAM credentials initialized."
