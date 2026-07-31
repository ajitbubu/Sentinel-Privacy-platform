# Docker

The development stack lives at the **repo root** (`docker-compose.yml`) so that
`docker compose up` works from where you naturally are.

    make up      # or: docker compose up -d --build

`docker-compose.prod.yml` in this directory is the production topology and is
not used for local development.
