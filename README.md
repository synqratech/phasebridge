
# PhaseBridge — Lossless Discrete ↔ Phase ↔ Discrete

**PhaseBridge** is a tiny, universal interchange layer that lets any system move data **losslessly** between a discrete space and a **continuous, phase-based** representation — and back again. It standardizes a strict, reversible mapping `uintM ↔ θ ∈ [0, 2π)` with a minimal schema, clean SDK, CLI tools, and conformance tests.

- **Lossless by default**: when `meta.note="no_processing"`, `decode(encode(x)) == x` (bit-exact for the declared alphabet).
- **Simple & universal**: phases (unit circle) as a compact continuous target; float64-only θ.
- **Separation of concerns**: conversion is strict and idempotent; any future processing must be explicit and labeled.
- **Observable**: κ (coherence) as a read-only diagnostic signal.

> MVP supports time series and 8-bit grayscale images. More modalities (tables, RGB, audio, text tokens, logs) are planned.

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
# optional extras individually
pip install msgpack pillow hypothesis
msgpack — compact binary PIF I/O (optional).

pillow — image I/O for the image demo (optional).

hypothesis — property-based tests (optional).

---
## How to run demos
Quick commands to check strict round-trip and κ reports.
```bash
# 1) Timeseries demo (creates synthetic CSV)
python examples/timeseries_roundtrip.py \
  --in-csv series.csv \
  --out-pif series.pif.json \
  --out-csv series_rec.csv \
  --M 256 --dtype uint8 --fs 100 --synth --N 2000

# 2) Image demo (8-bit grayscale)
python examples/image_roundtrip.py \
  --in-img lena.png \
  --out-pif lena.pif.json \
  --out-img lena_rec.png \
  --M 256
```

Both scripts print a JSON report: ok=true, matching hashes (hash_ok=true), κ value.

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

p = codec.encode(x, schema)   # -> PIF (theta float64)
xr = codec.decode(p)          # -> back to uint8
assert np.array_equal(x, xr)

k = kappa_timeseries(p)       # read-only coherence in [0,1]
print("kappa:", k)

# JSON round-trip
s = p.to_json(indent=2)
p2 = PIF.from_json(s, validate=True)

```

### CLI

```bash
# Encode raw bytes -> PIF JSON
cat data.bin | pb-encode --in - --in-fmt bin --dtype uint8 --M 256 > out.pif.json

# Decode PIF JSON -> raw bytes
cat out.pif.json | pb-decode --in - --pif-fmt json --out - --out-fmt bin > recon.bin

# Validate schema/runtime/hash (and compare with a raw file)
pb-validate --in out.pif.json --raw data.bin --in-fmt bin --dtype uint8 --report json

# κ (global or windowed)
pb-kappa --in out.pif.json --fmt plain
pb-kappa --in out.pif.json --win 256 --hop 128 --fmt csv > kappa_windowed.csv

```

---

## Demos & Examples

- `examples/timeseries_roundtrip.py` — CSV (uint) → PIF → CSV; strict equality & κ report.
- `examples/image_roundtrip.py` — 8-bit grayscale image → PIF → image; strict equality & κ report.
- `demo/roundtrip_image.ipynb` — visual “wow” demo (original / phase map / reconstructed).
- `demo/roundtrip_timeseries.ipynb` — series round-trip + windowed κ plot.

---

## Core Guarantees

- **Lossless round-trip** for declared alphabets (`uintM`):

    `meta.note == "no_processing"` ⇒ `decode(encode(x)) == x`.

- **Float64 phases**: θ stored as IEEE-754 float64, wrapped to `[0, 2π)`.
- **Nearest-grid decoding**: robust and deterministic.
- **Schema validation**: minimal, explicit `schema.alphabet.M` (+ optional metadata).
- **Integrity**: `meta.hash_raw = sha256(raw)` recommended; verify on decode.

Details: see `docs/pif_format.md` and `docs/api_sdk.md`.

---

## Repo Layout

```bash
phasebridge/
├─ src/phasebridge/              # SDK (PIF, codec, κ, schema, utils, errors)
├─ cli/                          # pb-encode / pb-decode / pb-kappa / pb-validate
├─ schemas/                      # JSON Schema (PIF v1 core) + YAML mirror
├─ examples/                     # runnable scripts (series, image)
├─ demo/                         # Jupyter notebooks (wow demos)
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

- `docs/overview.md` — motivation & principles
- `docs/pif_format.md` — PIF v1 core (normative)
- `docs/cli_usage.md` — CLI commands & recipes

---

## Roadmap

- Adapters: tables, text tokens, RGB, audio, logs/events.
- Sidecar service (HTTP/gRPC) and streaming operators (Kafka/Flink).
- Optional processing track (explicit, labeled `processed:*`, outside MVP core).
- Language bindings (Go/C++/Rust). See `docs/roadmap.md`.

---

## Contributing

Contributions are welcome! Please see:

- `CONTRIBUTING.md` — guidelines
- `CODE_OF_CONDUCT.md` — community standards
- `SECURITY.md` — reporting vulnerabilities

Run tests locally before opening a PR. Keep the **lossless contract** sacred.
