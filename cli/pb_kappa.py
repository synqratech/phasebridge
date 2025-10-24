# cli/pb_kappa.py
from __future__ import annotations
import argparse, sys, json
from pathlib import Path
from typing import Optional
import numpy as np

from phasebridge.pif import PIF
from phasebridge.kappa import kappa_timeseries, kappa_timeseries_windowed

def _detect_pif_fmt(path: Optional[Path], explicit: Optional[str]) -> str:
    if explicit:
        return explicit
    if path is None:
        return "json"  # stdin default
    suf = path.suffix.lower()
    if suf in (".mp", ".msgpack", ".mpk"):
        return "msgpack"
    if suf in (".cbor", ".cbor2"):
        return "cbor"
    if suf == ".npz":
        return "npz"
    return "json"

def _load_pif_json_bytes(b: bytes) -> PIF:
    s = b.decode("utf-8")
    return PIF.from_json(s, validate=True)

def main():
    ap = argparse.ArgumentParser(
        description="Compute κ from PIF (global or windowed)"
    )
    ap.add_argument("--in", dest="inp", default="-", help="input PIF file or '-' for stdin")
    ap.add_argument("--pif-fmt", dest="pif_fmt", choices=["json","msgpack","cbor","npz"], default=None,
                    help="PIF format (auto by ext; stdin default=json)")
    ap.add_argument("--weighted", action="store_true", help="use amp as weights if amp is an array")
    ap.add_argument("--win", type=int, default=None, help="window size (samples) for windowed κ")
    ap.add_argument("--hop", type=int, default=None, help="hop size (samples) for windowed κ")
    ap.add_argument("--fmt", choices=["plain","json","csv"], default="plain",
                    help="output format (default: plain; windowed: csv/json recommended)")
    args = ap.parse_args()

    # read PIF
    if args.inp == "-" or not args.inp.strip():
        b = sys.stdin.buffer.read()
        in_path = None
    else:
        in_path = Path(args.inp)
        if not in_path.exists():
            ap.error(f"Input file not found: {in_path}")
        b = in_path.read_bytes()

    pif_fmt = _detect_pif_fmt(in_path, args.pif_fmt)
    if pif_fmt == "json":
        p = _load_pif_json_bytes(b)
    else:
        p = PIF.from_bytes(b, fmt=pif_fmt, validate=True)

    # compute kappa
    if args.win is None or args.hop is None:
        val = kappa_timeseries(p, weighted=args.weighted, validate=False)
        if args.fmt == "plain":
            print(f"{val:.12f}")
        elif args.fmt == "json":
            print(json.dumps({"kappa": float(val)}, ensure_ascii=False))
        else:  # csv
            sys.stdout.write("kappa\n")
            sys.stdout.write(f"{val:.12f}\n")
            sys.stdout.flush()
    else:
        centers, vals = kappa_timeseries_windowed(
            p, win=int(args.win), hop=int(args.hop),
            weighted=args.weighted, validate=False
        )
        if args.fmt == "json":
            out = {"centers": centers.tolist(), "kappa": [float(v) for v in vals]}
            print(json.dumps(out, ensure_ascii=False))
        else:
            # csv (default for windowed in plain/csv modes)
            sys.stdout.write("center_idx,kappa\n")
            for c, v in zip(centers, vals):
                sys.stdout.write(f"{int(c)},{v:.12f}\n")
            sys.stdout.flush()

if __name__ == "__main__":
    main()
