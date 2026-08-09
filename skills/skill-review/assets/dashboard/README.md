# Portfolio HTML dashboard

`scripts/gen_dashboard.py` renders a **single self-contained HTML file** (inline CSS/JS, no
server, no external assets, no network) summarizing a Mode B portfolio audit. Open it in any
browser.

```
python scripts/gen_dashboard.py <WORKDIR>/run/*.consolidated.json --out <WORKDIR>/reports/portfolio.html
```

It accepts `consolidated.json` or `verdict.json` files. Each row shows a skill's verdict
(🔴 BLOCK / 🟡 WARN / 🟢 PASS) and severity counts; click a row to expand its findings and any
degradation notes. Filter buttons (All/BLOCK/WARN/PASS) and sortable columns help triage a
large portfolio.

The HTML follows skill-creator's static-viewer approach (no long-running process on Windows).
For a single-skill audit the in-chat report (`references/report-template.md`) is enough; the
dashboard is most useful when scanning many installed skills at once. The generator embeds the
data; this directory only documents it (no template file is required).
