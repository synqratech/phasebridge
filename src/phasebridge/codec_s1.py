# src/phasebridge/codec_s1.py
from __future__ import annotations
import numpy as np
import hashlib
from typing import Dict, Any
from .pif import PIF, validate_pif

TWO_PI = 2.0 * np.pi

class S1PhaseCodec:
    """Strict phase codec (uintM ↔ θ), lossless round-trip.
    θ = 2π * n / M; decoding uses nearest lattice node; dtype chosen based on M.
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
    def encode(self, x_uint: np.ndarray, schema: Dict[str, Any]) -> PIF:
        """Discrete → phase (strict conversion, no processing)."""
        if not np.issubdtype(x_uint.dtype, np.unsignedinteger):
            raise ValueError("Input must be unsigned integer array.")
        self._check_schema_compat(schema)

        n = x_uint.astype(np.int64)
        if self.strict_range:
            if np.any(n < 0) or np.any(n >= self.M):
                raise ValueError(f"Values out of range [0, {self.M-1}] for strict mode")
        else:
            n = n % self.M

        theta = (TWO_PI * n / self.M).astype(np.float64)

        raw_bytes = np.ascontiguousarray(x_uint).tobytes()
        meta = {
            "note": "no_processing",
            "hash_raw": f"sha256:{self._sha256_bytes(raw_bytes)}",
            "codec_hash": f"sha256:{self._codec_hash()}",
            "codec": self._codec_id(),
        }

        p = PIF(schema=schema, theta=theta, amp=1.0, meta=meta)
        validate_pif(p)  # basic PIF validation
        return p

    def decode(self, p: PIF, verify_schema: bool = True) -> np.ndarray:
        """Phase → discrete (strict reversibility when meta.note == 'no_processing')."""
        if verify_schema:
            self._check_schema_compat(p.schema)
        theta = np.mod(p.theta.astype(np.float64), TWO_PI)
        n = np.rint(self.M * theta / TWO_PI).astype(np.int64) % self.M
        out_dtype = self._min_uint_dtype_for_output(self.M)
        return n.astype(out_dtype)
