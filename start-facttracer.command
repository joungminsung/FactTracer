#!/bin/zsh
set -e

cd "$(dirname "$0")"

docker compose up --build -d

for _ in {1..120}; do
  if curl -fsS http://localhost:3000 >/dev/null 2>&1; then
    open http://localhost:3000
    docker compose logs -f
    exit 0
  fi
  sleep 1
done

docker compose ps
echo "FactTracer web did not become ready within 120 seconds."
exit 1
