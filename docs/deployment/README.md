# Deployment

- Local: `docker compose -f infrastructure/docker/docker-compose.yml up -d`
- K8s:   `./infrastructure/scripts/deploy.sh <env> <pmp|idp|api|all>`
- Health: `./infrastructure/scripts/health-check.sh`
- Deploy order: migrations -> external-api -> backends -> frontends
