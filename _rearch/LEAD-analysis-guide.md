# Lead-Level Deep Dive Analysis Guide

> **Purpose:** Reproducible methodology for deep-diving into a specific CID + Lead from a Vulnhalla orchestrated run. Point Copilot at this doc + a CID/Lead and it will produce a `CID-{id}-L{lead}-analysis.md`.

---

## When To Use

- A lead burned excessive tool calls or cost
- A lead's confidence is `low` or `answered: false`
- You want to evaluate whether the model's investigation strategy was sound
- You want to assess whether the final verdict was correct

---

## Input Required

Tell Copilot:
```
Deep dive CID {cid_number} Lead {lead_id} following _rearch/LEAD-analysis-guide.md
```

---

## Step-by-Step Methodology

### 1. Gather Quantitative Data

**Tool calls CSV** — filter by CID + lead to get the ordered tool sequence:
```powershell
Import-Csv "output\results_orchestrated\c\run_tool_calls_batch_{date}.csv" |
  Where-Object { $_.cid -eq '{CID}' -and $_.lead_id -eq '{LEAD}' } |
  Format-Table call_index, tool, first_arg, phase, cached, found, loc -AutoSize
```

**Lead summary** — get metrics (tokens, cost, rounds, confidence, answered):
```powershell
Import-Csv "output\results_orchestrated\c\run_leads_batch_{date}.csv" |
  Where-Object { $_.cid -eq '{CID}' -and $_.lead_id -eq '{LEAD}' } |
  Format-List *
```

### 2. Identify the Run Folder

```powershell
Get-ChildItem "output\results_orchestrated\c\{CID}" -Directory | Select-Object Name
```

Then list files — the latest `_v{N}` suffix is from the most recent batch replay:
```powershell
Get-ChildItem "output\results_orchestrated\c\{CID}\run_001" -File | Select-Object Name
```

### 3. Read Key Artifacts

Read these files (adjust `_v{N}` suffix for the run you're analyzing):

| File | What it tells you |
|------|-------------------|
| `1_plan_final.json` | All leads, their questions, seed tools |
| `2_initial_code.json` | The flagged source code + Coverity message |
| `2_{LEAD}_final_v{N}.json` | Full investigation transcript (messages array with all tool calls/responses) |
| `2_{LEAD}_summary_v{N}.json` | Compact metrics for this lead |
| `3_synthesize_final.json` | The synthesizer's cross-lead verdict |

**Priority reads:**
1. `2_initial_code.json` — understand the actual vulnerability being investigated
2. `1_plan_final.json` — understand what question this lead was assigned
3. `2_{LEAD}_final_v{N}.json` — the full transcript (this is the main artifact)
4. Other leads' `_final` files — what evidence they found that could complement this lead
5. `3_synthesize_final.json` — the overall verdict

### 4. Analyze the Tool Call Sequence

For each tool call, evaluate:

1. **Was it reasonable?** Given what the model knew at that point, was this the logical next lookup?
2. **Was it productive?** Did it return useful information? Did the model use that information?
3. **Was it redundant?** Was this info already available from a prior call?
4. **Was it a dead end?** Did the model recognize it as such and pivot, or did it keep probing?

Classify each call as one of:
- **Essential** — directly answered the question or provided critical evidence
- **Reasonable** — logical follow-up that happened not to produce results
- **Marginal** — low-probability probe, but not unreasonable given constraints
- **Wasteful** — the model should have known this wouldn't help
- **Duplicate** — same tool+args already called (should have been cached or avoided)

### 5. Identify What It Was Stuck On

Common patterns:
- **Tool gap** — the entity exists but no tool can reach it (enums, typedefs, small structs)
- **Not-found spiral** — initial lookup fails, model probes neighbors hoping for transitive discovery
- **Huge-response distraction** — a large class definition (like hknpShape at 646 LOC) buries the useful info
- **Wrong tool for the job** — e.g., using `get_class` for something that's a function, or vice versa
- **Didn't follow the call chain** — code from a prior tool showed the next function to look up, but model missed it

### 6. Evaluate the Conclusion

Ask these questions:
1. **Given what it found, was the conclusion factually correct?**
2. **Could it have answered with higher confidence from existing evidence?** (e.g., cross-lead evidence it didn't use)
3. **Was the confidence level appropriate?** (low/medium/high)
4. **If answered=false, was that justified?** Or could it have synthesized an answer from partial evidence?
5. **What would a human analyst conclude from the same evidence?**

### 7. Check Cross-Lead Interaction

Read other leads' `_final` files briefly:
- Did another lead find evidence that would have answered this lead's question?
- Did the synthesizer properly combine evidence across leads?
- Were there redundant lookups across leads that could have been shared?

---

## Output Format

Create `_rearch/CID-{id}-L{lead}-analysis.md` with these sections:

```markdown
# CID {id} — Lead {lead} Deep Dive

## {date} — {context description}

### Issue Context
- Coverity message, file, function

### Lead Assignment
- Question, why it matters

### Run Metrics
- Table: tool calls, cached, found rate, rounds, tokens, cost, confidence, answered

### Tool Call Sequence
- Table: #, tool, argument, found, assessment (essential/reasonable/marginal/wasteful/duplicate)

### What It Was Stuck On
- Root cause of failure or high cost

### Was the Conclusion Right?
- Evaluate accuracy, conservatism, missed inferences

### Cross-Lead Summary
- Table of all leads for this CID with outcomes

### Lessons / Improvement Ideas
- Actionable items (tool gaps, prompt changes, budget tuning)
```

---

## Quick Reference: File Naming Convention

- Combined batch CSVs: `run_{tool_calls,leads,cids}_batch_{YYYYMMDD}.csv`
- Per-CID files: `output/results_orchestrated/c/{CID}/run_001/`
- Versioned files: `2_{LEAD}_final_v{N}.json` where v1=original, v2=first replay, v3=second replay, etc.
- Analysis output: `_rearch/CID-{CID}-L{LEAD}-analysis.md`
