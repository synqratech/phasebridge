# PhaseBridge — Lossless Discrete ↔ Phase ↔ Discrete

**PhaseBridge** is a tiny, universal interchange layer that lets any system move data **losslessly** between a discrete space and a **continuous, phase-based** representation — and back again. It standardizes a strict, reversible mapping `uintM ↔ θ ∈ [0, 2π)` with a minimal schema, clean SDK, CLI tools, and conformance tests.

* **Lossless by default**: when `meta.note="no_processing"`, `decode(encode(x)) == x` (bit-exact for the declared alphabet).
* **Lazy-PIF**: store compact **indices** (`encoded_uint`) with `theta_lazy=true`; materialize `θ` on demand.
* **Numeric policy**: `θ` may be **float32** (with `precision_safe=true` for the conservative safe zone `M ≤ 65536`) or **float64**.
* **Binary formats**: first-class I/O via **MessagePack**, **CBOR**, and **NPZ** in addition to JSON.
* **Separation of concerns**: conversion is strict and idempotent; any processing must be explicit and labeled.
* **Observable**: κ (coherence) as a read-only diagnostic signal.

> MVP supports time series and 8-bit grayscale images. More modalities (tables, RGB, audio, tokens, logs) are planned.

---

## Contents

- [PhaseBridge — Lossless Discrete ↔ Phase ↔ Discrete](#phasebridge--lossless-discrete--phase--discrete)
  - [Contents](#contents)
  - [Install](#install)
  - [Quickstart](#quickstart)
    - [Python SDK](#python-sdk)
    - [CLI](#cli)
  - [Demos \& Examples](#demos--examples)
  - [Core Guarantees](#core-guarantees)
  - [Repo Layout](#repo-layout)
  - [Testing](#testing)
  - [Docs](#docs)
  - [Roadmap](#roadmap)
  - [Contributing](#contributing)

---

## Install

Python 3.10+.

```bash
# from source (editable)
pip install -e .

# with extras for demos/tests
pip install -e .[pillow,hypothesis]

# optional binary I/O deps
pip install msgpack cbor2

# optional: image demo / property tests
pip install pillow hypothesis
```

---

## Quickstart

### Python SDK

```python
import numpy as np
from phasebridge import S1PhaseCodec, PIF, kappa_timeseries

# Discrete input: uint8 in [0..255]
x = np.arange(0, 256, dtype=np.uint8)

codec = S1PhaseCodec(M=256)
schema = {"alphabet": {"type": "uint", "M": 256}, "sampling": {"fs": 100.0}}

# 1) Eager θ (default float64)
p = codec.encode(x, schema)
xr = codec.decode(p)
assert np.array_equal(x, xr)
print("kappa eager:", kappa_timeseries(p))

# 2) Lazy θ + float32 preference (safe for M ≤ 65536)
p_lazy = codec.encode(x, schema, lazy_theta=True, prefer_float32=True, allow_downgrade=True)
# theta materializes on demand (float32 in safe zone)
print("theta dtype:", p_lazy.theta_view.dtype)

# 3) Binary round-trip (MessagePack)
blob = p_lazy.to_bytes(fmt="msgpack")
p_lazy2 = PIF.from_bytes(blob, fmt="msgpack", validate=True)
assert np.array_equal(codec.decode(p_lazy2), x)
```

### CLI

```bash
# Encode raw bytes -> PIF (lazy + float32 if safe) in MessagePack
cat data.bin | pb-encode --in - --in-fmt bin --dtype uint8 --M 256 \
  --lazy --prefer-float32 --pif-fmt msgpack > out_lazy.pif.mpk

# Decode PIF (any format) -> raw bytes
pb-decode --in out_lazy.pif.mpk --pif-fmt msgpack --out recon.bin --out-fmt bin

# Validate (schema/runtime/hash) with NPZ
pb-validate --in out_lazy.pif.npz --pif-fmt npz --report json

# κ (global and windowed) from CBOR
pb-kappa --in out_lazy.pif.cbor --pif-fmt cbor --fmt plain
pb-kappa --in out_lazy.pif.cbor --pif-fmt cbor --win 256 --hop 128 --fmt csv > kappa_windowed.csv
```

---

## Demos & Examples

* `examples/timeseries_roundtrip.py` — CSV (uint) → PIF → CSV; strict equality & κ report.
* `examples/image_roundtrip.py` — 8-bit grayscale image → PIF → image; strict equality & κ report.
* `demo/roundtrip_image.ipynb` — visual demo (original / phase map / reconstructed).
* `demo/roundtrip_timeseries.ipynb` — series round-trip + windowed κ plot.

**How to run demos (short):**

```bash
# 1) Timeseries demo (creates synthetic CSV)
python examples/timeseries_roundtrip.py \
  --in-csv series.csv \
  --out-pif series.pif.cbor --pif-fmt cbor --lazy --prefer-float32 \
  --out-csv series_rec.csv \
  --M 256 --dtype uint8 --fs 100 --synth --N 2000

# 2) Image demo (8-bit grayscale)
python examples/image_roundtrip.py \
  --in-img lena.png \
  --out-pif lena.pif.npz --pif-fmt npz --lazy --prefer-float32 \
  --out-img lena_rec.png \
  --M 256
```

Both scripts print a JSON report: `ok=true`, matching hashes (`hash_ok=true`), κ value.

---

## Core Guarantees

* **Lossless round-trip** for declared alphabets (`uintM`):
  `meta.note == "no_processing"` ⇒ `decode(encode(x)) == x`.

* **Numeric policy**:

  * `theta` MAY be stored as **float32** (with **conservative safety** `M ≤ 65536`; `numeric.precision_safe=true`) or **float64**.
  * Decoding uses float64 rounding for nearest-grid snapping; this ensures robustness even for float32 θ.

* **Lazy-PIF**:

  * `theta_lazy=true` + `encoded_uint` (no explicit θ in storage).
    Consumers materialize `θ = (2π/M)⋅n` on demand in `numeric.dtype` (default float64).

* **Schema validation**: minimal, explicit `schema.alphabet.M` (+ optional metadata).

* **Integrity**: `meta.hash_raw = sha256(raw)` recommended; verify on decode.

Details: see `docs/pif_format.md` and `docs/api_sdk.md`.

---

## Repo Layout

```bash
phasebridge/
├─ src/phasebridge/              # SDK (PIF, codec, κ, schema, utils, errors)
├─ cli/                          # pb-encode / pb-decode / pb-kappa / pb-validate
├─ schemas/                      # JSON Schema (PIF v1 core) + YAML mirror
├─ examples/                     # runnable scripts (series, image)
├─ demo/                         # Jupyter notebooks (demos)
├─ tests/                        # unit + property tests
└─ docs/                         # overview, spec, API, CLI, integration, roadmap, ADRs
```

---

## Testing

```bash
pytest -q                    # unit tests
pip install hypothesis
pytest -q                    # adds property tests
```

The test suite covers strict round-trip, κ bounds, schema/runtime validation, and API contract.

---

## Docs

* `docs/overview.md` — motivation & principles
* `docs/pif_format.md` — PIF v1 core (normative; lazy θ, numeric policy, binary I/O)
* `docs/cli_usage.md` — CLI commands & recipes

---

## Roadmap

* Adapters: tables, text tokens, RGB, audio, logs/events.
* Sidecar service (HTTP/gRPC) and streaming operators (Kafka/Flink).
* Optional processing track (explicit, labeled `processed:*`, outside MVP core).
* Language bindings (Go/C++/Rust). See `docs/roadmap.md`.

---

## Contributing

Contributions are welcome! Please see:

* `CONTRIBUTING.md` — guidelines
* `CODE_OF_CONDUCT.md` — community standards
* `SECURITY.md` — reporting vulnerabilities

Run tests locally before opening a PR. Keep the **lossless contract** sacred.
