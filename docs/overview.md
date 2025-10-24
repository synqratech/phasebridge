# PhaseBridge: Overview

PhaseBridge is a small, universal **interchange layer** that lets any system move data **losslessly** between a discrete space and a **continuous, phase-based** representation — and back again. It provides a single, modality-agnostic way to express data as phases (θ) on the unit circle with optional amplitudes (A), so different systems (symbolic, neural, hybrid, stream, batch) can **meet in the same continuous space** without losing information.

At its core, PhaseBridge defines:

* **PIF (Phase Interchange Format)**: a strict, versioned on-wire/in-file format that holds the phase representation (eager θ **or** lazy indices) and the minimal schema needed to reconstruct the original discrete data.
* **Lossless codecs** (starting with `S1PhaseCodec`): exact round-trip transforms `discrete uintM ↔ θ ∈ [0,2π)`.
* **κ (kappa) metrics**: simple, consistent measures of **coherence** in phase space (e.g., κ = |⟨e^{iθ}⟩|) for routing/health/insight — never modifying data.

> **MVP status:** time-series and 8-bit images (grayscale) with strict round-trip; **lazy-PIF**, **numeric policy (float32/float64)**, **binary I/O** (MessagePack/CBOR/NPZ), clean SDK & CLI, windowed κ for series.

---

## Why PhaseBridge?

Most pipelines juggle many **discrete** forms (bytes, tokens, categorical tables) and many **continuous** models (embeddings, spectra, latents). Each modality tends to invent its own encoders/normalizations and loses the ability to **round-trip** the exact original data.

PhaseBridge solves this with a **single, minimal, lossless bridge**:

* **Same language for all:** Phase space (unit circle) is a compact, universal continuous target.
* **Strict reversibility:** When marked as `no_processing`, decoding must reproduce input **bit-for-bit** (for the declared alphabet).
* **Separation of concerns:** Conversion (lossless) is **separate** from any processing (optional, explicitly labeled).
* **Composable:** Works as an embedded library, a sidecar process, a streaming operator, or a file format in a lake.

---

## Design Principles

1. **Lossless by default**
   For PIF objects with `meta.note="no_processing"`, the library guarantees `decode(encode(x)) == x` (bit-exact for the declared alphabet).

2. **Minimal, explicit schema**
   Only the essentials needed for reconstruction (e.g., `alphabet.M`, optional `sampling.fs`) — in a versioned PIF schema.

3. **Modality-agnostic core**
   Start with time series and 8-bit images; the same contract generalizes to tables, logs, events, graphs, and text (with appropriate adapters).

4. **Clear boundary: conversion vs processing**
   Conversion is strict and idempotent. Any future processing must be opt-in and labeled `meta.note="processed:<ops>"`.

5. **Simple, observable metrics**
   κ (coherence) is a read-only measurement to diagnose structure vs noise or drive phase routing, never altering payload.

---

## Core Concepts

### PIF (Phase Interchange Format)

A minimal, versioned container for phase data. Two equivalent payload modes:

* **Eager θ**

  * `theta: float32[] | float64[]` — phases wrapped to `[0, 2π)`.
  * `numeric.dtype ∈ {"float32","float64"}` and optional `numeric.precision_safe: boolean`.
  * If `numeric` omitted, default is `"float64"`.

* **Lazy θ**

  * `theta_lazy: true`, `encoded_uint: integer[]` — **no explicit θ stored**.
  * Consumers materialize `θ = (2π/M)·n` on demand in `numeric.dtype` (default float64).
  * This drastically reduces size on wire/disk and avoids θ allocation.

Common fields:

* `amp: 1.0` (MVP) — amplitude (scalar now; may be an array later).
* `schema.alphabet.type="uint"`, `schema.alphabet.M` — discrete alphabet size (e.g., 256 for 8-bit).
* Optional `schema.sampling.fs` for time series metadata.
* `numeric.phase_wrap` (optional, default `[0, 2π)`).
* `meta.note="no_processing"` for lossless conversion.
* `meta.hash_raw="sha256:..."` — integrity hash of the original discrete input.
* `meta.codec`, `meta.codec_hash` — codec identity and a stable hash.

