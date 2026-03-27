# Orchestrated Run Analysis Guide

## Scope
Analyze ONLY the latest orchestrated run for the requested CID. The run data lives under `output\results_orchestrated\c\{CID}\run_NNN\`. Each run is self-contained — never overwritten.

**Start here:** Open `run_report.md` in the run folder. It has the full lead findings and synthesize verdict in one readable file. Use the JSON files below only when you need to dig deeper (tool call sequences, full conversations, etc.).

## Data Sources

### Run-level
- **Run report:** `run_NNN\run_report.md` — human-readable markdown with header stats, per-lead findings, and synthesize verdict (read this first)
- **Run summary:** `run_NNN\run_summary.json` — total cost, tokens, duration, model, leads count, and all findings (without full conversation)
- **Plan (raw):** `run_NNN\1_plan_raw.json` — raw LLM output from the planner
- **Plan (final):** `run_NNN\1_plan_final.json` — parsed leads with questions, why, evaluate, tool seeds
- **Plan (summary):** `run_NNN\1_plan_summary.json` — planner token/cost stats
- **Initial code:** `run_NNN\2_initial_code.json` — the flagged code snippet sent to all investigators

### Per-lead (lead N = 1, 2, 3, …)
- **Summary:** `run_NNN\2_{N}_summary.json` — tokens, cost, duration, tool call list with args/cached status, confidence, answered flag
- **Final:** `run_NNN\2_{N}_final.json` — full conversation (system + user + all tool_calls/tool messages + final answer), plus the finding and confidence
- **Raw:** `run_NNN\2_{N}_raw.json` — raw LLM response text before parsing

### Versioned replays
When a single lead is replayed, output is versioned: `2_{N}_v2_final.json`, `2_{N}_v3_final.json`, etc. Never overwrites the original.

## Per-Run Analysis Checklist

### 1. Plan Quality
- Read `1_plan_final.json` — list the leads with their questions
- Are the leads **non-overlapping**? (Each should be self-contained, answerable with only code lookups)
- Are the leads **sufficient**? Do they cover the key aspects needed to reach a verdict?
- Does any lead embed assumptions from another lead's territory? (This causes investigator drift)
- What seed tool did each lead start with? Was it reasonable?

### 2. Per-Lead Investigation Deep-Dive
For each lead, read `2_{N}_summary.json` and `2_{N}_final.json`:

| Metric | Where to find it |
|--------|-----------------|
| Rounds used / budget (12) | `follow_up_rounds` in summary |
| Tool calls (total / cached) | `tool_calls`, `tool_calls_cached` in summary |
| Answered? | `answered` in summary |
| Confidence | `confidence` in summary |
| Cost | `estimated_cost_usd` in summary |
| Wind-down nudge fired? | Look for `"wind-down nudge"` in console output or round 9+ in final |

**Tool call breakdown table** (from `tools_executed` in summary):

| Round | Tool | Args | Cached? | Phase | Was it needed? |
|-------|------|------|---------|-------|---------------|
| seed  | get_caller_function | {function_name: ...} | no | seed | — |
| 1     | get_class | {object_name: ...} | no | followup | yes/no/why |
| ...   | ... | ... | ... | ... | ... |

Key questions:
- Were any calls **redundant** (same tool+args requested twice despite anti-duplicate prompt)?
- Did the model use the **macro→global_var fallback** when needed?
- Did it **drift** into another lead's territory? (Requesting data about concepts from a different lead's question)
- Did it fill in a meaningful **reason** for each tool call?
- At what round did it have enough info to answer? Did it keep going unnecessarily?

### 3. Finding Quality
For each lead's finding (in `2_{N}_final.json`):
- Quote the exact finding text
- Does it cite specific **line numbers and values** from the tool results?
- Is it **factual** (based on code seen) or does it speculate?
- Does it answer the assigned question, or drift into verdict territory?
- Is the confidence level appropriate given the evidence gathered?

### 4. Synthesis Readiness
Look at all findings together:
- Do the findings **chain together** to support a clear verdict?
- Is there a gap — something none of the leads investigated that's needed for a verdict?
- Would a synthesizer have enough evidence to produce a confident TP/FP/More Data decision?

### 5. LOC Analysis

LOC (Lines of Code) metrics track how much source code the engine actually examined during investigation. These are available in each lead's summary and in the run report header.

**Per-lead LOC table** (from `loc` in `2_{N}_summary.json` or the run report):

| Lead | Initial LOC | Tool LOC | Total LOC | Avg LOC/call | Tool calls |
|------|-------------|----------|-----------|-------------|------------|
| Lead 1 | `loc.initial` | `loc.tool_total` | `loc.total` | `loc.avg_per_tool_call` | from summary |
| Lead 2 | ... | ... | ... | ... | ... |
| Lead 3 | ... | ... | ... | ... | ... |
| **Run total** | — | — | from run report header | — | — |

**What to look for:**

- **Initial LOC**: The flagged code snippet sent to the investigator (same for all leads). This is the starting context.
- **Tool LOC**: Lines retrieved via tool calls (`get_function_code`, `get_class`, `get_caller_function`, etc.). This is the code the model actually read during investigation.
- **Avg LOC/call**: How much code each tool call returned on average. Low values (<10) may indicate small helper functions; high values (>25) indicate large functions or class definitions.
- **Total LOC across run**: The sum of all unique LOC examined. Note cached tool calls return the same code, so total LOC from tool calls may overcount slightly across leads.

**Key questions:**
- Is the total LOC reasonable for the complexity of the issue? Simple issues may need <100 LOC; complex cross-function data flows may need 200-400+.
- Did any lead examine very little code relative to its round count? (High rounds + low LOC = spinning without progress)
- Did any lead pull in huge amounts of code? (May indicate unfocused tool calls or overly broad `get_class` results)
- What's the LOC-to-cost ratio? ($/LOC gives a rough efficiency metric)

### 6. Cost & Efficiency

| Metric | Value |
|--------|-------|
| Plan cost | from `1_plan_summary.json` |
| Lead 1 cost | from `2_1_summary.json` |
| Lead 2 cost | from `2_2_summary.json` |
| Lead 3 cost | from `2_3_summary.json` |
| **Total** | from `run_summary.json` |
| Total tokens | from `run_summary.json` |
| Duration | from `run_summary.json` |

Compare against non-orchestrated runs for the same CID if available (`output\results\c\{CID}\`).

### 7. Lead Breakdown Format (for reporting)
When summarizing a run, use this format for each lead:

**Lead N** (rounds, outcome, confidence, *key question: answer*) — What it was chasing. What it found or why it failed. Whether it got the right answer.

The parenthetical should include: round count, outcome (answered/budget exhausted/unanswered), confidence level, and the lead's essential question distilled to a short `key: value` pair.

Examples:
- **Lead 1** (12 rounds, budget exhausted, low confidence, upper bound on `find_first_bit`: unknown) — Chasing `find_first_bit<true>()` return range guarantees relative to `num_bits`. Spent all 12 rounds trying to resolve the `ntl::bitset` class definition but couldn't find it. Never answered, but the synthesizer correctly treated the missing bound as "unbounded."
- **Lead 2** (8 rounds, answered, high confidence, caller clamps `layerCount`: no) — Chasing who calls `R_ST_IterateLayerMask` and what `layerCount` value they pass. Found the single caller passes `surface.layerCount` (unbounded `uint`) with no clamping. Correct.
- **Lead 3** (9 rounds, answered, high confidence, callback bounds-checks `layerIndex`: no) — Chasing how the callback uses `layerIndex` and whether it has its own bounds checks. Found the lambda directly indexes 256-element arrays with zero checking. Correct.

### 8. Cross-Run Comparison
If multiple runs exist (run_001, run_002, …), build a comparison table:

| Run | Leads | L1 Rounds/Conf | L2 Rounds/Conf | L3 Rounds/Conf | Total LOC | Total Cost | Duration | Verdict |
|-----|-------|---------------|---------------|---------------|----------|-----------|----------|---------|
| run_001 | 3 | 10/med | 4/high | 8/high | 185 | $0.19 | 219s | — |
| run_002 | ... | ... | ... | ... | ... | ... | ... | ... |

## Suggested Improvements
After analysis, list:
- Prompt changes that would help (planner, investigator, or future synthesizer)
- Budget or mechanism changes (wind-down threshold, max rounds, etc.)
- Leads that should have been planned differently
- Tool calls that were wasted and how to prevent them

## Output
- Save analysis in `_rearch\CID-{cid}-orchestrated-analysis.md`
- Add a new section for each run analyzed
- **Share the full analysis in chat** — the user should not have to open the document to see results

---

## Quick Reference

### Status Codes (same as non-orchestrated)

| Code | Meaning | Classification |
|------|---------|----------------|
| `1337` | True Positive — real vulnerability | Exploitable security issue |
| `1007` | False Positive — not a real issue | Safe, no action needed |
| `7331` | Need More Data | Insufficient info |
| `7337` | Conflicting evidence | Re-analysis recommended |

### Diagnosing "Need More Data" (7331) Cases

When analyzing inconclusive results:

```powershell
# Check budget exhaustion patterns
(Get-Content "output\results_orchestrated\c\{CID}\run_NNN\run_summary.json" | ConvertFrom-Json).findings | Where-Object { $_.answered -eq $false }

