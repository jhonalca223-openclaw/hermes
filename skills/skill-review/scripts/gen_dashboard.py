#!/usr/bin/env python3
"""
gen_dashboard.py - Render a static, self-contained HTML risk dashboard for a portfolio of
audited skills (Mode B). No server, no external assets, no network.

Input: one or more consolidated.json or verdict.json files (each has skill_name, counts,
findings, and optionally verdict). Output: a single .html file the user opens in a browser,
with a severity-sorted, filterable table and per-skill drill-down.

Usage:
    gen_dashboard.py results/*.json --out portfolio.html

Pure stdlib. Mirrors skill-creator's static-HTML eval-viewer approach.
"""

import argparse
import glob
import html
import json
import sys
from pathlib import Path

SEVS = ["critical", "high", "medium", "low", "info"]


def rollup_verdict(counts):
    if counts.get("critical"):
        return "BLOCK"
    if counts.get("high"):
        return "WARN"
    if counts.get("medium"):
        return "WARN"
    return "PASS"


def load(paths):
    rows = []
    for p in paths:
        try:
            d = json.loads(Path(p).read_text(encoding="utf-8"))
        except Exception as e:
            print(f"skip {p}: {e}", file=sys.stderr)
            continue
        counts = d.get("counts", {})
        rows.append({
            "skill_name": d.get("skill_name", Path(p).stem),
            "verdict": d.get("verdict") or rollup_verdict(counts),
            "counts": {s: counts.get(s, 0) for s in SEVS},
            "findings": d.get("findings", []),
            "degradations": d.get("degradations", []),
            "runtime": d.get("runtime", ""),
        })
    order = {"BLOCK": 0, "WARN": 1, "PASS": 2}
    rows.sort(key=lambda r: (order.get(r["verdict"], 3),
                             -r["counts"]["critical"], -r["counts"]["high"]))
    return rows


