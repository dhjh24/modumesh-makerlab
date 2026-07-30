# Generator Capability and Runtime Contract — ADR

**Status:** Draft

## Context

Generators in MakerLab have different runtime requirements. Some need
CadQuery/VTK for CAD workflows, some use PrusaSlicer for slicing, and
future generators may need GPU for AI inference. The current manifest
schema has a flat `engine` and `capabilities` field but no way to
express hardware tiers, sidecar services, or precise resource contracts.

## Decision

We add a `runtime` block to the plugin manifest that declares:

- `mode`: `"inprocess"` (Python in CI) or `"sidecar"` (init container)
- `hardware`: CPU only, specific GPU tiers, or minimal
- `resources`: explicit min/max for CPU, memory, disk, GPU VRAM
- `sidecars`: list of init containers with image, command, port
- `filesystems`: read paths, write paths, tmpfs size
- `security`: network policy, privilege, capabilities

The block is optional at v1. Generators that omit it default to
in-process CPU mode with the existing `memoryMb` and `networkPolicy`
fields.

## New manifest section

```json
{
  "runtime": {
    "mode": "inprocess",
    "hardware": "cpu",
    "resources": {
      "cpu_cores": {"min": 1, "max": 4},
      "memory_mb": {"min": 128, "max": 2048},
      "disk_mb": {"min": 1, "max": 512}
    },
    "network": {"egress": false},
    "privileged": false
  }
}
```

## GPU tier names

`hardware` values:
- `"cpu"` — standard CPU worker (default)
- `"gpu-low"` — ~4 GB VRAM (T4, GTX 1660)
- `"gpu-medium"` — ~8 GB VRAM (RTX 3070, A10)
- `"gpu-high"` — ~24 GB VRAM (RTX 4090, A100)
- `"gpu-low-fp16"`, `"gpu-medium-fp16"`, `"gpu-high-fp16"` — FP16 tiers

## Sidecar contract

When `mode` is `"sidecar"`, the generator entrypoint is a Docker init
container that communicates with the parent worker over a local port.
The sidecar section specifies:

```json
{
  "sidecars": [
    {
      "name": "meshlab-server",
      "image": "modumesh/meshlab-server:1.0",
      "port": 8500,
      "command": ["meshlabserver", "-s", "/scripts/process.mlx"]
    }
  ]
}
```
