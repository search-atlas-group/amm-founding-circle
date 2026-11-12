#!/usr/bin/env python3
"""Bounded, offline token-ledger summary; never infers quota."""
from __future__ import annotations
import argparse, json
from collections import defaultdict
from pathlib import Path

def summarize(path: Path, limit: int = 100_000) -> dict:
    totals=defaultdict(lambda: {"calls":0,"tokens":0,"token_records":0})
    errors=0
    with path.open(encoding="utf-8") as fh:
        for n,line in enumerate(fh):
            if n >= limit: break
            try: row=json.loads(line)
            except (json.JSONDecodeError, TypeError): errors += 1; continue
            if not isinstance(row,dict): continue
            provider=str(row.get("provider") or row.get("model_provider") or "unknown")
            bucket=totals[provider]; bucket["calls"] += 1
            val=row.get("tokens", row.get("total_tokens"))
            if isinstance(val,(int,float)) and val >= 0:
                bucket["tokens"] += val; bucket["token_records"] += 1
            else:
                parts=[row.get(k) for k in ("input_tokens","output_tokens")]
                if all(isinstance(v,(int,float)) and v >= 0 for v in parts):
                    bucket["tokens"] += sum(parts); bucket["token_records"] += 1
    return {"quota":"UNKNOWN (not exposed by local ledger)","providers":dict(totals),"malformed_records":errors,"bounded":True}

def main(argv=None):
    ap=argparse.ArgumentParser(); ap.add_argument("--ledger",type=Path,required=True); args=ap.parse_args(argv)
    if not args.ledger.is_file(): ap.error(f"ledger not found: {args.ledger}")
    print(json.dumps(summarize(args.ledger),indent=2,sort_keys=True)); return 0
if __name__ == "__main__": raise SystemExit(main())
