# CID 15518 — Orchestrated Analysis

## Run 008 Analysis

**Run folder**: `output\results_orchestrated\c\15518\run_008`
**Model**: azure/gpt-5.1-codex | **Engine**: orchestrator
**Verdict**: **1337 (True Positive)** | **Human**: Yes (TP) — **AGREE**
**Tokens**: 49,386 | **Cost**: $0.25 | **Duration**: 216s | **Tool calls**: 10

**Issue**: Overrunning callee's array of size 256 by passing argument `layerIndex` (which evaluates to 256) in call to `operator()`.
**File**: SuperTerrainDefines.h, line 220

---

### 1. Plan Quality

3 leads planned:

| Lead | Question | Seed Tool | Reasonable? |
|------|----------|-----------|-------------|
| 1 | Return range of `find_first_bit<true>()` at line 217 relative to `layerCount`/`num_bits` | `get_class(StLayerMaskOMPV)` | Yes — need to understand the value that initializes the loop |
| 2 | Return value of `find_first_bit_from<true>(layerIndex + 1)` at line 227 when `layerIndex == layerCount - 1` | `get_class(StLayerMaskOMPV)` | Yes — need to understand the loop-continuation value |
| 3 | Which functions call `R_ST_IterateLayerMask` and what callbacks do they pass? | `get_caller_function(R_ST_IterateLayerMask)` | Yes — need to see if callbacks bounds-check `layerIndex` |

**Non-overlapping?** Yes. Lead 1 focuses on the initial `find_first_bit` range. Lead 2 focuses on the `find_first_bit_from` continuation behavior and the break condition. Lead 3 focuses on callers and callback internals. Clean separation.

**Sufficient?** Yes. Together they cover: (1) can `layerIndex` reach ≥256?, (2) does the loop prevent it?, (3) does the callback protect against it? That's exactly what you need for this overrun.

**Cross-lead assumptions?** None detected. Each lead is self-contained.

**Seed tools reasonable?** Lead 1 & 2 both seed with `get_class(StLayerMaskOMPV)` — makes sense since they need to trace into the bitset methods. Lead 3 seeds with `get_caller_function` — directly targets the call graph. All appropriate.

---

### 2. Per-Lead Investigation Deep-Dive

#### Lead 1 — `find_first_bit` return range (4 rounds, answered, high confidence)

| Round | Tool | Args | Cached? | Phase | Needed? |
|-------|------|------|---------|-------|---------|
| seed | get_class | `{StLayerMaskOMPV}` | no | seed | yes — gets the class to find method definitions |
| 1 | get_function_code | `{StLayerMaskOMPV::find_first_bit}` | no | followup | yes — traces the delegation chain |
| 2 | get_function_code | `{ntl::bitset::find_first_bit_from_block}` | no | followup | yes — core implementation with return values |
| 3 | get_function_code | `{R_ST_IterateLayerMask}` | no | followup | yes — needed exact source lines for evidence citations |

**Redundant calls?** None. Each call retrieved a different function.
**Drift?** The `R_ST_IterateLayerMask` fetch in round 3 could be seen as touching Lead 3's territory, but it was used for loop-guard context (line 218), not caller analysis. Acceptable.
**Efficiency?** Excellent. 4 rounds, 4 tools, answered with high confidence. No wasted calls.

#### Lead 2 — `find_first_bit_from` continuation semantics (5 rounds, answered, high confidence)

| Round | Tool | Args | Cached? | Phase | Needed? |
|-------|------|------|---------|-------|---------|
| seed | get_class | `{StLayerMaskOMPV}` | **yes** | seed | — (cache hit from Lead 1) |
| 1 | get_function_code | `{StLayerMaskOMPV::find_first_bit_from}` | no | followup | yes — the target function |
| 2 | get_function_code | `{StLayerMaskOMPV::find_first_bit}` | **yes** | followup | marginal — already covered by Lead 1, but model may not see Lead 1's data |
| 3 | get_function_code | `{find_first_bit_from_block}` | no | followup | yes — implementation details |
| 4 | get_function_code | `{R_ST_IterateLayerMask}` | **yes** | followup | yes — needed for break condition citation |

