# CLI Usage — PhaseBridge

PhaseBridge ships four command-line tools that wrap the SDK for **strict, lossless** discrete ↔ phase ↔ discrete conversion and read-only κ-metrics.

* `pb-encode` — raw (bin/csv/npy) → **PIF** (json/msgpack)
* `pb-decode` — **PIF** (json/msgpack) → raw (bin/csv/npy)
* `pb-kappa`  — compute **κ** (global/windowed) from PIF
* `pb-validate` — schema/runtime validation + decode + hash checks (+ optional raw compare)

> Requirements: Python 3.10+, `numpy`. Optional: `msgpack` (for MessagePack I/O).
> See: `docs/pif_format.md` (wire format), `docs/api_sdk.md` (SDK).

---

## Common Conventions

* **stdin/stdout**: pass `--in -` / `--out -` to read from stdin / write to stdout.
* **PIF format**: defaults to JSON; specify `--pif-fmt msgpack` for MessagePack (requires `msgpack`).
* **Alphabet size** `M`: defines the discrete symbol set `{0…M-1}` (e.g., `256` for `uint8`).
* **Strict lossless**: tools perform *conversion only*. No processing is allowed in MVP.

---

## `pb-encode` — raw → PIF

Convert raw discrete data into a PIF object.

**Usage**

```
pb-encode --in <file|->
          --in-fmt {bin|csv|npy}
          --dtype <numpy-uint>
          --M <int>
          [--fs <float>]
          [--out <file|- >]
          [--pif-fmt {json|msgpack}]
          [--pretty]
```

**Key options**

* `--in, --in-fmt`: input and its format (`bin`, `csv`, or `.npy` array).
* `--dtype`: unsigned dtype of the input (e.g., `uint8`, `uint16`).
* `--M`: alphabet size (e.g., `256` for 8-bit values).
* `--fs`: optional sampling rate metadata (Hz) for time series.
* `--pif-fmt`: `json` (default) or `msgpack`.
* `--pretty`: pretty-print JSON (indent=2).

**Examples**

```bash
# Bytes -> PIF JSON (stdout)
cat data.bin | pb-encode --in - --in-fmt bin --dtype uint8 --M 256 > out.pif.json

# CSV of uint8 -> PIF JSON (file)
pb-encode --in data.csv --in-fmt csv --dtype uint8 --M 256 --fs 100 --out out.pif.json

# Numpy .npy -> PIF MessagePack
pb-encode --in data.npy --in-fmt npy --dtype uint16 --M 65536 \
          --pif-fmt msgpack --out out.pif.mpk
```

---

## `pb-decode` — PIF → raw

Reconstruct the original discrete data from a PIF object (bit-exact w.r.t. declared alphabet).

**Usage**

```
pb-decode --in <file|->
          [--pif-fmt {json|msgpack}]
          --out <file|->
          --out-fmt {bin|csv|npy}
```

**Notes**

* Output dtype is auto-chosen: minimal unsigned dtype covering `[0..M-1]`.

**Examples**

```bash
# PIF JSON -> raw bytes (stdout)
cat out.pif.json | pb-decode --in - --pif-fmt json --out - --out-fmt bin > recon.bin

# PIF MessagePack -> CSV
pb-decode --in out.pif.mpk --pif-fmt msgpack --out recon.csv --out-fmt csv
```

---

## `pb-kappa` — κ(PIF)

Compute κ coherence from a PIF (global or windowed). **Read-only; does not modify data.**

**Usage**

```
pb-kappa --in <file|->
         [--pif-fmt {json|msgpack}]
         [--weighted]           # use amp[] as weights if present
         [--win <int> --hop <int>]
         [--fmt {plain|json|csv}]
```

**Output**

* Global κ: single scalar (`plain` prints a float).
* Windowed κ: centers + κ values (`csv` or `json` recommended).

**Examples**

