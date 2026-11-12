#!/usr/bin/env python3
"""Bounded, stdlib-only codebase navigation map."""
from __future__ import annotations
import argparse, ast, json, os
from pathlib import Path
IGNORED={".git","node_modules","vendor","dist","build","target",".venv","venv","__pycache__",".next"}
EXT={".py",".js",".ts",".tsx",".jsx",".go",".rs",".rb",".php",".java",".cs"}
def symbols(p):
    if p.suffix != ".py": return []
    try: tree=ast.parse(p.read_text(encoding="utf-8",errors="ignore"))
    except (OSError,SyntaxError,UnicodeError): return []
    return [f"{type(n).__name__.lower()} {n.name}" for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))][:40]
def generate(root,out,max_files,max_bytes,since=None):
    root=root.resolve(); prior={}
    if since and since.is_file():
        try: prior=json.loads(since.read_text()).get("files",{})
        except (OSError,ValueError): prior={}
    rows=[]; used=0
    for base,dirs,files in os.walk(root):
        dirs[:]=sorted(d for d in dirs if d not in IGNORED and not d.startswith("."))
        for name in sorted(files):
            p=Path(base)/name
            if p.suffix not in EXT: continue
            rel=p.relative_to(root).as_posix(); stat=p.stat()
            if prior and prior.get(rel)==stat.st_mtime_ns: continue
            if len(rows)>=max_files or used+stat.st_size>max_bytes: break
            rows.append((rel,stat.st_size,stat.st_mtime_ns,symbols(p))); used+=stat.st_size
        if len(rows)>=max_files or used>=max_bytes: break
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text("# Code Base Map\n\n"+"\n".join(f"- `{r}` ({size} bytes)"+(" — "+", ".join(syms) if syms else "") for r,size,_,syms in rows)+"\n",encoding="utf-8")
    out.with_suffix(".json").write_text(json.dumps({"files":{r:m for r,_,m,_ in rows},"count":len(rows),"bytes":used},indent=2)+"\n")
def main(argv=None):
    ap=argparse.ArgumentParser(); ap.add_argument("root",type=Path); ap.add_argument("--out",type=Path,required=True); ap.add_argument("--max-files",type=int,default=1000); ap.add_argument("--max-bytes",type=int,default=120000); ap.add_argument("--since",type=Path); a=ap.parse_args(argv); generate(a.root,a.out,a.max_files,a.max_bytes,a.since); return 0
if __name__=="__main__": raise SystemExit(main())
