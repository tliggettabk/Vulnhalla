# CID 20212 — Lead 2 Deep Dive

## 2026-03-23 — Post-Batch Analysis (FunctionLookup.csv v1)

### Issue Context
- **Coverity Message:** `Event overrun-call: Overrunning callee's array of size 8 by passing argument "hknpLevelOfDetail::INVALID" in call to "setBodyAndShapeWithLevelOfDetail"`
- **File:** `WaterDynamics_PhysicsBehavior.cpp:1794`
- **Function:** `CalcSDFPoints` — water dynamics SDF query setup

### Lead 2 Assignment
**Question:** *What integral values and valid range does hknpLevelOfDetail define, particularly for the INVALID constant used at line 1794?*

**Why it matters:** Lead 1 already found that `hknpLodShape::getShapeAtLod` does `m_variants[(int)level]` — a raw array index with **no bounds check**. Lead 2's job was to find the enum definition and confirm what `(int)INVALID` numerically equals, to determine if it overruns the 8-entry array.

### Run Metrics
| Metric | Value |
|--------|-------|
| Tool calls | 13 |
| Cached | 0 |
| Found | 9/13 (69%) |
| Rounds | 12 (budget exhausted) |
| Tokens | 231K (163K prompt + 68K completion) |
| Cost | $0.863 |
| Duration | 832.6s |
| Confidence | low |
| Answered | false |

### Tool Call Sequence

| # | Tool | Argument | Found | Assessment |
|---|------|----------|-------|------------|
| 1 | `get_class` | `hknpLevelOfDetail` | No | Correct first attempt. Enum/struct not indexed by CodeQL's class table |
| 2 | `get_class` | `hknpCdBodySdf` | Yes (9 LOC) | Reasonable — hoping definition lived nearby. Only got forward-references |
| 3 | `get_class` | `hknpShape` | Yes (646 LOC) | **Goldmine it didn't recognize.** `hknpShape.h` uses `hknpLevelOfDetail` as a member type (lines 212, 246) but its definition is in a separate `#include`d header |
| 4 | `get_class` | `hknpShapeType` | Yes (59 LOC) | Marginal — saw similar Havok enum pattern (`INVALID` after sentinel). Didn't prove `hknpLevelOfDetail` follows same pattern |
| 5 | `get_macro_or_global` | `hknpLevelOfDetail` | No | Reasonable fallback. But it's a struct containing an enum, not a macro |
| 6 | `get_macro_or_global` | `HKNP_SHAPE_DEFAULT_CONVEX_RADIUS` | Yes | **Wasteful.** Hoped for "surrounding context" but macro tool returns only the body |
| 7 | `get_class` | `hknpShapeKey` | No | Hopeful probing — different Havok type hoping for transitive include |
| 8 | `get_class` | `hknpCdBody` | Yes (9 LOC) | Same strategy, same result — no `hknpLevelOfDetail` |
| 9 | `get_class` | `hknpShapeCollector` | Yes (158 LOC) | More neighbor-walking |
| 10 | `get_class` | `hknpShapeCollector::Internal` | Yes | Duplicate content from call 9 |
| 11 | `get_class` | `hknpShapeSignals` | Yes (51 LOC) | Different header entirely. No relevant info |
| 12 | `get_class` | `hknpLevelOfDetail::Enum` | No | Last-ditch attempt at nested enum |
| 13 | `get_class` | `hknpShapeKeyMask` | Yes (75 LOC) | Final probe. Showed same `INVALID` pattern but for a different type |

### What It Was Stuck On

**A tool gap.** `hknpLevelOfDetail` is a small Havok struct containing only a nested `Enum` — likely declared in `hknpTypes.h` or its own tiny header. It has no member functions or data members beyond the enum, so CodeQL's class extractor didn't index it.

After `get_class(hknpLevelOfDetail)` and `get_macro_or_global(hknpLevelOfDetail)` both returned not-found, the model had **no remaining path** to the definition. It spent calls 6–13 probing neighboring Havok types hoping one header would transitively include the definition. None did.

The model **correctly recognized it was stuck** but kept trying because the system prompt says "ALWAYS try requesting tools before concluding you cannot answer."

### Was the Conclusion Right?

**Final verdict: 7331 (Need More Data) — defensible but conservative.**

The synthesizer correctly identified the evidence gap: without knowing `(int)hknpLevelOfDetail::INVALID`, it can't prove the overrun.

