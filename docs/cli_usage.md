# CLI Usage — PhaseBridge

PhaseBridge ships four command-line tools that wrap the SDK for **strict, lossless** discrete ↔ phase ↔ discrete conversion and read-only κ-metrics.

- `pb-encode` — raw (bin/csv/npy) → **PIF** (json/msgpack/cbor/npz)
- `pb-decode` — **PIF** (json/msgpack/cbor/npz) → raw (bin/csv/npy)
- `pb-kappa` — compute **κ** (global/windowed) from PIF
- `pb-validate` — schema/runtime validation + decode + hash checks (+ optional raw compare)

> Requirements: Python 3.10+, numpy.
> 
> 
> Optional: `msgpack` (for MessagePack I/O), `cbor2` (for CBOR I/O).
> 
> See also: `docs/pif_format.md` (wire format), `docs/api_sdk.md` (SDK).
> 

---

## Common Conventions

- **stdin/stdout**: pass `-in -` / `-out -` to read from stdin / write to stdout.
- **PIF format**:
    - Default is JSON when `-in -` (stdin).
    - By file extension: `.mp/.mpk/.msgpack` → msgpack, `.cbor/.cbor2` → cbor, `.npz` → npz, otherwise json.
    - Explicit override: `-pif-fmt {json|msgpack|cbor|npz}`.
- **Alphabet size** `M`: defines the discrete symbol set `{0…M-1}` (e.g., `256` for `uint8`).
- **Strict lossless**: tools perform *conversion only*. No processing is allowed in MVP.

---

## `pb-encode` — raw → PIF

Convert raw discrete data into a PIF object.

**Usage**

```
pb-encode --in <file|->                                  \
          --in-fmt {bin|csv|npy}                         \
          --dtype <numpy-uint>                           \
          --M <int>                                      \
          [--fs <float>]                                 \
          [--out <file|->]                               \
          [--pif-fmt {json|msgpack|cbor|npz}]            \
          [--lazy]                                       \
          [--prefer-float32] [--no-downgrade]            \
          [--pretty]                                     # JSON pretty-print

```

**Key options**

- `-in, --in-fmt`: input and its format (`bin`, `csv`, or `.npy` array).
- `-dtype`: unsigned dtype of the input (e.g., `uint8`, `uint16`).
- `-M`: alphabet size (e.g., `256` for 8-bit values).
- `-fs`: optional sampling rate metadata (Hz) for time series (`schema.sampling.fs`).
- `-pif-fmt`: choose container: `json` (text), `msgpack`/`cbor` (binary), `npz` (binary zip).
- `-lazy`: emit **Lazy θ** (`theta_lazy=true` + `encoded_uint`), do **not** store `theta` explicitly.
- `-prefer-float32`: request `numeric.dtype="float32"`. If **safe** (conservative v1: `M ≤ 65536`), set `precision_safe=true`.
    
    Если **unsafe** и **без** `--no-downgrade` → автоматический **downgrade** на `float64` (`precision_safe=true`).
    
    Если **unsafe** и **с** `--no-downgrade` → оставить `float32`, но пометить `precision_safe=false`.
    
- `-pretty`: pretty-print JSON (indent=2); не влияет на двоичные форматы.

**Examples**

```bash
# Bytes -> PIF JSON (stdout)
cat data.bin | pb-encode --in - --in-fmt bin --dtype uint8 --M 256 > out.pif.json

# CSV of uint8 -> PIF MessagePack (Eager θ, float64)
pb-encode --in data.csv --in-fmt csv --dtype uint8 --M 256 --fs 100 \
          --pif-fmt msgpack --out out.pif.mpk

# Numpy .npy -> PIF CBOR (Lazy θ + float32 safe)
pb-encode --in data.npy --in-fmt npy --dtype uint16 --M 65536 \
          --lazy --prefer-float32 --pif-fmt cbor --out out_lazy.pif.cbor

# Numpy .npy -> PIF NPZ (Lazy θ; fallback to float64 if unsafe)
pb-encode --in data.npy --in-fmt npy --dtype uint32 --M 100000 \
          --lazy --prefer-float32           \
          --pif-fmt npz --out out_lazy.pif.npz

# Force float32 even if unsafe (precision_safe=false)
pb-encode --in data.bin --in-fmt bin --dtype uint32 --M 200000 \
          --lazy --prefer-float32 --no-downgrade \
          --pif-fmt msgpack --out out_unsafe_f32.pif.mpk

```

---

## `pb-decode` — PIF → raw

Reconstruct the original discrete data from a PIF object (bit-exact w.r.t. declared alphabet).

**Usage**

```
pb-decode --in <file|->
          [--pif-fmt {json|msgpack|cbor|npz}]
          --out <file|->
          --out-fmt {bin|csv|npy}

```

**Notes**

- Output dtype is auto-chosen: minimal unsigned dtype covering `[0..M-1]`.
- Works for both **Eager θ** and **Lazy θ** PIFs.

**Examples**

```bash
# PIF JSON -> raw bytes (stdout)
cat out.pif.json | pb-decode --in - --pif-fmt json --out - --out-fmt bin > recon.bin

# PIF MessagePack -> CSV
pb-decode --in out.pif.mpk --pif-fmt msgpack --out recon.csv --out-fmt csv

# PIF CBOR (lazy θ) -> NPY
pb-decode --in out_lazy.pif.cbor --pif-fmt cbor --out recon.npy --out-fmt npy

# PIF NPZ -> raw bytes
pb-decode --in out_lazy.pif.npz --pif-fmt npz --out recon.bin --out-fmt bin

```

