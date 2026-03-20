# CID-19309 Analysis

**Vulnerability:** Memory - illegal accesses (array overrun in `glass_crack_shard.cpp:836`)  
**Issue:** `coord[vertIter - 1]` where `vertIter` is `uint` and can be 0 when `vertCount == 1`, causing unsigned underflow to index `4294967295`  
**Function:** `Glass_AreaX2AndScaledCentroidForEdgeLoop`

---

## Run Comparison Table

| Metric | Run 1 (3/17) | Run 2 (3/18 AM) | Run 4 (3/18 PM, Latest) |
|--------|-------------|-----------------|------------------------|
| **Model** | azure/gpt-5.1-codex | azure/gpt-5.1-codex | azure/gpt-5.1-codex |
| **Verdict** | **1337 (TP)** | **1007 (FP)** | **1337 (TP)** |
| **Rounds** | 2 | 21 (hit tool limit) | 4 |
| **Tool Calls** | 2 | 16 | 3 |
| **Tokens** | ~4,500 (est.) | ~25,600 (est. from file size) | 19,079 |
| **Cost** | ~$0.03 (est.) | ~$0.15 (est.) | $0.1061 |
| **Duration** | N/A | N/A | 112s |
| **Correct?** | Yes | **No** | Yes |

---

## Run 1 — 2026-03-17 (file: `1_final.json`)

### System Prompt
Original (simpler) system prompt — no assertion warning, no evidence-based analysis rules, no tool dedup rules.

### Tool Requests
1. `get_macro("GLASS_VERT_PER_PIECE_LIMIT")` → returned `#define GLASS_VERT_PER_PIECE_LIMIT 128` — **Needed, reasonable**
2. `get_macro("ARRAY_COUNT")` → returned the macro definition — **Needed, reasonable**

### Analysis Quality
- Correctly identified that `vertCount` can be 1 (do-while loop runs at least once)
- Correctly traced: `vertIter = vertCount - 1 = 0`, then `vertIter - 1` underflows to `UINT_MAX`
- Correctly noted `core_assert_index` is not runtime protection
- Reached **1337** — **correct conclusion**

### Assessment
Efficient run. Only 2 tool calls, both useful. Drew conclusion purely from local code analysis. Did not need caller context to determine the function was vulnerable in isolation.

---

## Run 2 — 2026-03-18 AM (file: `2_final.json`)

### System Prompt
Original (simpler) system prompt — same as Run 1.

### Tool Requests
1. `get_caller_function()` — **Reasonable** (wanted to check if callers guarantee vertCount >= 2)
2. `get_class("FxGlassShard")` — **Reasonable** (understanding data structures)
3. `get_class("FxGlassShardEdgeLoop")` — **Reasonable**
4. `get_class("FxGlassCrackEdge")` — **Needed** (understanding edge loop structure)
5-10. `get_class("FxGlassCrackEdge")` x6 more times — **REDUNDANT** (same args, same result every time)
11. `get_function_code("FxGlassCrackEdge")` — **Not useful** (tried function lookup for a struct)
12. `get_class("struct FxGlassCrackEdge")` — **Redundant variant** (same struct, different query format)
13. `get_caller_function()` — **Redundant** (already called)
14. `get_function_code("Glass_ExtractShardCracksAndHoles")` — **Reasonable** (examining caller)
15. `get_function_code("Glass_ExtractCracksAndHolesFromLoop")` — **Reasonable** (examining loop construction)
16. Hit tool limit — forced to conclude

### Analysis Quality
- The LLM went deep into caller analysis and concluded that callers guarantee `vertCount >= 3` based on `Glass_ExtractCracksAndHolesFromLoop` logic
- This reasoning is **plausible but unverifiable** — it depends on ALL callers enforcing this invariant, which isn't guaranteed
- The function itself has no guard and is `static` but reachable from multiple paths
- Reached **1007 (FP)** — **incorrect conclusion** (or at best debatable)

### Assessment
**Major issue: 6 redundant `get_class("FxGlassCrackEdge")` calls** consumed most of the tool budget. The LLM kept retrying the same query hoping for a fuller struct definition. This wasted rounds and ultimately forced a premature conclusion via the tool limit warning.

The caller-analysis approach is intellectually interesting but led to an **overconfident false-negative**. The function is unconditionally vulnerable if called with a 1-vertex loop, and the LLM's claim that callers always provide 3+ vertices is a strong assumption.

---

## Run 4 — 2026-03-18 PM, Latest (file: `4_final.json`)

### System Prompt
**Enhanced prompt** with:
- `EVIDENCE-BASED ANALYSIS` rule (treat static analyzer findings as evidence to investigate, not dismiss)
- `ASSUMPTION VALIDATION` rule (verify that critical assumptions are true)
- `CRITICAL: Do NOT rely on assertions` rule
- `Tool Usage Rules` with explicit dedup instructions (check conversation for prior identical calls)
- `7337` conflicting evidence status code with lean directional confidence

### Tool Call Breakdown

| # | Tool | Args | Result | Needed? |
|---|------|------|--------|---------|
| 1 | `get_class` | `FxGlassCrackEdge` | 4-line truncated struct from `glass_crack_types.h` (lines 26-29: `struct FxGlassCrackEdge { union {`) | **Yes** — needed to understand the edge loop data structure, specifically how `next` pointer enables circular linked list traversal |
| 2 | `get_class` | `FxGlassCrackEdge` | Same 4-line truncated result | **Redundant** — exact same tool + args as #1. Violated the explicit dedup rule in the system prompt. Likely retried because result was truncated and LLM hoped for more |
| 3 | `get_macro` | `GLASS_VERT_PER_PIECE_LIMIT` | `#define GLASS_VERT_PER_PIECE_LIMIT 128` | **Yes** — confirms array `coord[128][2]` size, needed to validate static analyzer's overflow claim |