**However**, a human analyst could make a stronger call. Lead 1 found:
1. `setBodyAndShapeWithLevelOfDetail` checks `shape->getType() == hknpShapeType::LOD` (line 72)
2. If LOD → `setLevelOfDetail(levelOfDetail)` → `lodShape->getShapeAtLod(level)` → `m_variants[(int)level]` (line 14) — **no bounds check**
3. `hknpShapeType::Enum` shows the Havok SDK pattern: `INVALID` sits *after* `NUM_SHAPE_TYPES` sentinel (the highest value)
4. Coverity specifically says the array has 8 entries

If `hknpLevelOfDetail` follows the same `{valid..., NUM, INVALID}` pattern (standard in this SDK), then `(int)INVALID` ≥ 8, causing the overrun. A human would likely call this **1337 (TP)** based on the pattern + Coverity's array-size claim.

### Cross-Lead Summary

| Lead | Question | Answered | Confidence | TCs | Cost |
|------|----------|----------|------------|-----|------|
| 1 | How does `setBodyAndShapeWithLevelOfDetail` use the lod argument? | Yes | high | 4 | $0.046 |
| 2 | What values does `hknpLevelOfDetail` define? | No | low | 13 | $0.863 |
| 3 | How does `getShapeAtLod` validate the shape pointer? | Yes | high | 10 | $0.171 |

**Final synthesis verdict:** 7331 — additional evidence needed for (a) numeric value of `hknpLevelOfDetail::INVALID` and (b) variant array size confirmation.

### Lessons / Improvement Ideas

1. **Enum/small-struct coverage gap** — `get_class` doesn't find types that are only enums or small structs without member functions. A `get_type` or `get_enum` CodeQL query could close this gap.
2. **Wind-down compliance** — model received the "running low on tool calls" nudge at round 9 but continued probing for 3 more rounds. Could have answered with partial evidence sooner.
3. **Cross-lead synthesis weakness** — Lead 1 already found `m_variants[(int)level]` with no bounds check, and `hknpShapeType` showed the `INVALID`-after-sentinel pattern. The synthesizer could have inferred the answer from these combined leads rather than treating Lead 2's failure as a blocker.

---

## 2026-03-24 — Post-EnumLookup.csv Fix (v4 Replay)

### What Changed

`EnumLookup.csv` was created with a smart structural parser that indexes all standalone `enum`/`enum class` types from the CodeQL database. `get_class()` in `db_lookup.py` now falls back to this CSV when `Classes.csv` doesn't have the type. See [\_rearch/\_\_CSV-maintenance.md](__CSV-maintenance.md) for full details.

### Replay Result

| Metric | Original (run_001) | Replay (v4) | Delta |
|--------|-------------------|-------------|-------|
| Tool calls | 13 | **1** | -92% |
| Rounds | 12 (budget exhausted) | **1** | -92% |
| Found | 9/13 (69%) | **1/1 (100%)** | +31pp |
| Tokens | 231K | **5K** | -98% |
| Cost | $0.863 | **$0.014** | -98% |
| Duration | 832.6s | **18.3s** | -98% |
| Confidence | low | **high** | — |
| Answered | false | **true** | — |

### What Happened

`get_class('hknpLevelOfDetail')` hit `EnumLookup.csv` on the fallback path and returned the full 23-line enum definition from `hknpTypes.h` (lines 707–728). The LLM read the enumerators directly and answered in one round:

> **hknpLevelOfDetail** is an `enum class` backed by `hkUint8`. Valid levels range from `HIGH=0` through `USER_4=7`, with `NUM_LEVELS=8`. **INVALID = 0xF** (decimal 15), a sentinel value outside the valid range.

This is the exact answer Lead 2 was trying to find across 13 tool calls and 12 rounds.

### Impact on Synthesis

With Lead 2 now answering `INVALID = 0xF = 15` and Lead 1 showing `m_variants[(int)level]` indexes an 8-entry array with no bounds check, the overrun is confirmed: `(int)0xF = 15 ≥ 8`. This CID should upgrade from **7331 (Need More Data)** to **1337 (True Positive)**.

### Lesson Validated

Item 1 from the original analysis ("Enum/small-struct coverage gap") is now fixed. The `EnumLookup.csv` pipeline delivers 10,760 correct enum definitions with **0 wrong results** from 15,829 raw CodeQL rows, using a smart parser that structurally classifies forward declarations, wrong-name matches, macro-based enums, and typedef patterns.
