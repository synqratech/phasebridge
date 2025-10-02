# PIF v1 — Core Specification (Strict, Lossless)

**Phase Interchange Format (PIF)** is a minimal, versioned container for representing discrete data as **continuous phase** values and back **without loss**. This document defines the **normative core** of PIF v1 used by PhaseBridge MVP.

Scope here is the **strict conversion layer**: no processing, no filtering, no compression. If a PIF object declares `meta.note: "no_processing"`, decoding MUST reproduce the original discrete input **bit-exactly** with respect to the declared alphabet.

---

## 1. Terminology

* **Producer**: component that creates a PIF object from discrete input (encoder).
* **Consumer**: component that reads PIF and reconstructs the discrete data (decoder).
* **Alphabet**: finite set of discrete symbols `{0,…,M-1}`.
* **S1PhaseCodec(M)**: canonical lossless mapping `uintM ↔ θ ∈ [0,2π)`.

---

## 2. Data Model (Object Members)

A PIF object is a JSON (or MessagePack) object with the following members. JSON is the **normative** serialization; MessagePack is allowed with identical semantics.

| Field         | Type              | Required | Description                                                                  |
| ------------- | ----------------- | -------- | ---------------------------------------------------------------------------- |
| `pif_version` | string            | optional | SemVer of the PIF format (e.g., `"1.0.0"`).                                  |
| `domain`      | string            | optional | Informational (e.g., `"time_series"`, `"image"`).                            |
| `schema`      | object            | **yes**  | Minimal schema for reconstruction (see §3).                                  |
| `numeric`     | object            | optional | Numeric hints; default implied (see §3.3).                                   |
| `codec`       | object            | optional | Codec identifiers (informational in MVP).                                    |
| `theta`       | number[]          | **yes**  | Phases, **float64**, **wrapped** to `[0,2π)`. Length `N ≥ 1`.                |
| `amp`         | number | number[] | optional | Amplitude. MVP defaults to scalar `1.0`. If array, length `N`, values `≥ 0`. |
| `meta`        | object            | **yes**  | Operational metadata (see §4).                                               |

> **Normative types:** `theta` MUST be interpreted as IEEE-754 **float64**; consumers MUST coerce to float64 before use. `amp` scalar MUST be a finite number; if array, MUST be float64 and finite.

---

## 3. Schema & Numeric Constraints

### 3.1 `schema.alphabet` (required)

```json
"schema": {
  "alphabet": { "type": "uint", "M": 256 },
  "...": "other optional keys"
}
```

* `type` MUST be `"uint"`.
* `M` MUST be integer `2 ≤ M ≤ 2^32`.
* This defines the round-trip alphabet `{0,…,M-1}`.

### 3.2 `schema.sampling` (optional)

```json
"schema": {
  "sampling": { "fs": 100.0 }
}
```

* `fs` (Hz) MUST be a positive finite number if present.

### 3.3 `numeric` (optional)

If omitted, the following defaults are assumed:

```json
"numeric": {
  "dtype": "float64",
  "phase_wrap": [0.0, 6.283185307179586]
}
```

* `dtype` MUST be `"float64"` for `theta`.
* `phase_wrap` indicates that `theta` values are wrapped to `[0, 2π)`. Producers MUST store wrapped values; consumers MAY re-wrap defensively.

### 3.4 `theta` and `amp` payload

* `theta`: array of length `N ≥ 1`, **finite** float64, each value `0.0 ≤ θ < 2π`. `NaN`/`±∞` are forbidden.
* `amp` (MVP): scalar `1.0`. If provided as array, it MUST:

  * have length `N`,
  * be float64,
  * contain finite values `≥ 0`.

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

* `meta.note` is **required**.

  * `"no_processing"` means the payload was produced by a pure conversion and MUST round-trip bit-exactly.
  * `"processed:<ops>"` (future) indicates transformations beyond conversion (then strict round-trip is not guaranteed).
* `meta.hash_raw` (optional but RECOMMENDED): SHA-256 of the original discrete input bytes, encoded as `"sha256:<hex64>"`. Consumers SHOULD verify `sha256(decoded) == meta.hash_raw`.
* `meta.codec` (optional): stable codec identifier string (e.g., `"S1_phase_code_M256"`).
* `meta.codec_hash` (optional): SHA-256 fingerprint of the codec identity string (or binary).

`codec` object (optional) MAY mirror identifiers:

```json
"codec": { "forward": "S1_phase_code_M256", "inverse": "S1_phase_decode_M256" }
```

---

## 5. Canonical Codec (S1PhaseCodec)

**Encoding (Producer):** for `M ≥ 2`, input array `x` of unsigned integers with values in `[0, M-1]`:

[
\theta_i ;=; \frac{2\pi}{M}; x_i
]

* Store `theta` as float64, wrapped to `[0, 2π)`.
* Set `amp = 1.0` (MVP).
* Set `meta.note = "no_processing"`.
* Compute `meta.hash_raw = "sha256:" + SHA256(bytes(x))`.

**Decoding (Consumer):** for phases `θ`:

[
n_i ;=; \operatorname{round}!\left(\frac{M}{2\pi};\theta_i\right) \bmod M
]

* `round` is **nearest integer**; any tie-breaking is acceptable. With valid producer data, exact ties are not expected.
* Output dtype MUST be the minimal unsigned integer type that can represent `[0, M-1]`:

  * `M ≤ 256` → `uint8`
  * `M ≤ 65536` → `uint16`
  * `M ≤ 2^32` → `uint32`
  * otherwise `uint64` (not used in MVP).

