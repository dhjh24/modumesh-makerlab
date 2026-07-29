# Rollback Guide

1. Stop API and worker to freeze writes.
2. Redeploy previous image tags for `api`, `worker`, and `web`.
3. If schema changed incompatibly, restore Postgres from the pre-upgrade backup:

```bash
./scripts/restore.sh backups/<pre-upgrade-stamp>
```

4. Restore MinIO only when object keys or buckets diverged.
5. Start services; verify `/health/ready` and admin status.
6. Capture incident notes (correlation IDs, failed job IDs) before retrying the upgrade.