# Review tool call patterns
(Get-Content "output\results_orchestrated\c\{CID}\run_NNN\2_1_summary.json" | ConvertFrom-Json).tools_executed | Format-Table tool, args, cached
```

**Common patterns:**
- **High tool usage (10+ rounds)**: Often external API/system type lookups
- **Medium usage (4-8 rounds)**: Usually missing constant relationships
- **Low usage (1-3 rounds)**: Unfocused questions or tool failures

**Common patterns:**
- **High tool usage (10+ rounds)**: Often external API/system type lookups
- **Medium usage (4-8 rounds)**: Usually missing constant relationships
- **Low usage (1-3 rounds)**: Unfocused questions or tool failures

**Analyzing consecutive failure patterns:**

To identify potential early termination opportunities, analyze tool call conversation logs:

```powershell
# Extract consecutive failure patterns from actual conversations
python -c "
import json
messages = json.load(open('output/results_orchestrated/c/{CID}/run_{N}/2_1_final.json'))['messages']
consecutive = 0
max_consecutive = 0
for msg in messages:
    if msg.get('role') == 'tool':
        is_failure = 'not found' in msg.get('content', '').lower()
        if is_failure:
            consecutive += 1
            max_consecutive = max(max_consecutive, consecutive)
        else:
            consecutive = 0