**Redundant calls?** The round 2 `find_first_bit` fetch was already done by Lead 1, but Lead 2 runs independently and doesn't see Lead 1's results, so it's a legitimate re-fetch (served from cache). Not a prompt issue.
**Drift?** No. Focused on `find_first_bit_from` and the break path.
**Efficiency?** Good. 5 rounds but 2 were cache hits. The model correctly identified that the break at lines 222-224 prevents the function from being called when `layerIndex == layerCount - 1`.

#### Lead 3 — Caller analysis (1 round, answered, high confidence)

| Round | Tool | Args | Cached? | Phase | Needed? |
|-------|------|------|---------|-------|---------|
| seed | get_caller_function | `{R_ST_IterateLayerMask}` | no | seed | yes — directly answers the question |

**Efficiency?** Perfect. Single tool call, answered immediately. The `get_caller_function` returned the caller with the full lambda body, giving the model everything it needed in one shot. Best-case scenario.

---

### 3. Finding Quality

**Lead 1 finding**: Correctly identifies that `find_first_bit` returns values in `[0, num_bits)` for real results and `num_bits` as sentinel. Cites specific lines (424, 592, 597, 607, 611) with exact code. Notes that the `while (layerIndex < layerCount)` guard prevents sentinel values from triggering the callback. **Factual, well-cited, directly answers the question.**

**Lead 2 finding**: Key insight — correctly identifies that the break at lines 222-224 prevents `find_first_bit_from` from being called when `layerIndex == layerCount - 1`. This means the *question as asked* ("when prior layerIndex equals layerCount - 1") is partially moot, but the model still fully characterizes the return range for when it *is* called. Cites lines 222, 224, 227, 444, 448, 597, 607, 611. **Factual, well-cited, demonstrates genuine code comprehension.**

**Lead 3 finding**: Identifies `R_Stream_UpdateMaterialDistancesForTerrainNode` as the sole caller, with `surface.layerCount` passed as `layerCount`. Notes the lambda uses `layerIndex` to directly index `surface.layerMaterials[]` and `materialDistancesSq[]` with no bounds checking. Cites lines 5008-5028 with exact code. **Factual, well-cited, directly answers the question.**

**Did any lead drift into verdict territory?** No. All three stayed in their lane — reporting evidence without declaring TP/FP.

---

### 4. Synthesis Readiness

**Do the findings chain together?** Yes, cleanly:
- Lead 1: `layerIndex` can be any set-bit position in `[0, num_bits)`, bounded only by `< layerCount`
- Lead 2: The loop continuation doesn't add any tighter bound (break only prevents the last iteration from re-searching)
- Lead 3: The callback directly indexes 256-element arrays with `layerIndex` — no bounds check

**Gap?** Minor: None of the leads explicitly established what `num_bits` is for `StLayerMaskOMPV` (whether it can exceed 256). The synthesizer inferred this from the fact that neither `layerCount` nor `num_bits` is tied to 256. This is a reasonable inference but could be made stronger if a lead had confirmed the actual bitset size.

**Sufficient for verdict?** Yes. The evidence clearly shows: unbounded `layerCount` → `layerIndex` up to `layerCount - 1` → callback indexes 256-element array → overrun when `layerIndex ≥ 256`.

---

### 5. LOC Analysis

| Lead | Initial LOC | Tool LOC | Total LOC | Avg LOC/call | Tool calls |
|------|-------------|----------|-----------|-------------|------------|
| Lead 1 | 17 | 49 | 66 | 12.2 | 4 |
| Lead 2 | 17 | 78 | 95 | 15.6 | 5 |
| Lead 3 | 17 | 27 | 44 | 27.0 | 1 |
| **Run total** | **17** | **154** | **205** | **15.4** | **10** |

**Observations:**

