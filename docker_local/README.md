# Local services (Tika, Qdrant, Redis, MinIO)

This folder contains a simple `docker-compose.yml` for running:
- Apache Tika (document parsing)
- Qdrant (vector DB)
- Redis
- MinIO (S3-compatible storage)

## How to start

From this directory:

```bash
docker compose up -d
```

## Expected ports on the host

- Tika: `http://localhost:9998`
- Qdrant HTTP: `http://localhost:6333`
- Qdrant gRPC: `localhost:6334`
- Redis: `localhost:6379`
- MinIO S3: `http://localhost:9000`
- MinIO Console: `http://localhost:9001`

## MinIO credentials

By default MinIO uses:
- `MINIO_ROOT_USER=minioadmin`
- `MINIO_ROOT_PASSWORD=minioadmin`

You can override them by creating `docker_local/.env` with these variables.