print(f'Max consecutive failures: {max_consecutive}')
"
```

**Key questions for efficiency analysis:**
- How many consecutive `NOT FOUND` results before any success?
- Do successful high-tool investigations have different failure patterns?
- Are repeated failures on related entities providing new information?

Compare against human expert reasoning to identify knowledge gaps vs genuine uncertainty.

### PowerShell Quick-Access Commands

```powershell
# List all runs for a CID
Get-ChildItem "output\results_orchestrated\c\{CID}" -Directory | Sort-Object Name

# Read run summary
Get-Content "output\results_orchestrated\c\{CID}\run_NNN\run_summary.json" | ConvertFrom-Json | Format-List

# All lead decisions at a glance
(Get-Content "output\results_orchestrated\c\{CID}\run_NNN\run_summary.json" | ConvertFrom-Json).findings | Select-Object id, answered, confidence, tool_calls, estimated_cost_usd

# Plan leads overview
(Get-Content "output\results_orchestrated\c\{CID}\run_NNN\1_plan_final.json" | ConvertFrom-Json) | Select-Object id, question

# Per-lead tool call list
(Get-Content "output\results_orchestrated\c\{CID}\run_NNN\2_1_summary.json" | ConvertFrom-Json).tools_executed | Format-Table tool, args, cached, phase