---

## `pb-kappa` — κ(PIF)

Compute κ coherence from a PIF (global or windowed). **Read-only; does not modify data.**

**Usage**

```
pb-kappa --in <file|->
         [--pif-fmt {json|msgpack|cbor|npz}]
         [--weighted]                 # use amp[] as weights if present
         [--win <int> --hop <int>]
         [--fmt {plain|json|csv}]

```

**Output**

- Global κ: single scalar (`plain` prints a float).
- Windowed κ: centers + κ values (`csv` or `json` recommended).

**Examples**

```bash
# Global κ (plain float)
pb-kappa --in out.pif.json --pif-fmt json --fmt plain

# Windowed κ (JSON) from MessagePack (lazy θ)
pb-kappa --in out_lazy.pif.mpk --pif-fmt msgpack --win 512 --hop 256 --fmt json

# Windowed κ (CSV) from CBOR
pb-kappa --in out_lazy.pif.cbor --pif-fmt cbor --win 256 --hop 128 --fmt csv > kappa_win.csv

# Windowed κ (CSV) from NPZ
pb-kappa --in out_lazy.pif.npz --pif-fmt npz --win 256 --hop 128 --fmt csv

```

---

## `pb-validate` — schema/runtime/hash/round-trip checks

Validate a PIF object, decode it, verify hash, and optionally compare with a raw reference file.

**Usage**

```
pb-validate --in <file|->
            [--pif-fmt {json|msgpack|cbor|npz}]
            [--raw <file>] [--in-fmt {bin|csv|npy}] [--dtype <numpy-uint>]
            [--report {json|text}]

```

**Checks performed**

- JSON Schema + runtime validation of PIF structure/numerics.
- Decode with `S1PhaseCodec(M)` where `M` read from `schema.alphabet.M`.
- If `meta.hash_raw` present: verify `sha256(decoded) == meta.hash_raw`.
- If `-raw` given: also compare decoded vs raw (array equality) and raw hash vs `meta.hash_raw`.

**Exit code**

- `0` on success (`ok: true`), `1` otherwise.

**Examples**

```bash
# Validate and report (JSON) from CBOR
pb-validate --in out_lazy.pif.cbor --pif-fmt cbor --report json

# With raw comparison (NPZ)
pb-validate --in out_lazy.pif.npz --pif-fmt npz \
            --raw data.bin --in-fmt bin --dtype uint8 \
            --report text

```

---

## End-to-End Recipes

**Lossless pipeline (bytes)**

```bash
# Encode (lazy + msgpack) -> Decode -> Compare
cat data.bin \
 | pb-encode --in - --in-fmt bin --dtype uint8 --M 256 \
             --lazy --prefer-float32 --pif-fmt msgpack \
 | tee out_lazy.pif.mpk \
 | pb-decode --in - --pif-fmt msgpack --out - --out-fmt bin \
 > recon.bin

# Validate strict equality & hash
pb-validate --in out_lazy.pif.mpk --pif-fmt msgpack \
            --raw data.bin --in-fmt bin --dtype uint8 --report json

```

**Time series (CSV)**

```bash
pb-encode --in sensor.csv --in-fmt csv --dtype uint8 --M 256 --fs 100 \
          --lazy --prefer-float32 --pif-fmt cbor --out sensor_lazy.pif.cbor
pb-kappa  --in sensor_lazy.pif.cbor --pif-fmt cbor --win 256 --hop 128 --fmt csv \
          > sensor_kappa.csv
pb-decode --in sensor_lazy.pif.cbor --pif-fmt cbor --out sensor_rec.csv --out-fmt csv
pb-validate --in sensor_lazy.pif.cbor --pif-fmt cbor --report text

```

---

## Troubleshooting

- **“Values out of range” on encode**
    
    Your input contains values outside `[0, M-1]`. Fix input or choose correct `--M`.
    
    (*Optional non-strict modular mode may exist in SDK but is not used by CLI.*)
    
- **Wrong dtype**
    
    Ensure `--dtype` matches the file format: `bin` is raw bytes of that dtype; `csv` contains integer text; `npy` is a NumPy array.
    
- **Schema mismatch**
    
    If you hand-edited PIF, ensure `schema.alphabet.M` is correct and matches the encoder/decoder.
    
- **Missing binary dependencies**
    - MessagePack: `pip install msgpack`
    - CBOR: `pip install cbor2`
- **No processing**
    
    MVP forbids modifications to `theta`/`amp`. If a tool changes data, it must set `meta.note="processed:<ops>"` (strict round-trip no longer guaranteed).
    

---

## Performance Tips (Production Defaults)

- **Default to**: **`-lazy` + `-prefer-float32` + binary format (`-pif-fmt msgpack` or `cbor`)**.
    
    Это даёт:
    
    - компактнее хранения (без `theta` float64),
    - половину памяти/IO на θ при float32,
    - существенно быстрее загрузку/выгрузку в двоичных контейнерах.
- Если `M > 65536` и нужна строгая гарантия — **не** добавляйте `-no-downgrade`: encoder автоматически вернёт `float64` (`precision_safe=true`).
- Для обмена между Python-пайплайнами с NumPy можно использовать `-pif-fmt npz` (нативные `.npy` внутри контейнера).
- Избегайте pretty JSON (`-pretty`) на горячих путях.

---

## See Also

- `docs/overview.md` — motivation & principles
- `docs/pif_format.md` — normative PIF v1 core
- `docs/api_sdk.md` — Python SDK details
- `examples/` & `demo/` — hands-on scripts and notebooks