HTML_TMPL = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>skill-review portfolio</title>
<style>
:root{--bg:#0f1117;--card:#181b24;--fg:#e6e8ee;--mut:#9aa3b2;--bd:#272b36;
--crit:#ff5c5c;--high:#ff9f43;--med:#ffd23f;--low:#5cc8ff;--info:#7f8aa0;
--pass:#36d399;--warn:#ffb547;--block:#ff5c5c;}
*{box-sizing:border-box}body{margin:0;font:14px/1.5 system-ui,Segoe UI,Roboto,sans-serif;
background:var(--bg);color:var(--fg);padding:24px}
h1{font-size:20px;margin:0 0 4px}.sub{color:var(--mut);margin-bottom:16px}
.bar{display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap}
.bar button{background:var(--card);color:var(--fg);border:1px solid var(--bd);
border-radius:8px;padding:6px 12px;cursor:pointer}.bar button.active{border-color:var(--low)}
table{width:100%;border-collapse:collapse;background:var(--card);border-radius:10px;overflow:hidden}
th,td{padding:10px 12px;text-align:left;border-bottom:1px solid var(--bd)}
th{color:var(--mut);font-weight:600;cursor:pointer;user-select:none}
tr.skill{cursor:pointer}tr.skill:hover{background:#1e222d}
.v{font-weight:700;padding:2px 8px;border-radius:6px;font-size:12px}
.v.PASS{background:rgba(54,211,153,.15);color:var(--pass)}
.v.WARN{background:rgba(255,181,71,.15);color:var(--warn)}
.v.BLOCK{background:rgba(255,92,92,.15);color:var(--block)}
.pill{display:inline-block;min-width:20px;text-align:center;border-radius:5px;
padding:1px 6px;margin-right:3px;font-size:12px}
.c-critical{background:rgba(255,92,92,.2);color:var(--crit)}
.c-high{background:rgba(255,159,67,.2);color:var(--high)}
.c-medium{background:rgba(255,210,63,.2);color:var(--med)}
.c-low{background:rgba(92,200,255,.2);color:var(--low)}
.c-info{background:rgba(127,138,160,.2);color:var(--info)}
.detail{display:none;background:#12151c}.detail.open{display:table-row}
.detail td{padding:0}.finding{padding:10px 16px;border-bottom:1px solid var(--bd)}
.finding .meta{color:var(--mut);font-size:12px}.deg{color:var(--warn);font-size:12px}
code{background:#0c0e13;padding:1px 5px;border-radius:4px}
</style></head><body>
<h1>skill-review · portfolio risk dashboard</h1>
<div class="sub">__N__ skills · generated offline · click a row to expand findings</div>
<div class="bar">
<button data-f="ALL" class="active">All</button>
<button data-f="BLOCK">🔴 BLOCK</button>
<button data-f="WARN">🟡 WARN</button>
<button data-f="PASS">🟢 PASS</button>
</div>
<table id="t"><thead><tr>
<th data-k="skill_name">Skill</th><th data-k="verdict">Verdict</th>
<th data-k="critical">Severity counts</th><th data-k="runtime">Runtime</th>
</tr></thead><tbody id="b"></tbody></table>
<script>
const DATA = __DATA__;
const sevs=["critical","high","medium","low","info"];
let filter="ALL";
function counts(c){return sevs.map(s=>c[s]?`<span class="pill c-${s}">${c[s]}</span>`:"").join("")||"<span class=meta>none</span>";}
function esc(s){return (s||"").replace(/[&<>]/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[m]));}
function render(){
 const b=document.getElementById("b");b.innerHTML="";
 DATA.filter(r=>filter=="ALL"||r.verdict==filter).forEach((r,i)=>{
  const tr=document.createElement("tr");tr.className="skill";
  tr.innerHTML=`<td>${esc(r.skill_name)}</td><td><span class="v ${r.verdict}">${r.verdict}</span></td>`+
   `<td>${counts(r.counts)}</td><td class=meta>${esc(r.runtime)}</td>`;
  const d=document.createElement("tr");d.className="detail";
  let inner=r.degradations.map(x=>`<div class="finding deg">⚠ ${esc(x)}</div>`).join("");
  inner+=(r.findings.length?r.findings:[{title:"No findings",severity:"info"}]).map(f=>
   `<div class="finding"><span class="pill c-${f.severity||'info'}">${(f.severity||'info').toUpperCase()}</span> `+
   `<b>${esc(f.title||f.dimension||'')}</b><div class="meta">${esc(f.dimension||'')} · `+
   `${esc(f.file||'')}${f.locator?':'+esc(f.locator):''} · ${esc(f.evidence_summary||'')}</div></div>`).join("");
  d.innerHTML=`<td colspan=4>${inner}</td>`;
  tr.onclick=()=>d.classList.toggle("open");
  b.appendChild(tr);b.appendChild(d);
 });
}
document.querySelectorAll(".bar button").forEach(btn=>btn.onclick=()=>{
 document.querySelectorAll(".bar button").forEach(x=>x.classList.remove("active"));
 btn.classList.add("active");filter=btn.dataset.f;render();});
document.querySelectorAll("th").forEach(th=>th.onclick=()=>{
 const k=th.dataset.k;DATA.sort((a,b)=>{
  const av=k in a.counts?a.counts[k]:a[k],bv=k in b.counts?b.counts[k]:b[k];
  return (bv>av?1:bv<av?-1:0);});render();});
render();
</script></body></html>"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Static HTML risk dashboard")
    ap.add_argument("inputs", nargs="+", help="consolidated/verdict json files (globs ok)")
    ap.add_argument("--out", default="portfolio.html")
    args = ap.parse_args()

    paths = []
    for pat in args.inputs:
        paths += glob.glob(pat) if any(c in pat for c in "*?[") else [pat]
    rows = load(paths)
    if not rows:
        print("no inputs loaded", file=sys.stderr)
        return 1

    # SECURITY: escape the embedded JSON for an HTML <script> context so a malicious skill's
    # finding text (e.g. "</script><img onerror=...>") cannot break out and run JS in the
    # auditor's browser. The </script> breakout happens at HTML-parse time, before the page's
    # esc() ever runs, so escaping here is the real defence.
    data_js = (json.dumps(rows, ensure_ascii=False)
               .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
               .replace(chr(0x2028), chr(92)+chr(92)+chr(48)+chr(48)+chr(50)+chr(56)).replace(chr(0x2029), chr(92)+chr(92)+chr(48)+chr(48)+chr(50)+chr(57)))
    out = (HTML_TMPL
           .replace("__N__", str(len(rows)))
           .replace("__DATA__", data_js))
    Path(args.out).write_text(out, encoding="utf-8")
    print(f"wrote {args.out} ({len(rows)} skills)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
