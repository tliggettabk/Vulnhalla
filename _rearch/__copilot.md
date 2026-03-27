# _rearch — Copilot Context

> **This file is for system context only** — run commands, file layout, source pointers, and current status. Do NOT put analysis methodology, reporting formats, or checklists here. Those belong in `orchestrated-analysis-guide.md`.

This folder contains the orchestrated analysis engine design, guides, and analysis results. The orchestrated engine uses a Plan → Investigate → Synthesize pipeline instead of the single-conversation approach in the main `_analysis` folder.

## Key Files
- **orchestrated-analysis-plan.md** — Architecture design doc (Plan → Investigate → Synthesize phases)
- **orchestrated-analysis-guide.md** — Post-run analysis methodology, data dictionary, and quick reference

## How to Run Orchestrated Mode

### Run (fresh)
```powershell
python -c "from src.vulnhalla import IssueAnalyzer; analyzer = IssueAnalyzer(lang='c', orchestrated=True, exact_only=True); analyzer.run('C:\\code\\codeQL_CoD\\codeql')"
```
Each run auto-creates `run_NNN` under the CID folder (e.g., `run_001`, `run_002`, …). **Do NOT delete `output\results_orchestrated` before a fresh run** — just run again and it increments automatically.

### Run a batch (uses issues-{batch}.csv instead of issues.csv)
```powershell
python -c "from src.vulnhalla import IssueAnalyzer; analyzer = IssueAnalyzer(lang='c', orchestrated=True, exact_only=True, batch='b3'); analyzer.run('C:\\code\\codeQL_CoD\\codeql')"
```
When `batch` is set (e.g., `'b3'`), the engine reads `issues-b3.csv` from each DB folder instead of `issues.csv`. Omit `batch` or pass `''` for the default file.

### Run last X issues only (error recovery)
```powershell
python -c "from src.vulnhalla import IssueAnalyzer; analyzer = IssueAnalyzer(lang='c', orchestrated=True, exact_only=True, last_n=3); analyzer.run('C:\\code\\codeQL_CoD\\codeql')"
```
Processes only the last 3 issues from the CSV file (sorted by CID). Useful for error recovery when the full run fails partway through.

### Run plan only (skip Phases 2+3)
```powershell
python -c "from src.vulnhalla import IssueAnalyzer; analyzer = IssueAnalyzer(lang='c', orchestrated=True, exact_only=True, plan_only=True); analyzer.run('C:\\code\\codeQL_CoD\\codeql')"
```

### Replay with existing plan (skip Phase 1)
```powershell
python -c "from src.vulnhalla import IssueAnalyzer; analyzer = IssueAnalyzer(lang='c', orchestrated=True, exact_only=True, plan_file=r'output\results_orchestrated\c\15518\run_001\1_plan_final.json'); analyzer.run('C:\\code\\codeQL_CoD\\codeql')"
```

### Replay a single lead
```powershell
python -c "from src.vulnhalla import IssueAnalyzer; analyzer = IssueAnalyzer(lang='c', orchestrated=True, exact_only=True, plan_file=r'output\results_orchestrated\c\15518\run_001\1_plan_final.json', replay_lead='3'); analyzer.run('C:\\code\\codeQL_CoD\\codeql')"
```

### Replay synthesize only (re-run Phase 3 with existing findings)
```powershell
python -c "from src.vulnhalla import IssueAnalyzer; analyzer = IssueAnalyzer(lang='c', orchestrated=True, exact_only=True, plan_file=r'output\results_orchestrated\c\15518\run_001\1_plan_final.json', replay_synthesize=True); analyzer.run('C:\\code\\codeQL_CoD\\codeql')"
```

## Results Layout
```
output/results_orchestrated/c/{CID}/run_NNN/
├── 1_plan_raw.json              ← Raw planner LLM output
├── 1_plan_final.json            ← Parsed leads (reusable for replay)
├── 1_plan_summary.json          ← Planner token/cost stats
├── 2_initial_code.json          ← Flagged code snippet
├── 2_{N}_raw.json               ← Per-lead raw LLM output
├── 2_{N}_final.json             ← Per-lead full conversation + finding
├── 2_{N}_summary.json           ← Per-lead stats, tool list, confidence
├── 2_{N}_v2_final.json          ← Versioned replay outputs (never overwrite)
├── 3_synthesize_raw.json        ← Raw synthesizer LLM output
├── 3_synthesize_final.json      ← Full synthesizer conversation + verdict
├── 3_synthesize_summary.json    ← Synthesizer token/cost stats
├── 3_synthesize_v2_final.json   ← Versioned synthesize replay outputs
└── run_summary.json             ← Aggregate: cost, tokens, all findings, verdict
└── run_report.md                ← Human-readable markdown report (start here)
```

## Source Code
- **`src/llm/orchestrator.py`** — Plan + Investigate + Synthesize engine (native OpenAI function-calling)
- **`data/prompts/orchestrator_plan.yaml`** — Planner prompt
- **`data/prompts/orchestrator_investigate.yaml`** — Investigator prompt
- **`data/prompts/orchestrator_synthesize.yaml`** — Synthesizer prompt
- **`src/vulnhalla.py`** — Entry point; `orchestrated=True` flag selects the orchestrator

## Current Status
- Phase 1 (PLAN) — implemented
- Phase 2 (INVESTIGATE) — implemented with native function calling, reason param, wind-down nudge, cached-round skip
- Phase 3 (SYNTHESIZE) — implemented (single reasoning-only LLM call, produces verdict with status code)
## Guardrails
- **Lead cap**: If the planner produces more than 8 leads, the issue is skipped (returns 7331) and logged. Shows up in the final summary as "More Data" with the reason.

## Analysis Scripts

### Compare engine verdicts vs human ground truth
```powershell
python _analysis\tools\compare_orchestrated_vs_human.py
python _analysis\tools\compare_orchestrated_vs_human.py --run run_001
```
Reads human verdicts from `_analysis\x02-updateLineNums\Findings_WithCodeLine_WithTriageComment_Perfect.xlsx` (CID, Report, Last Triage Comment columns). Outputs agreement table, accuracy %, and per-CID detailed comparison. See `orchestrated-analysis-guide.md` Section 8 for full docs.

### LOC vs cost analysis
```powershell
python _analysis\tools\loc_cost_analysis.py
```
Reads all CID run_summary.json files. Outputs per-lead LOC/cost/tokens/rounds breakdown, cross-CID $/LOC ranking, and Pearson correlations (cost↔tokens r=0.94, cost↔rounds r=0.79, cost↔LOC r=0.45). Key insight: cost is driven by rounds × reasoning token accumulation, not LOC read.

## Known Issues & Analysis Docs
- **CID-19309-run001-lead1-badFP.md** — Engine returned 1007 (FP), human said TP. Root cause: investigator treated `core_assert(borderCount >= 2)` as structural guarantee. The assert is stripped in production and `if (borderCount == 2)` doesn't catch borderCount < 2. Led to adding assert instructions to `orchestrator_investigate.yaml`.

## Analysis
After a run, follow `orchestrated-analysis-guide.md` for methodology and quick-reference commands.
