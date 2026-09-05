#!/usr/bin/env bash

set -euo pipefail

: "${KAFKA_ADMIN_USERNAME:?KAFKA_ADMIN_USERNAME is required}"
: "${KAFKA_ADMIN_PASSWORD:?KAFKA_ADMIN_PASSWORD is required}"
: "${KAFKA_PRODUCER_USERNAME:?KAFKA_PRODUCER_USERNAME is required}"
: "${KAFKA_CONSUMER_USERNAME:?KAFKA_CONSUMER_USERNAME is required}"
: "${KAFKA_CONSUMER_GROUP_ID:?KAFKA_CONSUMER_GROUP_ID is required}"
: "${KAFKA_CONNECT_USERNAME:?KAFKA_CONNECT_USERNAME is required}"
: "${KAFKA_SCHEMA_REGISTRY_USERNAME:?KAFKA_SCHEMA_REGISTRY_USERNAME is required}"
: "${KAFKA_UI_USERNAME:?KAFKA_UI_USERNAME is required}"

CLIENT_PROPERTIES=$(mktemp)
trap 'rm -f "${CLIENT_PROPERTIES}"' EXIT
cat > "${CLIENT_PROPERTIES}" <<EOF
security.protocol=SASL_PLAINTEXT
sasl.mechanism=SCRAM-SHA-256
sasl.jaas.config=org.apache.kafka.common.security.scram.ScramLoginModule required username="${KAFKA_ADMIN_USERNAME}" password="${KAFKA_ADMIN_PASSWORD}";
EOF

BOOTSTRAP_SERVERS="broker-1:9092,broker-2:9093,broker-3:9094"

for attempt in $(seq 1 36); do
    if kafka-broker-api-versions \
        --bootstrap-server "${BOOTSTRAP_SERVERS}" \
        --command-config "${CLIENT_PROPERTIES}" >/dev/null 2>&1; then
        break
    fi
    if [ "${attempt}" -eq 36 ]; then
        echo "ERROR: Kafka did not become ready within three minutes."
        exit 1
    fi
    sleep 5
done

create_topic() {
    kafka-topics \
        --bootstrap-server "${BOOTSTRAP_SERVERS}" \
        --command-config "${CLIENT_PROPERTIES}" \
        --create \
        --if-not-exists \
        "$@"
}

authorize() {
    kafka-acls \
        --bootstrap-server "${BOOTSTRAP_SERVERS}" \
        --command-config "${CLIENT_PROPERTIES}" \
        --add \
        "$@"
}

create_topic \
    --topic streaming-topic \
    --partitions 3 \
    --replication-factor 3 \
    --config min.insync.replicas=2 \
    --config cleanup.policy=delete \
    --config retention.ms=604800000

create_topic \
    --topic docker-connect-configs \
    --partitions 1 \
    --replication-factor 3 \
    --config cleanup.policy=compact

create_topic \
    --topic docker-connect-offsets \
    --partitions 25 \
    --replication-factor 3 \
    --config cleanup.policy=compact

create_topic \
    --topic docker-connect-status \
    --partitions 5 \
    --replication-factor 3 \
    --config cleanup.policy=compact

create_topic \
    --topic _schemas \
    --partitions 1 \
    --replication-factor 3 \
    --config cleanup.policy=compact

# Airflow can write only to the application topic and inspect its metadata.
authorize --allow-principal "User:${KAFKA_PRODUCER_USERNAME}" --operation WRITE --operation DESCRIBE --topic streaming-topic

# Spark can read the application topic and its fixed consumer group.
authorize --allow-principal "User:${KAFKA_CONSUMER_USERNAME}" --operation READ --operation DESCRIBE --topic streaming-topic
authorize --allow-principal "User:${KAFKA_CONSUMER_USERNAME}" --operation READ --group "${KAFKA_CONSUMER_GROUP_ID}"

# Kafka Connect owns only its internal topics and worker group.
for topic in docker-connect-configs docker-connect-offsets docker-connect-status; do
    authorize --allow-principal "User:${KAFKA_CONNECT_USERNAME}" --operation READ --operation WRITE --operation DESCRIBE --topic "${topic}"
done
authorize --allow-principal "User:${KAFKA_CONNECT_USERNAME}" --operation READ --group compose-connect-group
authorize --allow-principal "User:${KAFKA_CONNECT_USERNAME}" --operation DESCRIBE --cluster

# Schema Registry owns the compacted schema topic.
authorize --allow-principal "User:${KAFKA_SCHEMA_REGISTRY_USERNAME}" --operation READ --operation WRITE --operation DESCRIBE --topic _schemas
authorize --allow-principal "User:${KAFKA_SCHEMA_REGISTRY_USERNAME}" --operation DescribeConfigs --topic _schemas
authorize --allow-principal "User:${KAFKA_SCHEMA_REGISTRY_USERNAME}" --operation READ --group schema-registry

# Kafka UI is read-only across topics and can inspect cluster metadata.
authorize --allow-principal "User:${KAFKA_UI_USERNAME}" --operation READ --operation DESCRIBE --topic '*'
authorize --allow-principal "User:${KAFKA_UI_USERNAME}" --operation DESCRIBE --cluster

echo "Kafka topics and ACLs initialized."
kafka-topics --bootstrap-server "${BOOTSTRAP_SERVERS}" --command-config "${CLIENT_PROPERTIES}" --describe --topic streaming-topic
kafka-topics --bootstrap-server "${BOOTSTRAP_SERVERS}" --command-config "${CLIENT_PROPERTIES}" --describe --topic docker-connect-configs
kafka-topics --bootstrap-server "${BOOTSTRAP_SERVERS}" --command-config "${CLIENT_PROPERTIES}" --describe --topic docker-connect-offsets
kafka-topics --bootstrap-server "${BOOTSTRAP_SERVERS}" --command-config "${CLIENT_PROPERTIES}" --describe --topic docker-connect-status