- **Lead 3 had the highest avg LOC/call (27.0)** — the single `get_caller_function` returned 27 lines including the full caller function with lambda body. This is why it answered in 1 round: one rich tool call gave everything needed.
- **Lead 1 had the lowest avg LOC/call (12.2)** — it retrieved 4 individual functions averaging 12 lines each (small helper methods in the bitset class). Despite small returns, each was highly targeted and sufficient.
- **Lead 2 fetched the most total LOC (95)** — 5 tool calls at 15.6 avg, but 2 were cache hits (re-retrieving `find_first_bit` and `R_ST_IterateLayerMask` from Lead 1). The unique new code was `find_first_bit_from` and `find_first_bit_from_block`.
- **205 total LOC is efficient** for this issue. The engine examined ~200 lines of source to reach a high-confidence TP verdict on a cross-function array overrun. Comparable to what a human reviewer would need to read.
- **Cost efficiency**: $0.25 / 205 LOC = **$0.0012/LOC analyzed**. At 154 LOC from tools, that's **$0.0016/LOC from tool returns**.

---

### 6. Cost & Efficiency

| Phase | Tokens | Cost | Duration |
|-------|--------|------|----------|
| Plan | 3,994 | $0.029 | 24s |
| Lead 1 | 16,997 | $0.090 | 82s |
| Lead 2 | 16,927 | $0.057 | 50s |
| Lead 3 | 4,110 | $0.021 | 17s |
| Synthesize | 5,020* | $0.053 | 43s |
| **Total** | **49,386** | **$0.249** | **216s** |

*Synthesize tokens estimated from total minus leads/plan.

**Compared to prior runs** (see Section 8), run_008 is the most efficient completed run — fewest tool calls (10), lowest token count (49K), and second-lowest cost ($0.25) while producing the same correct TP verdict.

---

### 7. Lead Breakdown Summary

**Lead 1** (4 rounds, answered, high confidence, *`find_first_bit` range*: `[0, num_bits)` or sentinel `num_bits`) — Traced `find_first_bit<true>()` through `find_first_bit_from_block`. Established return range and sentinel behavior. Correctly noted `while (layerIndex < layerCount)` bounds the loop but not the array access. 4 clean tool calls, no waste.

**Lead 2** (5 rounds, answered, high confidence, *`find_first_bit_from` at last index*: never called due to break) — Found that lines 222-224 break before `find_first_bit_from` executes when `layerIndex == layerCount - 1`, making the question's scenario impossible. Still fully characterized the function's return range. 5 tools (2 cache hits).

**Lead 3** (1 round, answered, high confidence, *callback bounds-checks `layerIndex`*: no) — Single `get_caller_function` call revealed the sole caller passes `surface.layerCount` (unbounded) and a lambda that directly indexes 256-element arrays with zero checking. Perfect efficiency.

---

### 8. Cross-Run Comparison

| Run | Leads | Tools | Tokens | LOC | Cost | Duration | Verdict | Notes |
|-----|-------|-------|--------|-----|------|----------|---------|-------|
| run_001 | 3 | 22 | 79,791 | — | $0.19 | 219s | — | Missing synthesize phase (incomplete) |
| run_002 | 3 | 30 | 122,750 | — | $0.37 | 435s | TP | Early run, high token/tool usage |
| run_003 | — | — | — | — | — | — | — | No summary (failed/incomplete) |
| run_004 | 4 | 18 | 50,522 | — | $0.16 | 200s | TP | 4-lead plan, cheapest complete run |
| run_005 | 4 | 18 | 55,819 | — | $0.21 | 214s | TP | Similar to run_004 |
| run_006 | 4 | 21 | 91,028 | — | $0.37 | 349s | TP | Higher cost, more tokens |
| run_007 | 4 | 0 | 4,955 | — | $0.01 | 10s | More Data | Plan-file replay test (no DB access) |
| **run_008** | **3** | **10** | **49,386** | **205** | **$0.25** | **216s** | **TP** | **Best efficiency among 3-lead runs** |

*LOC tracking was added in run_008; prior runs don't have this data.*

**Trends**: The 4-lead runs (004-006) come from a different plan structure. The 3-lead plans (001, 002, 008) are more focused. Run_008 is dramatically more efficient than run_002 (3 leads each): 60% fewer tokens, 33% less cost, 50% fewer tool calls.

