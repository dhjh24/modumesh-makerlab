# syntax=docker/dockerfile:1
FROM python:3.11-slim
RUN groupadd -r modumesh && useradd -r -g modumesh -d /app -s /bin/false modumesh
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY packages/plugin-sdk-py/ packages/plugin-sdk-py/
COPY apps/worker/pyproject.toml apps/worker/
RUN pip install --no-cache-dir -e packages/plugin-sdk-py -e apps/worker
COPY apps/worker/app/ app/
COPY plugins/ /plugins/
# Read-only plugin source for the non-root worker user.
RUN chmod -R a-w /plugins && chown -R modumesh:modumesh /app
USER modumesh
ENV WORKER_PLUGIN_DIR=/plugins
# Do not mount or expose the Docker socket to this image.
ENV MODUMESH_DENY_DOCKER_SOCK=1
CMD ["python", "-m", "app.main"]
