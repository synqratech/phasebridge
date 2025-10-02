# tests/test_api_contract.py
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import numpy as np
import pytest

from phasebridge.codec_s1 import S1PhaseCodec
from phasebridge.utils import sha256_of_array


def test_encode_sets_no_processing_and_hash():
    codec = S1PhaseCodec(M=256)
    x = np.arange(0, 256, dtype=np.uint8)
    schema = {"alphabet": {"type": "uint", "M": 256}}
    p = codec.encode(x, schema)

    assert p.meta.get("note") == "no_processing"
    assert isinstance(p.meta.get("codec"), str)
    assert isinstance(p.meta.get("codec_hash"), str)

    # The hash of the raw data matches the hash of the decoded data
    x_rec = codec.decode(p)
    assert np.array_equal(x, x_rec)
    assert p.meta.get("hash_raw") == sha256_of_array(x_rec)


def test_schema_incompat_raises():
    codec = S1PhaseCodec(M=256)
    x = np.array([0, 1, 2], dtype=np.uint8)
    bad_schema = {"alphabet": {"type": "uint", "M": 128}}
    with pytest.raises(ValueError):
        codec.encode(x, bad_schema)


def test_roundtrip_report_utility():
    from phasebridge.utils import verify_roundtrip
    codec = S1PhaseCodec(M=16)
    x = np.array([0, 1, 2, 15], dtype=np.uint8)
    schema = {"alphabet": {"type": "uint", "M": 16}}
    ok, report = verify_roundtrip(x, codec, schema)
    assert ok
    assert report["N"] == 4
    assert report["M"] == 16
