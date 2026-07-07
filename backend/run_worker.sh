#!/bin/sh
set -eu

if [ -z "${REDIS_URL:-}" ]; then
  echo "REDIS_URL is required for the RQ worker" >&2
  exit 1
fi

# Must match queue names used by core.queue_names (adaptive mode).
QUEUES="${WORKER_QUEUES:-finance-ai ocr_high_priority ocr_normal review transaction}"

echo "Starting RQ worker (redis=${REDIS_URL%%@*}@…, queues=${QUEUES})"
# shellcheck disable=SC2086
exec rq worker --url "$REDIS_URL" $QUEUES