```bash
# Global κ (plain float)
pb-kappa --in out.pif.json --fmt plain

# Windowed κ (CSV)
pb-kappa --in out.pif.json --win 256 --hop 128 --fmt csv > kappa_win.csv

# Windowed κ (JSON)
pb-kappa --in out.pif.mpk --pif-fmt msgpack --win 512 --hop 256 --fmt json > kappa_win.json
```

---

## `pb-validate` — schema/runtime/hash/round-trip checks

Validate a PIF object, decode it, verify hash, and optionally compare with a raw reference file.

**Usage**

```
pb-validate --in <file|->
            [--pif-fmt {json|msgpack}]
            [--raw <file>] [--in-fmt {bin|csv|npy}] [--dtype <numpy-uint>]
            [--report {json|text}]
```

**Checks performed**

* JSON Schema + runtime validation of PIF structure/numerics.
* Decode with `S1PhaseCodec(M)` where `M` read from `schema.alphabet.M`.
* If `meta.hash_raw` present: verify `sha256(decoded) == meta.hash_raw`.
* If `--raw` given: also compare decoded vs raw (array equality) and raw hash vs `meta.hash_raw`.

**Exit code**

* `0` on success (`ok: true`), `1` otherwise.

**Examples**

```bash
# Validate and report (JSON)
pb-validate --in out.pif.json --report json

# With raw comparison
pb-validate --in out.pif.json \
            --raw data.bin --in-fmt bin --dtype uint8 \
            --report text
```

---

## End-to-End Recipes

**Lossless pipeline (bytes)**

```bash
# Encode -> Decode -> Compare
cat data.bin \
 | pb-encode --in - --in-fmt bin --dtype uint8 --M 256 \
 | tee out.pif.json \
 | pb-decode --in - --pif-fmt json --out - --out-fmt bin \
 > recon.bin

# Validate strict equality & hash
pb-validate --in out.pif.json --raw data.bin --in-fmt bin --dtype uint8 --report json
```

**Time series (CSV)**

```bash
pb-encode --in sensor.csv --in-fmt csv --dtype uint8 --M 256 --fs 100 --out sensor.pif.json
pb-kappa  --in sensor.pif.json --win 256 --hop 128 --fmt csv > sensor_kappa.csv
pb-decode --in sensor.pif.json --out sensor_rec.csv --out-fmt csv
pb-validate --in sensor.pif.json --raw sensor.csv --in-fmt csv --dtype uint8 --report text
```

**Image (8-bit grayscale)**

```bash
# Convert image to 8-bit grayscale array (see examples/image_roundtrip.py)
python examples/image_roundtrip.py \
  --in-img lena.png --out-pif lena.pif.json --out-img lena_rec.png --M 256
```

---

## Troubleshooting

* **“Values out of range” on encode**
  Your input contains values outside `[0, M-1]`. Fix input or choose correct `--M`.
  (*Optional non-strict modular mode exists in SDK but is not used by CLI.*)

* **Wrong dtype**
  Ensure `--dtype` matches the file format: `bin` is raw bytes of that dtype; `csv` contains integer text; `npy` is a NumPy array.

* **Schema mismatch**
  If you hand-edited PIF, ensure `schema.alphabet.M` is correct and matches the encoder/decoder.

* **MessagePack not installed**
  Install: `pip install msgpack`, then use `--pif-fmt msgpack`.

* **No processing**
  MVP forbids any modification to `theta`/`amp`. If a tool changes data, it must set `meta.note="processed:<ops>"` (strict round-trip no longer guaranteed).

---

## Performance Tips

* Prefer MessagePack for large PIFs (`--pif-fmt msgpack`).
* Stream with stdin/stdout to avoid temporary files.
* Avoid pretty JSON (`--pretty`) on hot paths.

---

## See Also

* `docs/overview.md` — motivation & principles
* `docs/pif_format.md` — normative PIF v1 core
* `docs/api_sdk.md` — Python SDK details
* `examples/` & `demo/` — hands-on scripts and notebooks
