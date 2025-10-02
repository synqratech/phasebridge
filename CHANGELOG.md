# Changelog

All notable changes to this project will be documented in this file.

The project follows [SemVer](https://semver.org/).  
PIF format changes are versioned via `pif_version` (v1.x for non-breaking core).

---

## [0.1.0] — 2025-10-01

### Added

- **Core SDK**
  - `PIF` dataclass with strict runtime validation.
  - `S1PhaseCodec` (uintM ↔ θ) with strict round-trip guarantees.
  - κ metrics: `kappa_timeseries`, `kappa_timeseries_windowed`.
  - Schema helpers: default JSON Schema, runtime validation APIs.
  - Utilities: SHA-256 helpers, dtype selection, phase wrapping.

- **CLI**
  - `pb-encode`: raw (bin/csv/npy) → PIF (json/msgpack).
  - `pb-decode`: PIF → raw (bin/csv/npy).
  - `pb-kappa`: compute global/windowed κ from PIF.
  - `pb-validate`: schema/runtime validation, decode, hash checks, optional raw comparison.

- **Schemas**
  - `schemas/pif_v1.json` (authoritative) and `schemas/pif_v1.yaml` mirror.

- **Docs**
  - `docs/overview.md`, `pif_format.md`, `cli_usage.md`.

- **Examples & Demos**
  - `examples/timeseries_roundtrip.py` — CSV (uint) ↔ PIF ↔ CSV, κ.
  - `examples/image_roundtrip.py` — 8-bit grayscale image ↔ PIF ↔ image, κ.
  - `demo/roundtrip_image.ipynb`, `demo/roundtrip_timeseries.ipynb`.

- **Tests**
  - Round-trip, κ bounds, schema/runtime validation, API contract.
  - Property test (optional, with `hypothesis`).

### Security

- Documented security policy (`SECURITY.md`), hash-based integrity (`meta.hash_raw`).

---

## [Unreleased]

### Planned

- Adapters: tables, text tokens, RGB, audio.
- Sidecar service (HTTP/gRPC) and streaming operators.
- Extended PIF v1.x optional fields (multi-channel, chunking).
- Language bindings (Go/C++/Rust).

---

### Notes

- JSON is the normative on-wire format; MessagePack is optional and equivalent.
- θ values are **float64** wrapped to `[0, 2π)`; decoding uses nearest-grid snapping.
