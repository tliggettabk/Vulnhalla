# CID 27724 Deep Dive: run_004 Regression (FP→TP)

**Human verdict:** FP (1007) | **run_002:** 1007 ✅ | **run_003:** 1007 ✅ | **run_004 (b12):** 1337 ❌

## Root Cause: Two compounding failures

### 1. Planner wasted Lead 3 on the wrong function

| Run | Lead 1 | Lead 2 | Lead 3 |
|-----|--------|--------|--------|
| run_002 | GetSize() return values | Read() parameter behavior | **Allocate() size validation** |
| run_003 | GetSize() return values | Read() parameter behavior | **Allocate() size validation** |
| run_004 | GetSize() return values | Read() parameter behavior | **ParseCacheIndexLine()** ← wrong |

run_004's planner asked about `ParseCacheIndexLine` (a downstream consumer at line 627) instead of the allocator at line 588. The Lead 3 answer explicitly concluded _"it doesn't constrain fileSz or protect the read call relevant to this alert"_ — a dead-end that consumed the investigative budget with zero value.

In contrast, run_002/003 both investigated the allocator, learning that it takes `size_t` with no validation — context that, while not directly exonerating, helped frame the guard analysis correctly.

### 2. Synthesizer missed the critical `!pFile.IsValid()` guard

The run_004 synthesizer's Guard Assessment listed only two guards:
- `if (fileSz == 0) break;` — marked **Ineffective**
- `if (!buf) { … break; }` — marked **Ineffective**
- _"No other guard constrains fileSz before it is cast to size_t."_

**It completely omitted** `if (!pFile.IsValid()) break;` at lines 575–579, which is the exact guard that prevents `GetSize()` from returning −1. Both run_002 and run_003 correctly identified this guard as **Effective** and pivotal to the FP verdict.

### 3. Lead 1 interpretation was overly pessimistic

| Run | Lead 1 conclusion |
|-----|-------------------|
| run_003 | "For valid files it recomputes the size via platform OS calls and stores the **non‑negative byte count**" |
| run_004 | "any **error codes those APIs emit propagate unchanged**… so any error codes those APIs emit propagate unchanged" |

run_004's Lead 1 speculated that platform APIs (`sceKernelLseek`, `GetFileSize`) might themselves return negative error codes even for valid file handles. run_003's Lead 1 correctly characterized these as returning "the real non-negative size of the file" for valid handles. This pessimistic framing cascaded into the synthesizer assuming `GetSize()` could be negative even after the IsValid guard.

## Cascade Summary

```
Planner diverges on Lead 3 question
    → ParseCacheIndexLine instead of Allocate
        → Wasted lead provides no guard-relevant info
Lead 1 over-interprets OS API error potential  
    → Synthesizer believes negative fileSz is possible even for valid handles
        → Misses that !pFile.IsValid() eliminates the only negative path
            → Wrong verdict: TP (1337) instead of FP (1007)
```

## Efficiency Comparison

| Metric | run_002 | run_003 | run_004 |
|--------|---------|---------|---------|
| Tool calls | 11 | 3 | 3 |
| Tokens | 82,752 | 89,644 | 34,634 |
| Cost | $0.35 | $0.29 | $0.18 |
| Duration | 535s | 907s | 171s |
| Verdict | 1007 ✅ | 1007 ✅ | 1337 ❌ |

run_004 was the fastest and cheapest — but wrong. run_003 got the right answer despite Lead 3 failing to an API timeout. run_002 was the most thorough (11 tool calls, 8 rounds on Lead 3 to trace the allocator).

## Actionable Insights

1. **Guard-tracing lead is critical**: The planner should always generate a lead specifically asking "what guards exist between the source and sink?" when the alert involves data-flow from a potentially-negative source to an unsigned sink. run_004's planner didn't ask this.

2. **Lead 3 question selection matters**: Asking about `ParseCacheIndexLine` (a downstream consumer) instead of `Allocate` (the direct recipient of fileSz) was a strategic error. The planner should prioritize functions on the *direct* data-flow path between source and sink.

3. **Pessimistic OS API interpretation**: Lead 1's claim that OS APIs "propagate error codes unchanged" for valid handles was unsupported speculation. The investigation found `GetFileSize` / `sceKernelLseek` but didn't provide evidence these return negative values for valid file descriptors — yet the conclusion assumed they could.

---

## Fix: Planner Prompt Update

Two bullets added to `data/prompts/orchestrator_plan.yaml` IMPORTANT CONSTRAINTS:

1. **Data-flow prioritization** — _"Prioritize leads that investigate functions on the direct data-flow path between the alert's source and sink. Downstream consumers that operate on derived data AFTER the sink are lower priority."_
2. **Guard-investigation mandate** — _"When the flagged code contains guards or validity checks between the source and the sink, include a SEPARATE lead that asks whether those specific caller-side guards prevent the dangerous value from reaching the sink. Cite the guard's line numbers. Do NOT fold this into a lead about the callee's return values."_

Additionally, `src/llm/orchestrator.py` was fixed so `plan_only=True` now writes `2_initial_code.json`, enabling subsequent `replay_lead` without re-scanning the DB.

## Verification: run_007 → run_008

**Plan (run_007)** — planner now generates a guard-specific lead:

| Lead | run_004 (old prompt) | run_007 (new prompt) |
|------|---------------------|---------------------|
| 1 | GetSize() return values | GetSize() return values |
| 2 | Read() parameter behavior | Read() parameter behavior |
| 3 | **ParseCacheIndexLine()** ← wrong | **Guards at lines 575-585 (IsValid + fileSz==0)** ✅ |

Lead 3 question: _"Do the guards at lines 575-585 (checking pFile.IsValid() and fileSz == 0) ensure that fileSz is strictly positive before the allocation at line 588 and the Read call at lines 597-599?"_

**Full run (run_008)** — correct verdict restored:

| Metric | run_004 (old, wrong) | run_008 (new, correct) |
|--------|---------------------|----------------------|
| Verdict | 1337 (TP) ❌ | **1007 (FP) ✅** |
| Tool calls | 3 | 3 |
| Cost | $0.18 | $0.06 |
| Duration | 171s | 55s |

Synthesize replay with old leads (v2) confirmed the regression was deterministic — same bad leads always produce the wrong verdict. The fix had to be in the planner, not the synthesizer.