**Efficiency: 2 of 3 calls productive (67%). 1 redundant.**

### What It Did NOT Ask For (But Could Have)

| Missing Request | Why It Would Help | Impact on Conclusion |
|----------------|-------------------|---------------------|
| `get_caller_function()` | Would show which functions call `Glass_AreaX2AndScaledCentroidForEdgeLoop` and what constraints callers impose on edge loops | **Low impact** — the function is vulnerable in isolation regardless of callers. Run 2 went down this path and reached the wrong conclusion (1007) by over-trusting caller guarantees |
| `get_macro("ARRAY_COUNT")` | Run 1 asked for this; confirms the assert's size check | **Low impact** — the LLM correctly dismissed `core_assert_index` as debug-only without needing its exact expansion |
| `get_macro("core_assert_index")` | Would confirm it's a debug assert compiled out in release | **Low impact** — the system prompt's assertion warning was sufficient; the LLM correctly treated it as non-protective without needing proof |
| Full `FxGlassCrackEdge` struct | The truncated 4-line result didn't show the `next` pointer or `i0` member used in the code | **Low impact** — the code context already shows `edgeIter->next` and `edgeIter->i0`, so the struct definition was supplementary |

### Did It Have All the Info Needed?

**Yes.** The critical information was already in the code context provided in the prompt:
- The `do-while` loop guarantees `vertCount >= 1` (runs at least once)
- `vertIter = vertCount - 1` means `vertIter = 0` when `vertCount == 1`
- `coord[vertIter - 1]` with `uint vertIter = 0` underflows to `4294967295`
- `core_assert_index` is the only guard, and the prompt explicitly warned not to rely on assertions

The LLM didn't strictly *need* any tool calls — the vulnerability is fully visible in the provided function code. The `get_macro` call for `GLASS_VERT_PER_PIECE_LIMIT` confirmed the array size (128), which is good practice but not essential since the static analyzer already stated "128 16-byte elements."

### Did It Reach the Correct Conclusion? Why?

**Yes — 1337 (True Positive).** The reasoning was sound:

1. Correctly identified `vertCount == 1` as the trigger (single-vertex edge loop)
2. Correctly traced the arithmetic: `vertIter = 0`, then `vertIter - 1` = `UINT_MAX`
3. Correctly rejected `core_assert_index` as protection (following the system prompt's assertion warning)
4. Correctly described the impact: "corrupting stack memory"

**Why it succeeded where Run 2 failed:** The enhanced system prompt's evidence-based analysis rule kept the LLM focused on the local function's vulnerability rather than chasing caller guarantees. Run 2 spent 21 rounds investigating callers and concluded (incorrectly) that callers always provide 3+ vertices.

### Assessment

**Strengths:**
- Efficient — 4 rounds, 3 tool calls, correct answer in 112s
- Focused — didn't waste rounds investigating callers (unlike Run 2's 21 rounds)
- Correctly applied the assertion warning from the enhanced prompt
- Clear, specific exploit description

**Weaknesses:**
- 1 redundant `get_class` call despite explicit dedup rules in the system prompt — suggests dedup instructions alone aren't sufficient; programmatic enforcement would help
- `get_class` returned truncated results (4 lines of a struct), which is what triggered the retry. Root cause is the tool returning incomplete data, not the LLM's judgment
- Didn't verify `core_assert_index` is debug-only (relied on system prompt instruction instead of evidence). This happened to be correct, but evidence-based verification would be more robust

---

## Key Findings & Suggested Improvements

### What Worked Well
1. **Enhanced prompt** (Run 4) dramatically improved focus and efficiency vs Run 2
2. **Assertion warning** correctly prevented false-negative reasoning
3. **Evidence-based analysis** kept the LLM grounded in the reported issue
4. Run 4 was efficient: 4 rounds, 3 tool calls, correct answer

### What Needs Improvement
1. **Tool dedup still not fully working** — Run 4 still called `get_class("FxGlassCrackEdge")` twice despite explicit rules. Consider programmatic dedup (intercept duplicate calls before sending to LLM API).
2. **`get_class` returns truncated results** — the struct definition appears cut off at 4 lines. If the LLM can't see the full struct, it retries. Fix: return the complete struct/class definition.
3. **Run 2 showed dangerous caller-analysis drift** — the LLM went 21 rounds chasing caller guarantees and reached the wrong conclusion. The new prompt fixes this, but consider adding a hard round limit earlier (e.g., 8 rounds) to prevent runaway analysis.
4. **No cost data for prior runs** — only run_summary.json from the latest run is available. Consider appending to a run history log rather than overwriting.

### Correct Conclusion
**True Positive (1337)**. The function `Glass_AreaX2AndScaledCentroidForEdgeLoop` has no guard ensuring `vertCount >= 2`. When a single-vertex edge loop is passed, `vertIter = 0` and `coord[vertIter - 1]` underflows to `coord[4294967295]`, a massive out-of-bounds stack read. The `core_assert_index` check in the vertex-copy loop is a debug-only assertion and provides no protection in release builds.
