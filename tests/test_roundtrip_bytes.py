# tests/test_roundtrip_bytes.py
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import numpy as np
import pytest

from phasebridge.codec_s1 import S1PhaseCodec
from phasebridge.pif import PIF, TWO_PI


def test_roundtrip_uint8_random():
    rng = np.random.default_rng(0)
    x = rng.integers(0, 256, size=50_000, dtype=np.uint8)
    codec = S1PhaseCodec(M=256, strict_range=True)
    schema = {"alphabet": {"type": "uint", "M": 256}}
    p = codec.encode(x, schema)
    xr = codec.decode(p)
    assert np.array_equal(x, xr)


def test_roundtrip_edges_uint8():
    x = np.array([0, 1, 2, 254, 255], dtype=np.uint8)
    codec = S1PhaseCodec(M=256, strict_range=True)
    schema = {"alphabet": {"type": "uint", "M": 256}}
    p = codec.encode(x, schema)
    xr = codec.decode(p)
    assert np.array_equal(x, xr)


@pytest.mark.parametrize("M", [2, 3, 7, 16, 256])
def test_various_M_roundtrip(M):
    rng = np.random.default_rng(1)
    dtype = np.uint8 if M <= 256 else np.uint16
    x = rng.integers(0, M, size=5000, dtype=dtype)
    codec = S1PhaseCodec(M=M, strict_range=True)
    schema = {"alphabet": {"type": "uint", "M": M}}
    p = codec.encode(x, schema)
    xr = codec.decode(p)
    assert np.array_equal(x, xr)


def test_pif_wrap_phase_ok():
    # Create PIF with 'bad' phases and ensure they get wrapped
    theta_bad = np.array([-1e-9, 2*np.pi + 1e-9, 10*np.pi], dtype=np.float64)
    p = PIF(schema={"alphabet": {"type": "uint", "M": 256}},
            theta=theta_bad, amp=1.0, meta={"note": "no_processing"})
    assert np.all(p.theta >= 0.0) and np.all(p.theta < TWO_PI + 1e-15)


def test_strict_range_enforced():
    codec = S1PhaseCodec(M=16, strict_range=True)
    schema = {"alphabet": {"type": "uint", "M": 16}}
    x = np.array([0, 15, 16], dtype=np.uint8)
    with pytest.raises(ValueError):
        codec.encode(x, schema)


def test_non_strict_mod_ok():
    codec = S1PhaseCodec(M=16, strict_range=False)
    schema = {"alphabet": {"type": "uint", "M": 16}}
    x = np.array([0, 15, 16, 31], dtype=np.uint8)
    p = codec.encode(x, schema)
    xr = codec.decode(p)
    assert xr.tolist() == [0, 15, 0, 15]
