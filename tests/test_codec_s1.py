import numpy as np
from phasebridge.codec_s1 import S1PhaseCodec
from phasebridge.pif import PIF

def test_roundtrip_uint8_random():
    rng = np.random.default_rng(0)
    x = rng.integers(0, 256, size=10000, dtype=np.uint8)
    codec = S1PhaseCodec(M=256, strict_range=True)
    schema = {"alphabet": {"type": "uint", "M": 256}}
    p = codec.encode(x, schema)
    xr = codec.decode(p)
    assert np.array_equal(x, xr)

def test_schema_mismatch():
    codec = S1PhaseCodec(M=256)
    x = np.array([0, 1, 2], dtype=np.uint8)
    bad_schema = {"alphabet": {"type": "uint", "M": 128}}
    try:
        codec.encode(x, bad_schema)
        assert False, "should raise"
    except ValueError:
        pass

def test_non_strict_mod():
    codec = S1PhaseCodec(M=256, strict_range=False)
    schema = {"alphabet": {"type": "uint", "M": 256}}
    x = np.array([0, 300], dtype=np.uint16)
    p = codec.encode(x, schema)
    xr = codec.decode(p)
    assert xr.tolist() == [0, 44]
