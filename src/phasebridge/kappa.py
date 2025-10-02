# src/phasebridge/kappa.py
from __future__ import annotations
import numpy as np
from typing import Tuple
from .pif import PIF, validate_pif

TWO_PI = 2.0 * np.pi

def _compute_kappa(theta: np.ndarray, weights: np.ndarray | None = None) -> float:
    """
    Direct computation of κ = |⟨e^{iθ}⟩| (if weights=None) or
    κ_w = |Σ w_j e^{iθ_j} / Σ w_j| (if weights != None).
    All computations are in float64; phases are wrapped to [0, 2π).
    """
    th = np.mod(theta.astype(np.float64), TWO_PI)
    z = np.exp(1j * th)

    if weights is None:
        return float(np.abs(z.mean()))

    w = np.asarray(weights, dtype=np.float64)
    if w.ndim != 1 or w.shape[0] != th.shape[0]:
        raise ValueError("weights shape must be (N,) and match theta shape")
    s = w.sum()
    if not np.isfinite(s) or s <= 0.0:
        raise ValueError("weights must sum to a positive finite value")
    return float(np.abs((w * z).sum() / s))

def kappa_timeseries(p: PIF, weighted: bool = False, validate: bool = False) -> float:
    """
    κ for a timeseries in PIF format.
    - weighted=False: κ = |mean(exp(iθ))|
    - weighted=True:  κ = |Σ w_j exp(iθ_j) / Σ w_j|, where w = amp (if amp is an array);
                      otherwise, if amp is scalar, the unweighted version is used.
    validate=True enables basic PIF validation (optional if already validated earlier).
    """
    if validate:
        validate_pif(p)

    if isinstance(p.amp, np.ndarray) and weighted:
        return _compute_kappa(p.theta, weights=p.amp)
    return _compute_kappa(p.theta, weights=None)

def kappa_timeseries_windowed(
    p: PIF,
    win: int,
    hop: int,
    weighted: bool = False,
    validate: bool = False
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Windowed κ along the time axis.
    Returns: centers (indices of window centers), kappas (κ for each window).
    - win: window size (in samples)
    - hop: window step (in samples)
    """
    if validate:
        validate_pif(p)

    theta = np.asarray(p.theta, dtype=np.float64)
    N = theta.shape[0]
    if win <= 0 or hop <= 0:
        raise ValueError("win and hop must be positive integers")
    if win > N:
        # single window over the entire signal
        w = p.amp if (weighted and isinstance(p.amp, np.ndarray)) else None
        return np.array([ (N-1)/2.0 ]), np.array([ _compute_kappa(theta, w) ])

    centers = []
    kappas = []
    idx = 0
    while idx + win <= N:
        sl = slice(idx, idx + win)
        w = None
        if weighted and isinstance(p.amp, np.ndarray):
            w = p.amp[sl]
        centers.append(idx + (win - 1) / 2.0)
        kappas.append(_compute_kappa(theta[sl], weights=w))
        idx += hop

    return np.asarray(centers, dtype=np.float64), np.asarray(kappas, dtype=np.float64)
