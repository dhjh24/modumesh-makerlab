# syntax=docker/dockerfile:1
FROM python:3.11-slim
RUN groupadd -r modumesh && useradd -r -g modumesh -d /app -s /bin/false modumesh
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY apps/worker/pyproject.toml apps/worker/
RUN pip install --no-cache-dir -e apps/worker
COPY apps/worker/app/ app/
RUN chown -R modumesh:modumesh /app
USER modumesh
CMD ["python", "-m", "app.main"]