# Read a lead's final finding
(Get-Content "output\results_orchestrated\c\{CID}\run_NNN\2_1_final.json" | ConvertFrom-Json) | Select-Object finding, confidence
```

### Key Fields in `run_summary.json`

| Field | Description |
|-------|-------------|
| `model` | LLM model used (e.g., `azure/gpt-5.1-codex`) |
| `leads_count` | Number of investigation leads generated by planner |
| `tool_calls` | Total tool calls across all leads |
| `total_tokens` | Combined prompt + completion tokens |
| `estimated_cost_usd` | Total run cost from `litellm.completion_cost()` |
| `duration_seconds` | Wall-clock time for full run |
| `findings[]` | Array of per-lead results (without conversation messages) |

### Key Fields in `2_{N}_summary.json`

| Field | Description |
|-------|-------------|
| `lead_id` | Which lead (1, 2, 3, …) |
| `question` | The investigation question assigned |
| `answered` | `true` if the investigator produced a finding |
| `confidence` | `high`, `medium`, or `low` |
| `follow_up_rounds` | Rounds used out of budget (12 max) |
| `tool_calls` / `tool_calls_cached` | Total and cache-hit tool calls |
| `tools_executed[]` | Ordered list: tool name, args, cached flag, phase (seed/followup) |
| `estimated_cost_usd` | Cost for this lead only |

### Cost Estimation

When `estimated_cost_usd` is available, use it directly. When it's 0 (model not in litellm pricing DB):

| Model | Input $/1K tokens | Output $/1K tokens |
|-------|-------------------|-------------------|
| gpt-4o | $0.0025 | $0.010 |
| gpt-4.1-mini | $0.0004 | $0.0016 |
| gpt-5.1-codex | ~$0.015 (est.) | ~$0.030 (est.) |

```
cost = (prompt_tokens * input_rate + completion_tokens * output_rate)
```

---

## 9. Comparing Against Human Ground Truth

The Excel file at `_analysis\x02-updateLineNums\Findings_WithCodeLine_WithTriageComment_Perfect.xlsx` contains human researcher conclusions for each CID. Key columns:

| Column | Meaning |
|--------|---------|
| `CID` | Coverity Issue ID |
| `Report` | `"Yes"` = human says reportable (TP), `"No"` = not reportable (FP) |
| `Last Triage Comment` | Human's rationale / notes |

### Running the Comparison Script

```powershell
# Compare latest run per CID against human verdicts
python _analysis\tools\compare_orchestrated_vs_human.py

# Compare a specific run
python _analysis\tools\compare_orchestrated_vs_human.py --run run_001

# Custom paths
python _analysis\tools\compare_orchestrated_vs_human.py --excel PATH --results DIR
```

The script outputs:
1. **Summary table** — CID, human verdict, engine verdict, agreement, cost, tokens, leads
2. **Accuracy** — % agreement excluding inconclusive (7331/7337) verdicts
3. **Detailed comparison** — per-CID breakdown with human rationale

### Agreement Logic

| Human | Engine | Agreement |
|-------|--------|-----------|
| Yes (TP) | 1337 (TP) | **AGREE** |
| Yes (TP) | 1007 (FP) | **DISAGREE** |
| No (FP) | 1007 (FP) | **AGREE** |
| No (FP) | 1337 (TP) | **DISAGREE** |
| Any | 7331 / 7337 | **INCONCLUSIVE** (excluded from accuracy) |

### Interpreting Disagreements

When the engine disagrees with the human:
- **Engine says FP, human says TP**: Read the engine's synthesize verdict — did it find a real guard the human missed, or did it over-trust an assert? Check the human's triage comment for their reasoning.
- **Engine says TP, human says FP**: Read the engine's synthesis — is the exploit path realistic, or is it a theoretical path blocked by caller conventions?

### Script Location

`_analysis\tools\compare_orchestrated_vs_human.py`
