# Troubleshooting

| Issue | Likely cause | Action |
|-------|--------------|--------|
| Cannot sign in | Wrong password / inactive user | Reset via bootstrap password on fresh DB or admin user create |
| Empty project list | Owner filtering | Confirm user owns projects; admins see all |
| Plugin resync 403 | Non-admin | Use admin role |
| Worker OOM / killed | CadQuery memory | Raise `mem_limit` / `WORKER_MAX_MEMORY_MB` |
| Read-only FS errors | Worker needs writable temp | Ensure `/tmp` tmpfs; `TMPDIR=/tmp` |
| CORS errors | Origin mismatch | Align `API_CORS_ORIGINS` with the browser origin |
| 413 Payload too large | Body > `API_MAX_REQUEST_BYTES` | Reduce payload or raise limit |
| Checksum mismatch on download | Corrupt object | Re-run job; inspect MinIO object |

Structured JSON logs are emitted by API and worker. Filter by `correlation_id`.