---

### 9. Human Ground Truth Comparison

| | Human | Engine (run_008) |
|---|-------|-----------------|
| Verdict | **Yes (TP)** | **1337 (TP)** |
| Rationale | "No bounds checking on index, may return 256 if no free bits" | Unbounded `layerCount`/`layerMask` → `layerIndex` ≥ 256 → overrun of 256-element arrays |
| Agreement | **AGREE** |

The engine's analysis is more detailed than the human's triage comment but reaches the same conclusion through the same core reasoning: `find_first_bit` can return 256 (the sentinel/no-free-bits case), and the callback doesn't bounds-check.

---

### 10. Suggested Improvements

1. **Lead 2 was partially redundant with Lead 1.** Both investigate the same bitset method family (`find_first_bit` vs `find_first_bit_from`). The planner could combine these into a single lead: "What range of values do the bitset search functions return, and can `layerIndex` ever reach ≥256?" This would save 5 tool calls and ~17K tokens.

2. **No lead explicitly confirmed `StLayerMaskOMPV`'s `num_bits` capacity.** The synthesizer inferred it's ≥256 from context, but a direct confirmation (e.g., checking the typedef or template parameter) would strengthen the evidence chain.

3. **Lead 3 was perfectly efficient.** The `get_caller_function` seed gave everything needed in one call. Consider whether this pattern (single-tool leads for call graph questions) could be generalized.

4. **Cache utilization was good.** 3 of 10 tool calls were cache hits (30%), showing effective cross-lead data reuse.

5. **The assert-as-no-op handling worked correctly.** The synthesizer identified `core_assert(layerCount <= layerMask.num_bits)` as stripped in production — consistent with the prompt engineering from the CID 19309 work.

---

## Run 011 Lead 1 — TypeAliasLookup Fix Validation

### Background

Run 011 (the most recent full batch) exposed a critical gap: Lead 1's seed tool `get_class("StLayerMaskOMPV")` returned **"not found"** because `StLayerMaskOMPV` is a C++11 `using` alias (`using StLayerMaskOMPV = ntl::bitset<ST_MAX_LAYERS_PER_SURFACE_OMPV>;`), and `Classes.ql` only queries `NameQualifyingElement` — which excludes `TypedefType` subtypes.

The LLM then spent 15 tool calls across 12 rounds trying every conceivable alternative (`get_function_code`, `get_macro_or_global`, `get_global_var`, etc.), exhausted the tool budget, and answered with `"answered": false, "confidence": "low"`.

This motivated the `TypeAliasLookup.csv` feature — a new CodeQL query + CSV + `get_class()` fallback that covers `typedef` and `using` type aliases. See `_rearch/__CSV-maintenance.md` for full implementation details.

### Re-run: Lead 1 v2 (with TypeAliasLookup.csv)

**Date**: 2026-03-26 | **Plan**: run_011 `1_plan_final.json`, Lead 1 only

| Metric | v1 (original) | v2 (with TypeAliasLookup) | Change |
|--------|---------------|---------------------------|--------|
| Tool calls | 15 | **3** | -80% |
| Rounds | 12 (budget exhausted) | **3** | -75% |
| Answered | false | **true** | fixed |
| Confidence | low | **high** | fixed |
| Tokens | 78,029 | **7,873** | -90% |
| Cost | $0.294 | **$0.012** | -96% |
| Duration | 674s | **10.8s** | -98% |
| LOC from tools | 0 (all failures) | 7 | — |

#### Tool trace

| Round | Tool | Args | Found? | LOC | Purpose |
|-------|------|------|--------|-----|---------|
| seed | get_class | `StLayerMaskOMPV` | **yes** | 3 | Gets the `using` alias definition — now resolved via TypeAliasLookup.csv |
| 1 | get_macro_or_global | `ST_MAX_LAYERS_PER_SURFACE_OMPV` | yes | 2 | Follows the template parameter to find the bitset size |
| 2 | get_macro_or_global | `ST_MAX_LAYERS_PER_SURFACE_OMPV_NON_UTS` | yes | 2 | Resolves the constexpr alias to the literal value (256) |

