# tests/test_kappa_timeseries.py
import numpy as np
from phasebridge.pif import PIF
from phasebridge.kappa import kappa_timeseries, kappa_timeseries_windowed, TWO_PI

def _mk_pif(theta, amp=1.0):
    # minimal valid PIF for tests
    schema = {"alphabet": {"type": "uint", "M": 256}}
    return PIF(schema=schema, theta=np.asarray(theta, dtype=np.float64), amp=amp, meta={"note": "no_processing"})

def test_kappa_bounds_unweighted():
    # uniform phase distribution → κ close to 0
    th = np.linspace(0.0, TWO_PI, 1024, endpoint=False)
    p = _mk_pif(th)
    k = kappa_timeseries(p, weighted=False)
    assert 0.0 <= k <= 1.0
    assert k < 0.05  # almost decoherent

def test_kappa_constant_phase_is_one():
    th = np.zeros(1000, dtype=np.float64)            # all phases are identical
    p = _mk_pif(th)
    k = kappa_timeseries(p, weighted=False)
    assert abs(k - 1.0) < 1e-12

def test_kappa_weighted_equals_unweighted_for_const_amp():
    rng = np.random.default_rng(0)
    th = rng.random(2048) * TWO_PI
    p = _mk_pif(th, amp=1.0)  # scalar -> equivalent to unweighted
    k_u = kappa_timeseries(p, weighted=False)
    k_w = kappa_timeseries(p, weighted=True)
    assert abs(k_u - k_w) < 1e-12

def test_kappa_weighted_changes_with_amp_profile():
    # two clusters of phases; amplitude highlights one of them
    th = np.concatenate([np.zeros(500), np.ones(500) * np.pi])
    amp = np.concatenate([np.ones(500), np.ones(500) * 10.0])
    p = _mk_pif(th, amp=amp)
    k_u = kappa_timeseries(p, weighted=False)
    k_w = kappa_timeseries(p, weighted=True)
    # weighted should shift towards one phase group => usually changes k
    assert abs(k_u - k_w) > 1e-6

def test_windowed_basic_and_single_window_fallback():
    th = np.zeros(100)  # perfect coherence
    p = _mk_pif(th)
    centers, ks = kappa_timeseries_windowed(p, win=50, hop=25, weighted=False)
    assert centers.shape[0] == ks.shape[0] > 0
    assert np.allclose(ks, 1.0, atol=1e-12)

    # window larger than signal -> single measurement over entire signal
    centers2, ks2 = kappa_timeseries_windowed(p, win=200, hop=25, weighted=False)
    assert ks2.shape == (1,)
    assert abs(ks2[0] - 1.0) < 1e-12
