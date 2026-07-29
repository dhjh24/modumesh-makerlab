# MakerLab Plugin Author Guide

This document defines the **plugin contract** for ModuMesh MakerLab (Phase 3).
Plugins are untrusted code executed by the worker under host-enforced limits.

## Quick start

1. Create a directory under `plugins/<id>/`.
2. Add `plugin.manifest.json` and an input JSON Schema.
3. Implement a Python entrypoint `module:function` that accepts `PluginContext`.
4. Run the contract CLI:

```bash
pip install -e packages/plugin-sdk-py
modumesh-plugin-check check plugins/fixture-echo \
  --input plugins/fixture-echo/fixtures/valid-input.json
```

5. Restart/resync the API — the plugin appears at `GET /api/v1/plugins` with
   **no frontend source changes**.

## Manifest (`plugin.manifest.json`)

Validated against `packages/plugin-sdk/schemas/manifest.v1.json`.

| Field                              | Required | Notes                                         |
| ---------------------------------- | -------- | --------------------------------------------- |
| `schemaVersion`                    | yes      | Must be `"1"`                                 |
| `id`                               | yes      | Lowercase kebab-case; becomes `job_type`      |
| `name`                             | yes      | Human-readable                                |
| `version`                          | yes      | SemVer                                        |
| `sdkVersion`                       | yes      | Target SDK; host accepts same **major**       |
| `engine`                           | yes      | `python` (CadQuery plugins also use `python`) |
| `entrypoint`                       | yes      | `module:function`                             |
| `categories`                       | yes      | Non-empty list                                |
| `outputs`                          | yes      | Declared filenames + media types              |
| `timeoutSeconds`                   | yes      | 1–3600; job timeout is capped by this         |
| `memoryMb`                         | yes      | Best-effort RLIMIT_AS                         |
| `networkPolicy`                    | yes      | `deny` (default) or `allow`                   |
| `inputSchema`                      | yes      | Inline object or relative `.json` path        |
| `maxInputBytes` / `maxOutputBytes` | no       | Defaults 64 KiB / 1 MiB                       |

## Generator input schemas

Every input schema must satisfy `packages/plugin-sdk/schemas/input-rules.v1.json`:

- JSON Schema dialect declared
- `type: object`
- `additionalProperties: false`
- Property names limited; max 64 properties

## SDK context

```python
def run(ctx: PluginContext) -> None:
    ctx.set_progress(10, "starting")
    ctx.log("hello")
    ctx.write_json("echo.json", {"ok": True})
    ctx.write_text("note.txt", "hi\n")
```

Available to plugins:

- `job_id`, `plugin_id`, `plugin_version`, `input`
- `work_dir` — the only writable directory
- `log`, `set_progress`, `register_output` / `write_json` / `write_text`

**Never** available: database DSN, Redis, MinIO keys, Docker socket, host paths
outside `work_dir`.

## Security boundaries

| Control         | Behavior                                                         |
| --------------- | ---------------------------------------------------------------- |
| Plugin source   | Read-only (`:ro` mount / `chmod a-w`)                            |
| Work directory  | Per-job temp dir only                                            |
| Network         | Disabled by default (`networkPolicy=deny` + socket hooks)        |
| Host filesystem | Path traversal rejected; outputs must be single path segments    |
| Docker socket   | Not mounted; `DOCKER_*` stripped; optional hard deny             |
| Credentials     | `POSTGRES_*`, `MINIO_*`, `REDIS_*`, secrets stripped from env    |
| Size limits     | `maxInputBytes` / `maxOutputBytes` enforced                      |
| Outputs         | Must be declared; required outputs enforced; media types checked |
| Timeout         | `min(job.timeout, manifest.timeoutSeconds)`                      |

## Versioning policy

- **Manifest schema**: `schemaVersion` is an integer string. Breaking changes
  bump it (`"1"` → `"2"`). Hosts reject unknown versions.
- **SDK**: SemVer. Hosts accept plugins whose `sdkVersion` **major** matches
  the host major (`1.x` today).
- **Plugin**: SemVer. `(id, version)` is unique. Jobs record the exact
  `plugin_version` and an immutable `input_payload` copy at creation time.

## Compatibility matrix

| Host / SDK                 | Manifest `schemaVersion` | Plugin `sdkVersion` | Engine   |
| -------------------------- | ------------------------ | ------------------- | -------- |
| MakerLab Phase 3 (`1.0.0`) | `1`                      | `1.x`               | `python` |

## Migration rules

1. **Additive fields** on manifest `schemaVersion=1` may be introduced with
   defaults; plugins omit them safely.
2. **Removing / renaming** required fields requires a new `schemaVersion`.
3. **SDK major bump**: old plugins keep running on previous host major until
   retired; authors update `sdkVersion` and re-check with the CLI.
4. **Duplicate `(id, version)`** on disk: both copies are excluded with clear
   diagnostics until resolved.
5. **Enable/disable** is persisted in PostgreSQL and survives rediscovery.

## Example plugins

See `plugins/fixture-echo` (JSON/text), `plugins/fixture-mesh` (packaged STL/GLB),
and `plugins/nameplate` (CadQuery reference generator with STL/STEP/GLB/PNG).

## API surface

| Method | Path                                          | Purpose                  |
| ------ | --------------------------------------------- | ------------------------ |
| GET    | `/api/v1/plugins`                             | List discovered plugins  |
| GET    | `/api/v1/plugins/{id}`                        | Latest (or `?version=`)  |
| POST   | `/api/v1/plugins/resync`                      | Re-scan plugin directory |
| POST   | `/api/v1/plugins/{id}/versions/{ver}/enable`  | Enable                   |
| POST   | `/api/v1/plugins/{id}/versions/{ver}/disable` | Disable                  |
| POST   | `/api/v1/projects/{id}/jobs`                  | `job_type=<plugin_id>`   |

## Contract CLI

```bash
modumesh-plugin-check check <plugin-dir> [--input fixture.json] [--no-run]
modumesh-plugin-check discover <plugins-root>
```
