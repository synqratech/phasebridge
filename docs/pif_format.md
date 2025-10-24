# PIF v1 — Core Specification (Strict, Lossless)

**Phase Interchange Format (PIF)** is a minimal, versioned container for representing discrete data as **continuous phase** values and back **without loss**. This document defines the **normative core** of PIF v1 used by PhaseBridge.

Scope here is the **strict conversion layer**: no processing, no filtering, no compression. If a PIF object declares `meta.note: "no_processing"`, decoding MUST reproduce the original discrete input **bit-exactly** with respect to the declared alphabet.

---

## 1. Terminology

- **Producer**: component that creates a PIF object from discrete input (encoder).
- **Consumer**: component that reads PIF and reconstructs the discrete data (decoder).
- **Alphabet**: finite set of discrete symbols `{0,…,M-1}`.
- **S1PhaseCodec(M)**: canonical lossless mapping `uintM ↔ θ ∈ [0,2π)`.

---

## 2. Data Model (Object Members)

A PIF object is a structured object with the following members. JSON is the **normative** serialization (§7.1). Binary serializations (MessagePack, CBOR, NPZ) are **semantically equivalent** (§7.2–§7.4).

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `pif_version` | string | optional | SemVer of the PIF format (e.g., `"1.0.0"`). |
| `domain` | string | optional | Informational (e.g., `"time_series"`, `"image"`). |
| `schema` | object | **yes** | Minimal schema for reconstruction (see §3.1–§3.2). |
| `numeric` | object | optional | Numeric policy (see §3.3). |
| `codec` | object | optional | Codec identifiers (informational in MVP). |
| `theta` | number[] | *see oneOf* | Phases, wrapped to `[0,2π)`. See `numeric.dtype` for datatype. Length `N ≥ 1`. |
| `encoded_uint` | integer[] | *see oneOf* | Lazy symbols `{0,…,M-1}` used to materialize `theta` on demand (see §2.1). Length `N ≥ 1`. |
| `theta_lazy` | boolean | *see oneOf* | `true` if object carries lazy payload (`encoded_uint`) rather than explicit `theta`. |
| `amp` | number | number[] | optional | Amplitude. Defaults to scalar `1.0`. If array, length `N`, values `≥ 0`. |
| `meta` | object | **yes** | Operational metadata (see §4). |

### 2.1 One of two payload modes (normative)

A PIF v1 **MUST** use exactly one of the following payload modes:

- **Eager θ** (explicit phases):
    - `theta` **present**
    - `theta_lazy` either absent or `false`
    - `encoded_uint` **absent**
- **Lazy θ** (indices; phase materialized on read):
    - `theta_lazy: true`
    - `encoded_uint` **present**
    - `theta` **absent**

Consumers MUST support both modes. In Lazy θ, consumers materialize `theta = (2π/M)⋅n` on demand (see §6).

---

## 3. Schema & Numeric Constraints

### 3.1 `schema.alphabet` (required)

```json
"schema": {
  "alphabet": { "type": "uint", "M": 256 },
  "...": "other optional keys"
}

```

- `type` MUST be `"uint"`.
- `M` MUST be integer `2 ≤ M ≤ 2^32`.
- This defines the round-trip alphabet `{0,…,M-1}`.

### 3.2 `schema.sampling` (optional)

```json
"schema": {
  "sampling": { "fs": 100.0 }
}

```

- `fs` (Hz) MUST be a positive finite number if present.

### 3.3 `numeric` (optional)

If omitted, the following defaults are assumed:

```json
"numeric": {
  "dtype": "float64",
  "phase_wrap": [0.0, 6.283185307179586]
}

```

- `dtype`:
    - Enum: `"float32"` | `"float64"`.
    - If omitted, default is `"float64"`.
- `precision_safe` (boolean; optional):
    - If present and `true`, the producer asserts that storing θ in `numeric.dtype` is safe for round-trip (see §6.2).
- `phase_wrap`:
    - Indicates that `theta` values are wrapped to `[0,2π)`. Producers MUST store wrapped values; consumers MAY re-wrap defensively.

---

## 4. Meta & Codec

```json
"meta": {
  "note": "no_processing",
  "hash_raw": "sha256:<64 hex>",
  "codec": "S1_phase_code_M256",
  "codec_hash": "sha256:<64 hex>"
}

```

- `meta.note` is **required**.
    - `"no_processing"` means the payload was produced by canonical conversion and MUST round-trip bit-exactly.
    - `"processed:<ops>"` (future) indicates transformations beyond conversion (strict round-trip is not guaranteed).
