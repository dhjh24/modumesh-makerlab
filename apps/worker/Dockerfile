# syntax=docker/dockerfile:1
FROM python:3.11-slim
WORKDIR /app
COPY apps/worker/pyproject.toml apps/worker/
RUN pip install --no-cache-dir -e apps/worker
COPY apps/worker/app/ app/
CMD ["python", "-m", "app.main"]