**Zero wasted calls.** Each tool returned useful data, and the LLM chained them logically: alias → template param → actual constant.

#### Finding (v2)

> StLayerMaskOMPV is defined as `ntl::bitset<ST_MAX_LAYERS_PER_SURFACE_OMPV>`, so its `num_bits` equals ST_MAX_LAYERS_PER_SURFACE_OMPV, which is set to ST_MAX_LAYERS_PER_SURFACE_OMPV_NON_UTS = 256. Therefore `layerIndex` values are valid only in [0, 255], enforcing a hard 256-bit capacity.

Evidence cited:
- Line 147: `using StLayerMaskOMPV = ntl::bitset<ST_MAX_LAYERS_PER_SURFACE_OMPV>;`
- Line 56: `inline constexpr uint ST_MAX_LAYERS_PER_SURFACE_OMPV = ST_MAX_LAYERS_PER_SURFACE_OMPV_NON_UTS;`
- Line 51: `inline constexpr uint ST_MAX_LAYERS_PER_SURFACE_OMPV_NON_UTS = 256;`

**This directly answers the gap identified in run_008 Section 10 item 2**: "No lead explicitly confirmed `StLayerMaskOMPV`'s `num_bits` capacity." The v2 finding confirms `num_bits == 256` with a full evidence chain from the `using` alias through two constexpr indirections to the literal value.

### What changed in the codebase

| File | Change |
|------|--------|
| `data/queries/cpp/tools/TypeAliasLookup.ql` | New CodeQL query selecting `TypedefType` entries (both C `typedef` and C++11 `using`) |
| `src/codeql/db_lookup.py` | `get_class()` restructured: searches Classes.csv → EnumLookup.csv → TypeAliasLookup.csv with exact-match-first across all three before escalating to substring matching |
| `src/utils/prompt_loader.py` | Removed misleading "try get_global_var for typedef" guidance |
| `src/llm/llm_analyzer.py` | Removed misleading "try get_global_var for typedef" guidance |

---

## Run 012 — Parallel Leads + TypeAliasLookup

### Background

Run 012 is the first run combining both the **TypeAliasLookup.csv** fix (from run 011 validation) and the new **parallel lead investigation** feature. Leads are dispatched to a `ThreadPoolExecutor` (up to 4 workers), share a thread-safe tool cache, and accumulate tokens under a lock. This tests whether parallelism preserves correctness while reducing wall-clock time.

**Date**: 2026-03-26 | **Model**: azure/gpt-5.1-codex | **Engine**: orchestrator (parallel_leads=True)

### Summary

| Metric | run_008 (baseline) | run_012 (parallel + TypeAlias) | Change |
|--------|-------------------|-------------------------------|--------|
| Leads | 3 | 3 | — |
| Tool calls | 10 | **16** | +60% |
| Tool calls (cached) | 3 | **3** | — |
| Tokens | 49,386 | **83,600** | +69% |
| Cost | $0.25 | **$0.32** | +28% |
| Wall-clock duration | 216s | **191s** | **-12%** |
| Investigate wall time | — | **126s** | — |
| Investigate LLM time | — | **294s** (2.3× parallelism) | — |
| LLM seconds (total) | — | **359s** | — |
| Verdict | TP | **TP** | same |

### Plan

3 leads (similar structure to run_008):

| Lead | Question | Seed Tool |
|------|----------|-----------|
| 1 | How do `find_first_bit<true>()` and `find_first_bit_from<true>()` constrain `layerIndex` relative to `num_bits`? | `get_class(StLayerMaskOMPV)` |
| 2 | What bounds do callers place on `layerCount` passed into `R_ST_IterateLayerMask`? | `get_caller_function()` |
| 3 | Which concrete CB implementations are invoked at line 220, and what bounds do they enforce? | `get_caller_function()` |

### Parallel Execution

