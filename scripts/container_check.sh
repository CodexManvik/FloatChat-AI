#!/usr/bin/env bash
# Start the API image, fire 20 questions, and fail if memory exceeds the 512 MB free-tier budget.
# Usage: scripts/container_check.sh <image> <reader-database-url>
set -euo pipefail
IMAGE="$1"
DATABASE_URL="$2"
NAME=floatchat-api-check
LIMIT_MB=350

docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run -d --name "$NAME" --network host -e DATABASE_URL="$DATABASE_URL" \
  -e QUERY_LIMIT_PER_MINUTE=1000 -e QUERY_LIMIT_PER_DAY=1000 "$IMAGE" >/dev/null
trap 'docker logs "$NAME" | tail -30; docker rm -f "$NAME" >/dev/null' EXIT

for _ in $(seq 1 60); do curl -sf localhost:8000/ping >/dev/null && break; sleep 1; done
curl -sf localhost:8000/health | tee /dev/stderr | grep -q '"status":"healthy"'

QUESTIONS=("What is the average temperature at different depths?"
           "Show me profiles in the Arabian Sea"
           "Compare surface temperature across ocean regions"
           "Which floats measured low oxygen?")
for i in $(seq 0 19); do
  q="${QUESTIONS[$((i % 4))]} $i"
  curl -sf -X POST localhost:8000/query -H 'Content-Type: application/json' \
    -d "{\"query_text\": \"$q\"}" >/dev/null
done

# Count memory the kernel cannot reclaim (cgroup v2 "anon"). `docker stats` also counts cached
# file pages (model file, data), which are freed under memory pressure and would overstate usage.
mib=$(docker exec "$NAME" sh -c 'grep "^anon " /sys/fs/cgroup/memory.stat' | awk '{print int($2 / 1048576)}')
echo "API memory after 20 questions: ${mib} MiB non-reclaimable (limit ${LIMIT_MB} MiB)"
[ "$mib" -le "$LIMIT_MB" ]