**Serialization:** **JSON** (text) and **binary** formats — **MessagePack**, **CBOR**, **NPZ**.
For MessagePack/CBOR, ndarrays are packed as `{"__nd__": true, "dtype", "shape", "data": <bytes>}`.
NPZ stores `schema.json`, `meta.json`, optional `numeric.json`, `flags.json`, and exactly one of `theta.npy` / `encoded_uint.npy`, plus `amp.npy` or `amp.json`.

### S1PhaseCodec (uintM ↔ θ)

* **Encode:** map each symbol (n ∈ {0,…,M−1}) to θ = (2π/M)·n.

  * Supports **lazy** mode (store `encoded_uint`, defer θ) and **numeric policy** (`float32` vs `float64` with safety).
* **Decode:** nearest-grid snapping: n = round(M·θ / 2π) mod M.

  * Decoding uses float64 arithmetic for robustness even if θ is float32.

### κ (kappa) — coherence

* Global: κ = |⟨e^{iθ}⟩| ∈ [0,1].
* Windowed: sliding windows over time for local coherence profiles.
* Weighted variant: use `amp` as weights if `amp` is an array.

> κ is **diagnostic only**. It never alters data or threatens round-trip guarantees.

---

## What We Guarantee (MVP)

* **Lossless round-trip** for declared alphabets (`uintM`):
  If `meta.note=="no_processing"`, then `decode(encode(x)) == x`.

* **Numeric policy**

  * θ MAY be `float32` (with **conservative safety** `M ≤ 65536` → `precision_safe=true`) or `float64`.
  * Consumers decode with float64 rounding for nearest-grid snapping.

* **Lazy PIF**

  * `theta_lazy=true` + `encoded_uint`, with on-demand θ materialization in the declared/implicit dtype.

* **Schema validation** and basic runtime checks (shapes, types, ranges).

* **Observability:** consistent κ, raw hashes, codec IDs in metadata.

* **Versioning:** `pif_version` (SemVer) + JSON Schema; backward-compatible minor upgrades.

---

## Quickstart

### Python SDK

```python
import numpy as np
from phasebridge import S1PhaseCodec, PIF, kappa_timeseries

# Discrete input: uint8 array in [0..255]
x = np.arange(0, 256, dtype=np.uint8)

codec = S1PhaseCodec(M=256)
schema = {"alphabet": {"type": "uint", "M": 256}}

# 1) Eager θ (float64 by default)
p = codec.encode(x, schema)
xr = codec.decode(p)
assert np.array_equal(x, xr)
print("kappa (eager):", kappa_timeseries(p))

# 2) Lazy θ + prefer float32 (safe for M ≤ 65536)
p_lazy = codec.encode(x, schema, lazy_theta=True, prefer_float32=True, allow_downgrade=True)
print("theta dtype on materialize:", p_lazy.theta_view.dtype)

# 3) Binary round-trip (CBOR / MessagePack / NPZ)
blob = p_lazy.to_bytes(fmt="cbor")
p_lazy2 = PIF.from_bytes(blob, fmt="cbor", validate=True)
assert np.array_equal(codec.decode(p_lazy2), x)
```

### CLI

```bash
# Encode raw bytes (stdin) -> PIF (lazy + prefer float32) in MessagePack
cat input.bin | pb-encode --in - --in-fmt bin --dtype uint8 --M 256 \
  --lazy --prefer-float32 --pif-fmt msgpack > out_lazy.pif.mpk

# Decode PIF (any format) -> raw bytes
pb-decode --in out_lazy.pif.mpk --pif-fmt msgpack --out recon.bin --out-fmt bin

# Validate (schema/runtime/hash) with NPZ
pb-validate --in out_lazy.pif.npz --pif-fmt npz --report json

# κ (global/windowed) from CBOR
pb-kappa --in out_lazy.pif.cbor --pif-fmt cbor --fmt plain
pb-kappa --in out_lazy.pif.cbor --pif-fmt cbor --win 256 --hop 128 --fmt csv
```

