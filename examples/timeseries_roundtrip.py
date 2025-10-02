# examples/timeseries_roundtrip.py
from __future__ import annotations
import argparse
from pathlib import Path
import hashlib
import json
import sys
import numpy as np

from phasebridge.codec_s1 import S1PhaseCodec
from phasebridge.pif import PIF
from phasebridge.kappa import kappa_timeseries


def sha256_of_array(arr: np.ndarray) -> str:
    a = np.ascontiguousarray(arr)
    return "sha256:" + hashlib.sha256(a.tobytes()).hexdigest()


def load_csv_uint(path: Path, dtype: np.dtype) -> np.ndarray:
    arr = np.loadtxt(path, delimiter=",", dtype=dtype)
    if arr.ndim != 1:
        arr = arr.ravel()
    return np.ascontiguousarray(arr)


def save_csv_uint(path: Path, x: np.ndarray) -> None:
    # save as integers, comma delimiter
    np.savetxt(path, x, fmt="%d", delimiter=",")


def synth_series_uint(M: int, N: int = 2000, fs: float = 100.0, dtype: str = "uint8") -> np.ndarray:
    """
    Generate a synthetic sensor-like timeseries, quantized to [0, M-1].
    """
    t = np.arange(N) / fs
    s = 0.45*np.sin(2*np.pi*1.2*t) + 0.35*np.sin(2*np.pi*3.1*t + 0.6)
    s += 0.05*np.random.default_rng(0).standard_normal(size=N)
    # масштабируем к [0, M-1]
    s = (s - s.min()) / (s.max() - s.min() + 1e-12)
    x = np.floor(s * (M - 1) + 0.5).astype(np.int64)  # ближайший уровень
    x = np.clip(x, 0, M-1).astype(dtype)
    return x


def main():
    ap = argparse.ArgumentParser(
        description="Timeseries round-trip demo: CSV(uint) -> PIF(JSON) -> CSV(uint) with strict equality"
    )
    ap.add_argument("--in-csv", required=True, help="input CSV with integer values [0, M-1]")
    ap.add_argument("--out-pif", required=True, help="path to save PIF JSON")
    ap.add_argument("--out-csv", required=True, help="path to save reconstructed CSV")
    ap.add_argument("--M", type=int, default=256, help="alphabet size (default 256)")
    ap.add_argument("--dtype", default="uint8", help="I/O dtype (default uint8)")
    ap.add_argument("--fs", type=float, default=None, help="sampling frequency (optional)")
    ap.add_argument("--synth", action="store_true", help="generate synthetic data into --in-csv and then perform round-trip")
    ap.add_argument("--N", type=int, default=2000, help="length of synthetic series for --synth (default 2000)")
    args = ap.parse_args()

    in_csv = Path(args.in_csv)
    out_pif = Path(args.out_pif)
    out_csv = Path(args.out_csv)
    M = int(args.M)
    dtype = np.dtype(args.dtype)

    # Generate synthetic data if requested
    if args.synth:
        x_synth = synth_series_uint(M=M, N=int(args.N), fs=float(args.fs or 100.0), dtype=args.dtype)
        save_csv_uint(in_csv, x_synth)
        print(f"[demo] synthetic series written to {in_csv} (N={x_synth.size}, M={M}, dtype={args.dtype})", file=sys.stderr)

    if not in_csv.exists():
        print(f"Input CSV not found: {in_csv}", file=sys.stderr)
        sys.exit(1)

    # 1) Load the input discrete series
    x = load_csv_uint(in_csv, dtype=dtype)

    # 2) Encode into PIF
    codec = S1PhaseCodec(M=M)
    schema = {"alphabet": {"type": "uint", "M": M}}
    if args.fs is not None:
        schema["sampling"] = {"fs": float(args.fs)}
    p = codec.encode(x, schema=schema)

    # 3) Save PIF as JSON
    out_pif.write_text(p.to_json(indent=2), encoding="utf-8")

    # 4) Decode PIF back
    p2 = PIF.from_json(out_pif.read_text(encoding="utf-8"), validate=True)
    x_rec = codec.decode(p2)

    # 5) Save reconstructed CSV
    save_csv_uint(out_csv, x_rec)

    # 6) Strict equality checks
    arrays_equal = bool(np.array_equal(x, x_rec))
    sha_in = sha256_of_array(x)
    sha_rec = sha256_of_array(x_rec)
    sha_meta = p.meta.get("hash_raw", None)
    hash_ok = (sha_meta is None) or (sha_in == sha_meta == sha_rec)

    # 7) κ-metric
    kappa_val = kappa_timeseries(p, weighted=False, validate=False)

    # 8) Report
    report = {
        "ok": arrays_equal and hash_ok,
        "N": int(x.size),
        "M": M,
        "dtype": str(dtype),
        "arrays_equal": arrays_equal,
        "sha256_in": sha_in,
        "sha256_rec": sha_rec,
        "sha256_meta": sha_meta,
        "hash_ok": hash_ok,
        "kappa": float(kappa_val),
        "in_csv": str(in_csv),
        "out_pif": str(out_pif),
        "out_csv": str(out_csv),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))

    # Exit code based on strict check result
    sys.exit(0 if report["ok"] else 2)


if __name__ == "__main__":
    main()