- `meta.hash_raw` (optional but RECOMMENDED): SHA-256 of the original discrete input bytes, encoded as `"sha256:<hex64>"`. Consumers SHOULD verify `sha256(decoded) == meta.hash_raw`.
- `meta.codec` (optional): stable codec identifier string (e.g., `"S1_phase_code_M256"`).
- `meta.codec_hash` (optional): SHA-256 fingerprint of the codec identity string (or binary).

`codec` object (optional) MAY mirror identifiers:

```json
"codec": { "forward": "S1_phase_code_M256", "inverse": "S1_phase_decode_M256" }

```

---

## 5. Canonical Codec (S1PhaseCodec)

**Encoding (Producer)**: for `M ≥ 2`, input array `x` of unsigned integers with values in `[0, M-1]`:

[

\theta_i = \frac{2\pi}{M},x_i

]

- Store **EITHER** `theta` (eager) **OR** `encoded_uint` with `theta_lazy=true` (lazy).
- Set `amp = 1.0` (MVP).
- Set `meta.note = "no_processing"`.
- Compute `meta.hash_raw = "sha256:" + SHA256(bytes(x))`.

**Decoding (Consumer)**: for phases `θ`:

[

n_i = \operatorname{round}!\left(\frac{M}{2\pi},\theta_i\right) \bmod M

]

- `round` is **nearest integer**; exact ties are not expected for valid input.
- Output dtype MUST be the minimal unsigned integer type that can represent `[0, M-1]`:
    - `M ≤ 256` → `uint8`
    - `M ≤ 65536` → `uint16`
    - `M ≤ 2^32` → `uint32`
    - otherwise `uint64` (not used in MVP).

---

## 6. Lossless Round-Trip Contract & Numeric Policy

### 6.1 Core round-trip (normative)

For PIF with `meta.note == "no_processing"` and a valid `schema.alphabet.M`:

- **Correctness**: `decode(encode(x)) == x` **bit-exact**, for all arrays `x` with elements in `[0, M-1]`.
- **Decoding numeric**: Consumers MUST perform nearest-grid snapping using **float64** arithmetic for the rounding operation.

### 6.2 `theta` datatype policy

- `numeric.dtype` MAY be `"float64"` or `"float32"`.
- **Float32 allowance**:
    - A PIF MAY store θ as `float32` **iff** round-trip is guaranteed. In v1 core, the **conservative safe zone** is:
        - `M ≤ 65,536` (the “float32-safe M” table).
    - Producers SHOULD set `numeric = {"dtype":"float32","precision_safe":true}` when using float32 inside the safe zone.
    - Outside the safe zone, producers MAY set `{"dtype":"float32","precision_safe":false}` (for compactness), but **MUST NOT** claim strict round-trip unless they can prove tighter error bounds. Consumers SHOULD treat such payloads as potentially unsafe; decoding still uses float64 rounding.
- **Lazy θ**:
    - When `theta_lazy=true`, θ is **materialized** by the consumer on demand as:
        
        [
        
        \theta = \frac{2\pi}{M},n
        
        ]
        
        in the indicated `numeric.dtype` (default float64 if `numeric` absent).
        

---

## 7. Serialization

### 7.1 JSON (normative)

- Field names and semantics are normative.
- Numbers in `theta`/`amp` are interpreted according to `numeric.dtype` (default float64). Producers SHOULD emit sufficient precision (≥17 significant digits for float64) to ensure round-trip through text.
- Unknown fields MUST be ignored by consumers (forward compatibility).

### 7.2 MessagePack (optional; binary)

- Same object structure and semantics as JSON.
- **ndarray packing rule** (RECOMMENDED):
    - Arrays are represented as objects:
        
        ```json
        { "__nd__": true, "dtype": "float32", "shape": [N,...], "data": <bytes> }
        
        ```
        
    - `data` is raw bytes (no base64). This yields compact, fast I/O.

### 7.3 CBOR (optional; binary)

- Same object structure and semantics as JSON.
- Use the same ndarray packing rule as in MessagePack:
    
    ```json
    { "__nd__": true, "dtype": "float32", "shape": [N,...], "data": <bytes> }
    
    ```
    
- CBOR offers a standardized binary container with similar performance.

### 7.4 NPZ (optional; binary container)

- Zip with the following entries:
    - `schema.json`, `meta.json`, `numeric.json` (optional), `flags.json` (e.g., `{"theta_lazy": true}`)
    - **One of**: `theta.npy` **or** `encoded_uint.npy`
    - `amp.npy` (if array) **or** `amp.json` (if scalar)
- Arrays use `.npy` (native NumPy); JSON payloads use UTF-8 without BOM.

> All binary formats (MessagePack, CBOR, NPZ) are semantically equivalent to JSON. They differ only by transport/container; the PIF data model remains identical.
> 

---

## 8. JSON Schema

