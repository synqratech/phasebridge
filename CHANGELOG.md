# Changelog

All notable changes to this project will be documented in this file.
The project follows [SemVer](https://semver.org/).
PIF format changes are versioned via `pif_version` (v1.x for non-breaking core).

---

## [0.2.0] — 2025-10-24

### Added

* **Lazy PIF (θ on demand)**

  * New payload mode: `theta_lazy: true` + `encoded_uint: integer[]` (no explicit `theta` in storage).
  * `PIF` supports `encoded_uint`, `theta_lazy`, on-demand materialization via `theta_view`.
* **Numeric policy (float32 / float64)**

  * `numeric: { dtype: "float32"|"float64", precision_safe?: boolean, phase_wrap?: [0,2π) }`.
  * Conservative **float32-safe** zone: `M ≤ 65,536`.
  * Decoding remains float64 for nearest-grid snapping (robust round-trip).
* **Binary formats**

  * `PIF.to_bytes(fmt)` / `PIF.from_bytes(fmt)` with `fmt ∈ {"msgpack","cbor","npz"}`.
  * Unified ndarray packing (`{"__nd__":true,"dtype","shape","data":<bytes>}`) for MessagePack/CBOR.
  * NPZ container: `schema.json`, `meta.json`, optional `numeric.json`, `flags.json`, and one of `theta.npy`/`encoded_uint.npy`, plus `amp.npy` or `amp.json`.
* **CLI**

  * `pb-encode`: `--lazy`, `--prefer-float32`, `--no-downgrade`; `--pif-fmt {json,msgpack,cbor,npz}`.
  * `pb-decode`, `pb-kappa`, `pb-validate`: extended `--pif-fmt` with `cbor` and `npz`.
* **SDK helpers**

  * `utils`: `choose_phase_dtype`, `is_float32_safe_for_M`, `pack_ndarray`, `unpack_ndarray`.
  * `wrap_phase(theta, dtype=...)`, `grid_phases_from_uint(..., dtype=...)`.
* **Serialization errors**

  * New exceptions: `SerializationError`, `UnsupportedFormatError`.

### Changed

* **Schemas** (`schemas/pif_v1.json`, `schemas/pif_v1.yaml`)

  * Top-level `oneOf`: either **Eager θ** (`theta` present) **or** **Lazy θ** (`theta_lazy: true` + `encoded_uint`).
  * `numeric.dtype` enum (`float32|float64`), `numeric.precision_safe` boolean.
* **`S1PhaseCodec.encode`**

  * Signature extended: `encode(..., lazy_theta=False, prefer_float32=False, allow_downgrade=True)`.
  * Embeds `numeric` according to chosen dtype and `precision_safe`.
* **`kappa`**

  * Respects θ dtype; avoids unconditional float64 casts internally (final κ is still a float).

### Performance

* **I/O**: Binary formats (MessagePack/CBOR/NPZ) deliver ~×10–×50 faster load/save vs JSON on large arrays.
* **Memory**: `lazy + float32` halves θ memory footprint (and skips θ allocation entirely for lazy).

### Compatibility

* **Backward compatible** with prior eager-θ JSON PIFs (float64).
* Consumers **must** accept both payload modes (eager/lazy) and the updated `numeric` section.
* Old MessagePack readers that expect raw lists for `theta` may need to adopt the ndarray packing rule.

### Documentation

* **Removed “float64-only”** claim; documented numeric policy and lazy mode.
* Updated: `docs/pif_format.md`, `docs/cli_usage.md`, `README.md` with lazy+float32+binary defaults and examples.

### Security

* No changes to integrity model: `meta.hash_raw` recommended; verify on decode.
* Binary containers do not embed raw input; hashes enable end-to-end verification.

---

## [0.1.0] — 2025-10-01

### Added

* **Core SDK**

  * `PIF` dataclass with strict runtime validation.
  * `S1PhaseCodec` (uintM ↔ θ) with strict round-trip guarantees.
  * κ metrics: `kappa_timeseries`, `kappa_timeseries_windowed`.
  * Schema helpers: default JSON Schema, runtime validation APIs.
  * Utilities: SHA-256 helpers, dtype selection, phase wrapping.
* **CLI**

  * `pb-encode`: raw (bin/csv/npy) → PIF (json/msgpack).
  * `pb-decode`: PIF → raw (bin/csv/npy).
  * `pb-kappa`: compute global/windowed κ from PIF.
  * `pb-validate`: schema/runtime validation, decode, hash checks, optional raw comparison.
* **Schemas**

  * `schemas/pif_v1.json` (authoritative) and `schemas/pif_v1.yaml` mirror.
* **Docs**

  * `docs/overview.md`, `pif_format.md`, `cli_usage.md`.
* **Examples & Demos**

  * `examples/timeseries_roundtrip.py` — CSV (uint) ↔ PIF ↔ CSV, κ.
  * `examples/image_roundtrip.py` — 8-bit grayscale image ↔ PIF ↔ image, κ.
  * `demo/roundtrip_image.ipynb`, `demo/roundtrip_timeseries.ipynb`.
* **Tests**

  * Round-trip, κ bounds, schema/runtime validation, API contract.
  * Property test (optional, with `hypothesis`).

### Security

* Documented security policy (`SECURITY.md`), hash-based integrity (`meta.hash_raw`).

---

## [Unreleased]

### Planned

* Adapters: tables, text tokens, RGB, audio.
* Sidecar service (HTTP/gRPC) and streaming operators.
* Extended PIF v1.x optional fields (multi-channel, chunking).
* Language bindings (Go/C++/Rust).

---
