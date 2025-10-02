# src/phasebridge/errors.py
from __future__ import annotations

class PhaseBridgeError(Exception):
    """Base exception for the phasebridge library."""
    pass


# --- Schema / Validation ---
class SchemaError(PhaseBridgeError):
    """Schema format/content error."""
    pass

class SchemaValidationError(SchemaError):
    """PIF validation against schema failed."""
    pass

class IncompatibleSchemaError(SchemaError):
    """Schema incompatible with selected codec/parameters."""
    pass


# --- Codecs / Formats ---
class CodecError(PhaseBridgeError):
    """Codec error (encode/decode)."""
    pass

class PhaseFormatError(PhaseBridgeError):
    """Invalid phase/amplitude format."""
    pass

class RoundTripError(PhaseBridgeError):
    """Round-trip contract violation (decode(encode(x)) != x)."""
    pass


# --- Kappa / Metrics ---
class KappaError(PhaseBridgeError):
    """Error computing coherence κ."""
    pass


# --- Misc ---
class NotSupportedError(PhaseBridgeError):
    """Not yet supported (feature flag / roadmap)."""
    pass
