# src/phasebridge/codec_s1.py
from __future__ import annotations
import numpy as np
import hashlib
from typing import Dict, Any
from .pif import PIF, validate_pif
from .utils import choose_phase_dtype  # dtype policy

TWO_PI = 2.0 * np.pi


class S1PhaseCodec:
    """Strict phase codec (uintM ↔ θ), lossless round-trip.
    θ = 2π * n / M; decoding uses nearest lattice node; dtype chosen based on M / policy.
    """

    def __init__(self, M: int = 256, strict_range: bool = True):
        """M — alphabet size (2..2^32); strict_range=True enforces x ∈ [0, M-1]."""
        if not (2 <= int(M) <= (1 << 32)):
            raise ValueError("M must be in [2, 2^32]")
        self.M = int(M)
        self.strict_range = bool(strict_range)

    # ---------- helpers ----------
    @staticmethod
    def _sha256_bytes(b: bytes) -> str:
        return hashlib.sha256(b).hexdigest()

    @staticmethod
    def _min_uint_dtype(M: int):
        # Choose a dtype that safely accommodates arithmetic with M in ops like modulo.
        # Use strict upper bounds to avoid casting errors (e.g., 256 on uint8 in NumPy>=2.0).
        if M <= 255:
            return np.uint8
        if M <= 65535:
            return np.uint16
        if M <= 4294967295:
            return np.uint32
        return np.uint64

    @staticmethod
    def _min_uint_dtype_for_output(M: int):
        """Minimal unsigned dtype for decoding output values in [0, M-1].
        Uses inclusive upper bounds so that, e.g., M=256 decodes to uint8.
        """
        if M <= 256:
            return np.uint8
        if M <= 65536:
            return np.uint16
        if M <= 4294967296:
            return np.uint32
        return np.uint64

    def _codec_id(self) -> str:
        return f"S1_phase_code_M{self.M}"

    def _codec_hash(self) -> str:
        payload = self._codec_id().encode("utf-8")
        return self._sha256_bytes(payload)

    def _check_schema_compat(self, schema: Dict[str, Any]) -> None:
        # Minimal compatibility check: alphabet.type == 'uint', alphabet.M == self.M
        if "alphabet" not in schema or not isinstance(schema["alphabet"], dict):
            raise ValueError("schema.alphabet must be provided")
        alpha = schema["alphabet"]
        if alpha.get("type") != "uint":
            raise ValueError("schema.alphabet.type must be 'uint'")
        if int(alpha.get("M", -1)) != self.M:
            raise ValueError(f"schema.alphabet.M ({alpha.get('M')}) != codec.M ({self.M})")

    # ---------- API ----------
    def encode(
        self,
        x_uint: np.ndarray,
        schema: Dict[str, Any],
        *,
        lazy_theta: bool = False,
        prefer_float32: bool = False,
        allow_downgrade: bool = True
    ) -> PIF:
        """Discrete → phase (strict conversion, no processing).

        Args:
            x_uint: unsigned integer array of symbols in [0, M-1] (strict) or any (wrapped if not strict).
            schema: PIF schema dict; must match codec M and type 'uint'.
            lazy_theta: if True, store encoded_uint and defer θ materialization until first access.
            prefer_float32: if True, try to store θ as float32 when safe by policy.
            allow_downgrade: if True, fall back to float64 when float32 deemed unsafe.

        Returns:
            PIF object (eager θ or lazy-θ), with numeric policy recorded.
        """
        if not np.issubdtype(x_uint.dtype, np.unsignedinteger):
            raise ValueError("Input must be unsigned integer array.")
        self._check_schema_compat(schema)

        # Normalize range according to strict mode
        n64 = x_uint.astype(np.int64)
        if self.strict_range:
            if np.any(n64 < 0) or np.any(n64 >= self.M):
                raise ValueError(f"Values out of range [0, {self.M-1}] for strict mode")
            n_norm = n64
        else:
            n_norm = n64 % self.M

        # Decide phase dtype policy
        phase_dtype, precision_safe = choose_phase_dtype(self.M, prefer_float32, allow_downgrade)
        numeric = {
            "dtype": "float32" if phase_dtype == np.float32 else "float64",
            "precision_safe": bool(precision_safe),
        }

        # Meta
        raw_bytes = np.ascontiguousarray(x_uint).tobytes()
        meta = {
            "note": "no_processing",
            "hash_raw": f"sha256:{self._sha256_bytes(raw_bytes)}",
            "codec_hash": f"sha256:{self._codec_hash()}",
            "codec": self._codec_id(),
        }

        if lazy_theta:
            # Lazy-θ mode: store encoded_uint only; theta is materialized on first access using `numeric["dtype"]`.
            meta["theta_lazy"] = True  # informational
            out_dtype = self._min_uint_dtype_for_output(self.M)
            encoded_uint = n_norm.astype(out_dtype, copy=False)
            p = PIF(
                schema=schema,
                theta=None,
                amp=1.0,
                meta=meta,
                numeric=numeric,
                encoded_uint=encoded_uint,
                theta_lazy=True,
                _theta_cache=None,
            )
            validate_pif(p)
            return p

        # Eager θ mode: compute θ = 2π * n / M in chosen dtype
        theta = (TWO_PI * n_norm / self.M).astype(phase_dtype)
        p = PIF(schema=schema, theta=theta, amp=1.0, meta=meta, numeric=numeric)
        validate_pif(p)  # basic PIF validation
        return p

    def decode(self, p: PIF, verify_schema: bool = True) -> np.ndarray:
        """Phase → discrete (strict reversibility when meta.note == 'no_processing')."""
        if verify_schema:
            self._check_schema_compat(p.schema)

        # Obtain θ (materializes in lazy mode if needed); decode in float64 for stability
        theta = np.mod(p.theta_view.astype(np.float64), TWO_PI)
        n = np.rint(self.M * theta / TWO_PI).astype(np.int64) % self.M
        out_dtype = self._min_uint_dtype_for_output(self.M)
        return n.astype(out_dtype)