Authoritative schemas (mirrors):

- `schemas/pif_v1.json` (JSON Schema)
- `schemas/pif_v1.yaml` (human-readable mirror)

**Key points**:

- Top-level **`oneOf`** enforces exactly one payload mode:
    - Eager: requires `theta` (and `theta_lazy` absent/false).
    - Lazy: requires `theta_lazy: true` + `encoded_uint`.
- `numeric.dtype` enum is `{"float32","float64"}`; `precision_safe` is boolean (optional).

Consumers MAY use JSON Schema validation; **runtime validation** of numeric/range constraints is still REQUIRED (e.g., dtype, phase range, amp shape).

---

## 9. Conformance

### 9.1 Producer conformance

A conforming producer MUST:

- Emit `schema` (with valid `alphabet`) and `meta.note`.
- Use **either** Eager θ (`theta`) **or** Lazy θ (`theta_lazy: true` + `encoded_uint`).
- Wrap θ to `[0,2π)`.
- Respect `numeric.dtype` (default `"float64"`); when using `"float32"`, set `precision_safe=true` only if safety criteria are met (v1 core: `M ≤ 65536`).
- Set `meta.note = "no_processing"` for pure conversion.
- (Recommended) populate `meta.hash_raw`, `meta.codec`, `meta.codec_hash`.

### 9.2 Consumer conformance

A conforming consumer MUST:

- Support both Eager θ and Lazy θ payloads.
- Validate schema & numeric constraints at runtime.
- Materialize `theta` (lazy) honoring `numeric.dtype` (default float64).
- Decode with float64 arithmetic and nearest-grid snapping.
- Verify `meta.hash_raw` if present.

---

## 10. Backward/Forward Compatibility

- `pif_version` follows **SemVer**:
    - **Patch/minor** updates MUST be backward compatible within v1.
    - **Major** (`2.x.y`) MAY introduce breaking changes.
- Unknown/extra fields MUST be tolerated by consumers.
- Core invariants (`schema.alphabet`, `[0,2π)`, strict round-trip) are stable across v1.x.

---

## 11. Prohibitions (MVP)

When `meta.note == "no_processing"`:

- **No** modifications of `theta` beyond canonical encoding/wrapping.
- **No** resampling, filtering, compression, denoising, phase shifts, amplitude changes.
- **No** lossy quantization beyond the declared alphabet.

Any transformation MUST switch `meta.note` to `"processed:<ops>"` and invalidates the strict round-trip guarantee.

---

## 12. Examples

### 12.1 Eager θ (float64)

```json
{
  "pif_version": "1.2.0",
  "domain": "time_series",
  "schema": { "alphabet": { "type": "uint", "M": 256 } },
  "numeric": { "dtype": "float64", "phase_wrap": [0.0, 6.283185307179586] },
  "theta": [0.0, 0.024543692606, 0.049087385212, "..."],
  "amp": 1.0,
  "meta": {
    "note": "no_processing",
    "hash_raw": "sha256:2f0d...<64 hex>...",
    "codec": "S1_phase_code_M256",
    "codec_hash": "sha256:6a1b...<64 hex>..."
  }
}

```

### 12.2 Lazy θ (indices, float32 materialization)

```json
{
  "pif_version": "1.2.0",
  "domain": "time_series",
  "schema": { "alphabet": { "type": "uint", "M": 1024 } },
  "numeric": { "dtype": "float32", "precision_safe": true },
  "theta_lazy": true,
  "encoded_uint": [0, 1, 2, 3, "..."],
  "amp": 1.0,
  "meta": { "note": "no_processing", "codec": "S1_phase_code_M1024" }
}

```

---

## 13. Security & Privacy

- `meta.hash_raw` reveals an integrity fingerprint of the raw input. If raw data is sensitive, **do not** transmit raw; only the hash. Validate decoded output against the hash on the consumer side.
- PIF does not require storing raw data within the object. Keep confidential metadata out of PIF or encrypt externally.

---

## 14. Numerical Notes

- Producers SHOULD compute `theta = (2π/M)⋅n` in float64 for eager mode and store with enough precision in JSON.
- Consumers MUST decode with float64 and use nearest-grid snapping. An equivalent formula (implementation detail) is:
    [
    n = \left\lfloor \frac{M}{2\pi}\theta + 0.5 \right\rfloor \bmod M
    ]
- Valid producer data will be sufficiently close to exact grid nodes to make ties practically impossible.

---

This **PIF v1 Core** is deliberately small. It is the stable contract that underpins strict, lossless **discrete ↔ phase ↔ discrete** interchange across modalities. Future v1.x extensions may add optional, non-breaking fields (e.g., multi-channel layouts, chunked θ), but the guarantees above remain unchanged.