---

## Integration Patterns

* **Embedded SDK** (Python today; others can bind): call `encode`/`decode`/`kappa` in-process.
* **Sidecar** (later): a tiny gRPC/HTTP process offering `/encode`, `/decode`, `/kappa`, `/validate`.
* **Streaming operators** (later): Kafka/Flink connectors (`pif-encode`, `pif-decode`, `pif-kappa`).
* **Data lake:** store PIF objects next to raw; reproducible pipelines (hashes match, schema pinned).

---

## File & Wire Format

* **JSON** (default; human-readable).
* **Binary:** **MessagePack**, **CBOR**, **NPZ** for high-throughput paths and compact storage.
* **JSON Schema:** `schemas/pif_v1.json` (authoritative) + YAML mirror.
* **SemVer:** changes to PIF evolve via minor/patch bumps with CI conformance checks.

---

## Security & Privacy Notes

* PIF may carry hashes of raw data. Avoid storing sensitive raw in PIF payloads or derived fields.
* If raw data is sensitive, hash locally and **never** transmit the raw file; PhaseBridge needs only the discrete input at encode time.
* For integrity, verify `meta.hash_raw` after decode. For authenticity, add signatures later (e.g., `meta.sig`).

---

## Performance Notes

* Encode/decode are **O(N)** and vectorized (NumPy).
* **Lazy + float32** can cut memory/IO significantly (no θ array stored; θ materialized in float32 when safe).
* **Binary formats** (MessagePack/CBOR/NPZ) are typically ×10–×50 faster for large arrays vs plain JSON.

---

## Non-Goals (MVP)

* No in-place **processing** in phase space. The MVP strictly separates conversion from any transformation.
* No probabilistic or learned codecs. `S1PhaseCodec` is deterministic and reversible by construction.
* No implicit resampling, filtering, denoising, or compression.

---

## Roadmap

* **Adapters:** tables, logs/events, graphs, text (token-level `uintM`), multi-channel audio, RGB images.
* **Weighted κ** by amplitude arrays; κ variations per modality (kept read-only).
* **Sidecar service** & **stream connectors**.
* **PIF v1.x:** optional fields for multi-channel layouts, chunked/streaming θ, and signatures.

---

## FAQ

**Q: Why phases?**
A: The unit circle gives a compact, universal continuous space with a natural coherence metric and a **trivial, exact** mapping for finite alphabets. It’s the simplest possible continuous target for lossless interchange.

**Q: Is this just PM/PSK (phase modulation)?**
A: It’s inspired by the same math, but PhaseBridge standardizes a **data interchange format**, a **lossless contract**, and a **coherence interface** across **arbitrary modalities**, with explicit schema/versioning and tooling.

**Q: Do you modify data?**
A: No. When `meta.note="no_processing"`, the platform performs **pure conversion** only. Any future processing must be explicit and labeled.

**Q: Will this work for non-uint data?**
A: Yes, via **quantization to an alphabet** (`uintM`) declared in the schema. The bridge remains lossless **with respect to the declared alphabet**.

**Q: How does κ help?**
A: κ is a lightweight, modality-agnostic signal for **structure vs noise** and can route data between discrete/continuous/hybrid blocks **without changing the data**.

---

If you’re new to the repo, start with:

* `docs/pif_format.md` for the schema details,
* `examples/image_roundtrip.py` and `examples/timeseries_roundtrip.py`,
* `cli/` tools for quick hands-on,
* `tests/` to see exactly what we guarantee.
