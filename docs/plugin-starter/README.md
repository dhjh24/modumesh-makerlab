# MakerLab Community Plugin Starter

Use this template to create a new generator plugin for ModuMesh MakerLab.

## Directory structure

```
plugins/<your-plugin-id>/
├── plugin.manifest.json    # Required: plugin identity, capabilities, outputs
├── input.schema.json       # Required: JSON Schema for user parameters
├── pyproject.toml          # Required: Python package metadata and dependencies
├── src/
│   ├── __init__.py         # Package marker
│   └── <your_plugin_id>/
│       ├── __init__.py
│       └── plugin.py       # Required: entrypoint function
├── fixtures/
│   └── valid-input.json    # Recommended: test fixture
├── templates/              # Optional: static template files
└── assets/                 # Optional: bundled assets (thumbnails, etc.)
```

## Quick start

```bash
# 1. Copy the starter
cp -r docs/plugin-starter/template plugins/my-generator

# 2. Edit plugin.manifest.json — set your id, name, version, outputs
# 3. Edit input.schema.json — define your parameter schema
# 4. Implement src/my_generator/plugin.py

# 5. Validate locally
pip install -e packages/plugin-sdk-py
modumesh-plugin-check check plugins/my-generator \
  --input plugins/my-generator/fixtures/valid-input.json

# 6. Run a generation job
curl -X POST http://localhost:8002/api/v1/plugins/resync
curl -X POST http://localhost:8002/api/v1/projects/<id>/jobs \
  -H 'Content-Type: application/json' \
  -d '{"job_type":"my-generator","input_payload":{...}}'
```

## Submission checklist

Before submitting a community plugin, verify:

- [ ] `plugin.manifest.json` includes `author`, `license` (SPDX), and `sourceUrl`
- [ ] `input.schema.json` has `additionalProperties: false`
- [ ] Entrypoint function accepts `ctx: PluginContext` and uses `ctx.set_progress()`
- [ ] All declared outputs are generated
- [ ] Plugin runs with `networkPolicy: deny` (no outbound network calls)
- [ ] No hard-coded paths, credentials, or secrets
- [ ] Tested with `modumesh-plugin-check check`
- [ ] Tested with a real generation job through the API