> **Note:** Producers MAY optionally support a non-strict modular input mode before encoding, but for MVP strict mode is assumed: inputs MUST satisfy `0 ≤ x < M`, otherwise the producer MUST error.

---

## 6. Lossless Round-Trip Contract

For PIF with `meta.note == "no_processing"` and a valid `schema.alphabet.M`:

* **Correctness**: `decode(encode(x)) == x` **bit-exact**, for all arrays `x` with elements in `[0, M-1]`.
* **Stability**: `theta` MUST be stored with float64 precision; consumers MUST decode using float64 arithmetic and nearest-grid snapping.
* **Validation**: If `meta.hash_raw` is present, consumers SHOULD verify:

```
sha256(decoded_bytes) == meta.hash_raw
```

A PIF that violates numeric or schema constraints MUST be rejected.

---

## 7. Serialization

### 7.1 JSON (normative)

* Numbers in `theta`/`amp` MUST be interpreted as float64. Producers SHOULD emit sufficient precision (≥17 significant digits) to ensure round-trip through JSON text.
* Object member order is insignificant.
* Unknown fields MUST be ignored by consumers (forward compatibility).

### 7.2 MessagePack (optional)

* Use native numeric types; `theta` MUST decode to float64.
* Same field names and semantics as JSON.

---

## 8. JSON Schema

The normative JSON Schema for PIF v1 (core) is provided in the repo:

* `schemas/pif_v1.json` (authoritative)
* `schemas/pif_v1.yaml` (human-readable mirror)

Consumers MAY use JSON Schema validation; **runtime validation** of numeric/range constraints is still REQUIRED (e.g., float64 coercion, phase range, amp shape).

---

## 9. Conformance

* **Producer conformance** requires:

  * Emitting required fields (`schema`, `theta`, `meta.note`),
  * Wrapping phases to `[0,2π)`,
  * Using float64 for `theta` (and amp array if present),
  * Setting `meta.note = "no_processing"` for pure conversion,
  * (Recommended) populating `meta.hash_raw`, `meta.codec`, `meta.codec_hash`,
  * Emitting a valid `schema.alphabet` with correct `M`.

* **Consumer conformance** requires:

  * Validating schema & numeric constraints,
  * Coercing `theta` to float64, re-wrapping if needed,
  * Nearest-grid decoding with minimal unsigned dtype,
  * Verifying `meta.hash_raw` if present.

---

## 10. Backward/Forward Compatibility

* `pif_version` follows **SemVer**:

  * **Patch/minor** updates MUST be backward compatible within v1.
  * **Major** (`2.x.y`) MAY introduce breaking changes.
* Unknown/extra fields MUST be tolerated by consumers.
* Core invariants (float64 `theta`, `[0,2π)`, `schema.alphabet`) are stable across all v1.x releases.

---

## 11. Prohibitions (MVP)

When `meta.note == "no_processing"`:

* **No** modifications of `theta` beyond canonical encoding/wrapping.
* **No** resampling, filtering, compression, denoising, phase shifts, amplitude changes.
* **No** lossy quantization beyond the declared alphabet.

Any transformation MUST switch `meta.note` to `"processed:<ops>"` and invalidates the strict round-trip guarantee.

---

## 12. Examples

### 12.1 Minimal time-series PIF

```json
{
  "pif_version": "1.0.0",
  "domain": "time_series",
  "schema": {
    "alphabet": { "type": "uint", "M": 256 },
    "sampling": { "fs": 100.0 }
  },
  "numeric": { "dtype": "float64", "phase_wrap": [0.0, 6.283185307179586] },
  "codec": { "forward": "S1_phase_code_M256", "inverse": "S1_phase_decode_M256" },
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

### 12.2 Image (8-bit grayscale) PIF (non-normative extension fields)

```json
{
  "pif_version": "1.0.0",
  "domain": "image",
  "schema": {
    "alphabet": { "type": "uint", "M": 256 },
    "image": { "height": 256, "width": 256, "mode": "L" }
  },
  "theta": ["... float64 phases ..."],
  "amp": 1.0,
  "meta": { "note": "no_processing", "codec": "S1_phase_code_M256" }
}
```

---

## 13. Security & Privacy

* `meta.hash_raw` reveals an integrity fingerprint of the raw input. If raw data is sensitive, **do not** transmit raw; only the hash. Validate decoded output against the hash on the consumer side.
* PIF does not require storing raw data within the object. Keep confidential metadata out of PIF or encrypt externally.

---

## 14. Numerical Notes

* Producers SHOULD compute `theta = (2π/M) * n` in float64 and store as text with enough precision in JSON.
* Consumers MUST decode with float64 and use **nearest-grid** snapping. An equivalent formula to avoid library-specific rounding modes is:

[
n = \left\lfloor \frac{M}{2\pi}\theta + 0.5 \right\rfloor \bmod M
]

* Valid producer data will be sufficiently close to exact grid nodes to make ties practically impossible.

---

This **PIF v1 Core** is deliberately small. It is the stable contract that underpins strict, lossless **discrete ↔ phase ↔ discrete** interchange across modalities. Future v1.x extensions may add optional, non-breaking fields (e.g., multi-channel layouts, chunked θ), but the guarantees above remain unchanged.