All 3 leads started simultaneously. The interleaved log shows genuine concurrency:
- Lead 1 ran 8 rounds (deepest investigation — traced bitset internals)
- Lead 3 finished first (3 rounds, 70s)
- Lead 2 finished second (2 counting rounds, 126s — waited on LLM)
- Lead 1 finished last (8 rounds, 102s LLM time but overlapped)

**Investigate wall time was 126s** with **294s of LLM time** — a **2.3× parallelism factor** proving leads ran concurrently.

### Per-Lead Tool Traces

#### Lead 1 — `find_first_bit` return range (8 rounds, answered, high confidence)

| Round | Tool | Args | Found? | Cached? | LOC |
|-------|------|------|--------|---------|-----|
| seed | get_class | `StLayerMaskOMPV` | **yes** | no | 3 |
| 1 | get_class | `ntl::bitset` | no | no | 0 |
| 2 | get_function_code | `ntl::bitset::find_first_bit` | no | no | 0 |
| 3 | get_macro_or_global | `ST_MAX_LAYERS_PER_SURFACE_OMPV` | yes | no | 2 |
| 4 | get_macro_or_global | `ST_MAX_LAYERS_PER_SURFACE_OMPV_NON_UTS` | yes | no | 2 |
| 5 | get_function_code | `ntl::bitset<256…>::find_first_bit` | yes | no | 5 |
| 6 | get_function_code | `ntl::bitset<256…>::find_first_bit_from_block` | yes | no | 26 |
| 7 | get_function_code | `ntl::bitset<256…>::find_first_bit_from` | yes | no | 29 |

8 tool calls, 0 cached (Lead 1 ran first, populated the cache for others). **Two failures** (rounds 1-2): tried the generic `ntl::bitset` class/method before discovering the template-specialized names. After determining `num_bits=256` in rounds 3-4, it correctly used the instantiated names. **Cost**: $0.095, 31,764 tokens, 102s.

**Finding**: Comprehensively traces both `find_first_bit` and `find_first_bit_from` through `find_first_bit_from_block`. Cites lines 424, 434, 437-444, 448, 454, 592-597, 603-611 with exact code. Concludes both functions return values in `[0, num_bits)` or the sentinel `num_bits`. Confidence: **high**.

#### Lead 2 — Caller bounds on `layerCount` (2 counting rounds, answered, medium confidence)

| Round | Tool | Args | Found? | Cached? | LOC |
|-------|------|------|--------|---------|-----|
| seed | get_caller_function | *(flagged function)* | yes | no | 27 |
| 1 | get_caller_function | `R_ST_IterateLayerMask` | yes | **yes** | 27 |
| 1 | get_class | `StDiskTerrainSurface` | yes | no | 100 |
| 2 | get_macro_or_global | `ST_MAX_LAYERS_PER_SURFACE_OMPV` | yes | **yes** | 2 |
| 2 | get_function_code | `R_Stream_UpdateMaterialDistancesForTerrainNode` | yes | **yes** | 27 |

5 tool calls, 3 cached (populated by Lead 1 and Lead 3 running in parallel). **Cost**: $0.104, 28,285 tokens, 126s.

**Finding**: Identifies `R_Stream_UpdateMaterialDistancesForTerrainNode` as the sole caller, notes `surface.layerCount` is an unconstrained `uint` (line 499), and that the callback's buffer is sized to `ST_MAX_LAYERS_PER_SURFACE_OMPV`. Cites lines 499, 5008, 5014, 5028.

#### Lead 3 — Callback bounds checks (3 rounds, answered, medium confidence)

| Round | Tool | Args | Found? | Cached? | LOC |
|-------|------|------|--------|---------|-----|
| seed | get_caller_function | *(flagged function)* | yes | no | 27 |
| 1 | get_caller_function | `R_ST_IterateLayerMask` | yes | no | 27 |
| 2 | get_function_code | `R_Stream_UpdateMaterialDistancesForTerrainNode` | yes | no | 27 |

