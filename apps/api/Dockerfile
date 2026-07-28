# syntax=docker/dockerfile:1
FROM python:3.11-slim AS builder
WORKDIR /app
COPY apps/api/pyproject.toml apps/api/
RUN pip install --no-cache-dir build && cd apps/api && python -m build --wheel

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /app/apps/api/dist/*.whl .
RUN pip install --no-cache-dir *.whl
COPY apps/api/app/ app/
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
