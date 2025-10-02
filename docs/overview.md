# PhaseBridge: Overview

PhaseBridge is a small, universal **interchange layer** that lets any system move data **losslessly** between a discrete space and a **continuous, phase-based** representation — and back again. It provides a single, modality-agnostic way to express data as phases (θ) on the unit circle with optional amplitudes (A), so different systems (symbolic, neural, hybrid, stream, batch) can **meet in the same continuous space** without losing information.

At its core, PhaseBridge defines:

* **PIF (Phase Interchange Format)**: a strict, versioned on-wire/in-file format that holds the phase representation and the minimal schema needed to reconstruct the original discrete data.
* **Lossless codecs** (starting with `S1PhaseCodec`): exact round-trip transforms `discrete uintM ↔ θ ∈ [0,2π)`.
* **κ (kappa) metrics**: simple, consistent measures of **coherence** in phase space (e.g., ( \kappa = |\langle e^{i\theta}\rangle| )) for routing/health/insight — never modifying data.

> MVP status: **time-series and 8-bit images** (grayscale) with strict round-trip; clean SDK & CLI; windowed κ for series; JSON (and optional MessagePack) PIF serialization.

---

## Why PhaseBridge?

Most pipelines juggle many **discrete** forms (bytes, tokens, categorical tables) and many **continuous** models (embeddings, spectra, latents). Today, each modality tends to invent its own encoders/normalizations and loses the ability to **round-trip** the exact original data.

PhaseBridge solves this with a **single, minimal, lossless bridge**:

* **Same language for all**: Phase space (unit circle) is a compact, universal continuous target.
* **Strict reversibility**: When marked as `no_processing`, decoding must reproduce input **bit-for-bit**.
* **Separation of concerns**: Conversion (lossless) is **separate** from any processing (optional, explicitly labeled).
* **Composable**: Works as an embedded library, a sidecar process, a streaming operator, or a file format in a lake.

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

A minimal, versioned container for phase data:

* `theta: float64[]` — phases wrapped to ([0, 2\pi)).
* `amp: 1.0` (MVP) — amplitude (scalar now; may be an array later).
* `schema.alphabet.type="uint"`, `schema.alphabet.M` — discrete alphabet size (e.g., 256 for 8-bit).
* Optional `schema.sampling.fs` for time series metadata.
* `meta.note="no_processing"` for lossless conversion.
* `meta.hash_raw="sha256:..."` — hash of the original discrete input.
* `meta.codec`, `meta.codec_hash` — codec identity and a stable hash.

Serialization: **JSON** (default) or **MessagePack** (optional).

### S1PhaseCodec (uintM ↔ θ)

* **Encode**: map each symbol (n \in {0,\dots,M-1}) to ( \theta = 2\pi n/M ).
* **Decode**: snap ( \theta ) to the **nearest** grid node; exact integer recovery.
* **Strict range** (default) or modular wrap for inputs beyond ([0,M-1]) if explicitly desired.

### κ (kappa) — coherence

* Global: ( \kappa = \left|\langle e^{i\theta}\rangle\right| \in [0,1] ).
* Windowed: sliding windows over time for local coherence profiles.
* Weighted variant (future): use `amp` if present as weights.

> κ is **diagnostic only**. It never alters data or threatens round-trip guarantees.

---

## What We Guarantee (MVP)

* **Lossless round-trip** for declared alphabets (`uintM`):
  If `meta.note=="no_processing"`, then `decode(encode(x)) == x`.
* **Float64 phases** and consistent phase wrapping; stable nearest-grid decoding.
* **Schema validation** and basic runtime checks (shape, types, ranges).
* **Observability**: consistent κ, raw hashes, codec IDs in metadata.
* **Versioning**: `pif_version` (SemVer) + JSON Schema; backward-compatible minor upgrades.

---

## Quickstart

### Python SDK

```python
import numpy as np
from phasebridge import S1PhaseCodec, PIF, kappa_timeseries

# Discrete input: uint8 array in [0..255]
x = np.arange(0, 256, dtype=np.uint8)

# Build schema and encode
codec = S1PhaseCodec(M=256)
schema = {"alphabet": {"type": "uint", "M": 256}}
p = codec.encode(x, schema)

# Lossless decode
xr = codec.decode(p)
assert np.array_equal(x, xr)

# κ (diagnostic)
k = kappa_timeseries(p)
print("kappa =", k)

# Serialize to JSON
s = p.to_json(indent=2)
p2 = PIF.from_json(s, validate=True)
```

