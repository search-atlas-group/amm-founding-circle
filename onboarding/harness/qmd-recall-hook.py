#!/usr/bin/env python3
"""UserPromptSubmit hook: push brain recall to the agent.
Extract keywords -> qmd search with back-off -> inject <=3 new hits (>=90%, no raw captures) as context.
Single process. Per-session dedupe: a path already injected this session is not repeated.
Silent on short prompts, slash/! commands, missing qmd, errors. Budget ~100ms, <700 bytes."""
import sys, json, re, os, subprocess, shutil, hashlib

STOP=set("""a an the and or but if then else when where why how what which who whom this that these those is are was were be been being
have has had do does did doing will would shall should can could may might must of in on at to for from by with about into over after
before under between through during without within along across behind beyond up down out off again further once here there all any
both each few more most other some such no nor not only own same so than too very just also ever never still yet i me my we our you your
he him his she her it its they them their us am let lets please want need like make made get got give go going went come came take took
use used using find found look looking check see show tell said say says stay stayed change changed keep kept run ran try tried thing things
something anything way ways new old first last long same different back around remind decide decided asking asked ask explain describe
summarize summary help wonder wondering curious quick quickly maybe actually really basically""".split())

def stem(w):
    for suf,minlen in (("ations",4),("ation",4),("ings",4),("ing",4),("ed",4),("s",3)):
        if w.endswith(suf) and len(w)-len(suf)>=minlen and not w.endswith("ss"): return w[:-len(suf)]
    return w

def keywords(text):
    out=[]
    for w in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", text.lower()):
        if w in STOP: continue
        w=stem(w)
        if w not in out: out.append(w)
    return out[:8]

def parse(raw):
    hits=[];cur={}
    for l in raw.splitlines():
        if l.startswith("qmd://"): cur={"path":l.split()[0][6:]}
        elif l.startswith("Title:"): cur["title"]=l[6:].strip()
        elif l.startswith("Score:"):
            try: s=int(l[6:].strip().rstrip("%"))
            except ValueError: s=0
            if s>=90 and "/captures/" not in cur.get("path",""): cur["score"]=s; hits.append(cur)
            cur={}
    return hits

def main():
    try: d=json.load(sys.stdin)
    except Exception: return
    prompt=(d.get("prompt") or "").strip()
    if len(prompt)<25 or prompt[0] in "/!": return
    qmd=shutil.which("qmd") or "/opt/homebrew/bin/qmd"
    if not os.access(qmd,os.X_OK): return
    kw=keywords(prompt)
    hits=[]
    while len(kw)>=3:
        try:
            raw=subprocess.run([qmd,"search"," ".join(kw),"-n","4"],capture_output=True,text=True,timeout=3).stdout
        except Exception: return
        hits=parse(raw)
        if hits: break
        kw=kw[:-1]
    if not hits: return
    sid=d.get("session_id") or "nosession"
    state=os.path.join(os.environ.get("TMPDIR","/tmp"),"qmd-recall-"+hashlib.sha1(sid.encode()).hexdigest()[:12])
    seen=set(open(state).read().split("\n")) if os.path.exists(state) else set()
    new=[h for h in hits if h["path"].split(":")[0] not in seen][:3]
    if not new: return
    with open(state,"a") as f:
        for h in new: f.write(h["path"].split(":")[0]+"\n")
    lines="\n".join("- %s — %s (%d%%)"%(h.get("title","")[:70],h["path"],h["score"]) for h in new)
    print(json.dumps({"hookSpecificOutput":{"hookEventName":"UserPromptSubmit",
        "additionalContext":"Brain recall (qmd; read the file if relevant, do not re-ask JD):\n"+lines}}))

if __name__=="__main__": main()