3 tool calls, 0 cached (ran concurrently with Lead 1 — neither saw the other's cache). **Cost**: $0.060, 14,287 tokens, 70s. **Fastest lead**.

**Finding**: Identifies the lambda as sole callback, notes it indexes `surface.layerMaterials[layerIndex]` and `materialDistancesSq[layerIndex]` immediately with zero bounds checks. Cites lines 5014, 5016, 5021-5024, 5028.

### LOC Analysis

| Lead | Initial LOC | Tool LOC | Total LOC | Avg LOC/call | Tool calls |
|------|-------------|----------|-----------|-------------|------------|
| Lead 1 | 17 | 67 | 84 | 11.2 | 8 |
| Lead 2 | 17 | 183 | 200 | 36.6 | 5 |
| Lead 3 | 17 | 81 | 98 | 27.0 | 3 |
| **Run total** | **17** | **331** | **382** | **20.7** | **16** |

Lead 2's high avg LOC/call (36.6) is from fetching `StDiskTerrainSurface` (100 LOC) — a large class definition.

### Cache Effectiveness

| Tool call | Cached by | Used by |
|-----------|-----------|---------|
| `get_caller_function(R_ST_IterateLayerMask)` | Lead 3 | Lead 2 |
| `get_macro_or_global(ST_MAX_LAYERS_PER_SURFACE_OMPV)` | Lead 1 | Lead 2 |
| `get_function_code(R_Stream_UpdateMaterialDistancesForTerrainNode)` | Lead 3 | Lead 2 |

3 of 16 calls served from cache (19%). Lead 2 benefited most — 3 of its 5 calls were cache hits from the other two parallel leads.

### Cross-Run Comparison (updated)

| Run | Leads | Tools | Tokens | LOC | Cost | Duration | Verdict | Notes |
|-----|-------|-------|--------|-----|------|----------|---------|-------|
| run_001 | 3 | 22 | 79,791 | — | $0.19 | 219s | — | Incomplete (missing synthesize) |
| run_002 | 3 | 30 | 122,750 | — | $0.37 | 435s | TP | High token/tool usage |
| run_004 | 4 | 18 | 50,522 | — | $0.16 | 200s | TP | 4-lead plan, cheapest complete |
| run_005 | 4 | 18 | 55,819 | — | $0.21 | 214s | TP | Similar to run_004 |
| run_006 | 4 | 21 | 91,028 | — | $0.37 | 349s | TP | Higher cost |
| run_007 | 4 | 0 | 4,955 | — | $0.01 | 10s | More Data | Plan-file replay (no DB) |
| run_008 | 3 | 10 | 49,386 | 205 | $0.25 | 216s | TP | Best efficiency (sequential) |
| run_011* | 3 | 3 | 7,873 | 7 | $0.01 | 11s | — | Lead 1 only replay (TypeAlias fix) |
| **run_012** | **3** | **16** | **83,600** | **382** | **$0.32** | **191s** | **TP** | **Parallel leads + TypeAlias** |

*run_011 was a single-lead replay, not a full pipeline run.*

### Analysis

**Correctness**: Parallel execution produced the same TP verdict with the same evidence chain as sequential runs. All three leads answered, findings are factual and well-cited.

**Speed**: 191s total vs 216s for run_008 — **12% faster wall-clock** despite doing more work (16 vs 10 tool calls). The investigate phase saw 2.3× parallelism (294s LLM time in 126s wall time). The speedup is modest for 3 leads because LLM latency dominates and the Azure endpoint likely throttles concurrent requests. The benefit will be larger with 4+ leads or during off-peak hours.

**Cost increase**: $0.32 vs $0.25 (+28%). The extra cost comes from Lead 1 doing 8 tool calls (vs 4 in run_008) because it independently traced the full bitset specialization chain. In run_008's sequential mode, Lead 2 reused Lead 1's cached results more effectively because it started after Lead 1 completed. With parallel execution, leads start together so the first few rounds can't benefit from each other's cache.

**Trade-off**: Parallel leads trade slightly higher cost for faster wall-clock time. For runs with more leads or during peak Azure load, the wall-clock savings will be proportionally larger.