### CLI

```bash
# Encode raw bytes (stdin) -> PIF JSON (stdout)
cat input.bin | pb-encode --in - --in-fmt bin --dtype uint8 --M 256 > out.pif.json

# Decode PIF JSON (stdin) -> raw bytes (stdout)
cat out.pif.json | pb-decode --in - --pif-fmt json --out - --out-fmt bin > recon.bin

# Validate (schema/runtime/hash/round-trip against a raw file)
pb-validate --in out.pif.json --raw input.bin --in-fmt bin --dtype uint8 --report json

# Compute kappa (global or windowed)
pb-kappa --in out.pif.json --fmt plain
pb-kappa --in out.pif.json --win 256 --hop 128 --fmt csv
```

---

## Integration Patterns

* **Embedded SDK** (Python today; others can bind): call `encode`/`decode`/`kappa` in-process.
* **Sidecar** (later): a tiny gRPC/HTTP process offering `/encode`, `/decode`, `/kappa`, `/validate`.
* **Streaming operators** (later): Kafka/Flink connectors (`pif-encode`, `pif-decode`, `pif-kappa`).
* **Data lake**: store PIF objects next to raw; reproducible pipelines (hashes match, schema pinned).

---

## File & Wire Format

* **JSON** (default): human-readable, easy to debug.
* **MessagePack** (optional): compact binary for high-throughput paths.
* **JSON Schema**: `schemas/pif_v1.json` (authoritative) + YAML view.
* **SemVer**: changes to PIF evolve via minor/patch bumps with CI conformance checks.

---

## Security & Privacy Notes

* PIF may carry hashes of raw data. Avoid storing sensitive raw in PIF payloads or derived fields.
* If raw data is sensitive, consider hashing locally and **never** transmitting the raw file; PhaseBridge needs only the discrete input at encode time.
* For integrity, verify `meta.hash_raw` after decode. For authenticity, you can add signatures in future (`meta.sig`).

---

## Performance Notes

* Encode/decode are **O(N)** and vectorized (NumPy).
* θ stored in `float64`; decoding uses nearest-grid snapping (stable and fast).
* For large arrays, prefer MessagePack serialization and binary raw I/O.

---

## Non-Goals (MVP)

* No in-place **processing** in phase space. The MVP strictly separates conversion from any transformation.
* No probabilistic or learned codecs. `S1PhaseCodec` is deterministic and reversible by construction.
* No implicit resampling, filtering, denoising, or compression.

---

## Roadmap

* **Adapters**: Tables, logs/events, graphs, text (token-level `uintM`), multi-channel audio, RGB images.
* **Weighted κ** by amplitude arrays; κ variations per modality (kept read-only).
* **Sidecar service** & **stream connectors**.
* **PIF v1.x**: optional fields for multi-channel layouts, chunked/streaming θ, and signatures.

---

## FAQ

**Q: Why phases?**
A: The unit circle gives a compact, universal continuous space with a natural coherence metric and a **trivial, exact** mapping for finite alphabets. It’s the simplest possible continuous target for lossless interchange.

**Q: Is this just PM/PSK (phase modulation)?**
A: It’s inspired by the same math, but PhaseBridge standardizes a **data interchange format**, a **lossless contract**, and a **coherence interface** across **arbitrary modalities**, with explicit schema/versioning and tooling.

**Q: Do you modify data?**
A: No. When `meta.note="no_processing"`, the platform performs **pure conversion** only. Any future processing must be explicit and labeled.

**Q: Will this work for non-uint data?**
A: Yes, by **quantization to an alphabet** (`uintM`) declared in the schema. The bridge remains lossless **with respect to the declared alphabet**.

**Q: How does κ help?**
A: κ is a lightweight, modality-agnostic signal for **structure vs noise** and can route data between discrete/continuous/hybrid blocks **without changing the data**.

---

If you’re new to the repo, start with:

* `docs/pif_format.md` for the schema details,
* `examples/image_roundtrip.py` and `examples/timeseries_roundtrip.py`,
* `cli/` tools for quick hands-on,
* `tests/` to see exactly what we guarantee.
