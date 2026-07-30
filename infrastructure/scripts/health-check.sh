#!/usr/bin/env bash
for url in http://localhost:8001 http://localhost:8002 http://localhost:8003; do
  status=$(curl -s -o /dev/null -w "%{http_code}" "$url/api/v1/health" || echo "DOWN")
  echo "$url -> $status"
done
