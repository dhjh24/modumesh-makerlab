# syntax=docker/dockerfile:1
FROM python:3.11-slim AS builder
WORKDIR /build
COPY packages/plugin-sdk-py/ packages/plugin-sdk-py/
COPY apps/api/pyproject.toml apps/api/
RUN pip install --no-cache-dir build \
    && python -m build --wheel packages/plugin-sdk-py \
    && cd apps/api && python -m build --wheel

FROM python:3.11-slim
RUN groupadd -r modumesh && useradd -r -g modumesh -d /app -s /bin/false modumesh
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY --from=builder /build/packages/plugin-sdk-py/dist/*.whl /tmp/
COPY --from=builder /build/apps/api/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -f /tmp/*.whl
COPY apps/api/app/ app/
COPY apps/api/alembic/ alembic/
COPY apps/api/alembic.ini .
COPY apps/api/tests/ tests/
# Plugins are copied read-only into the image; compose may also bind-mount.
COPY plugins/ /plugins/
RUN find /plugins -type f -exec chmod 644 {} + && chmod -R a-w /plugins && chown -R modumesh:modumesh /app && mkdir -p /tmp/prometheus-metrics && chown -R modumesh:modumesh /tmp/prometheus-metrics
USER modumesh
ENV API_PLUGIN_DIR=/plugins
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
