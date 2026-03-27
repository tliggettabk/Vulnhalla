# CID 15518 — Lead 1 Deep Dive

## 2026-03-26 — TypeAliasLookup validation (v2 replay after typedef fix)

### Issue Context
- **Coverity event:** `overrun-call` — Overrunning callee's array of size 256 by passing argument `layerIndex` (which evaluates to 256)
- **File:** `SuperTerrainDefines.h`, line 220
- **Function:** `R_ST_IterateLayerMask`
- **Core question:** Can `layerIndex` reach 256 and overflow the callback's 256-element array?

### Lead Assignment
- **Question:** How is `layerMask.num_bits` (checked at line 216) defined within `StLayerMaskOMPV`, and what fixed or dynamic size limit does it impose on valid `layerIndex` values?
- **Why it matters:** The only bound on `layerIndex` before the callback at line 220 is `while (layerIndex < layerCount)`, and line 216's `core_assert(layerCount <= layerMask.num_bits)` is a no-op in production. Understanding `num_bits` is essential to know the theoretical maximum.
- **Seed tool:** `get_class(StLayerMaskOMPV)`

### Run Metrics

| Metric | v1 (original, no typedef CSV) | v2 (with TypeAliasLookup) | Delta |
|--------|-------------------------------|---------------------------|-------|
| Tool calls | 15 | **3** | **-80%** |
| Rounds | 12 (budget exhausted) | **3** | **-75%** |
| Prompt tokens | 51,561 | 7,227 | -86% |
| Completion tokens | 26,468 | 646 | -98% |
| Total tokens | 78,029 | **7,873** | **-90%** |
| Estimated cost | $0.294 | **$0.012** | **-96%** |
| Duration | 674s | **10.8s** | **-98%** |
| Answered | false | **true** | fixed |
| Confidence | low | **high** | fixed |

### Tool Call Sequence

#### v1 — Original (15 tools, 12 rounds, never answered)

| # | Tool | Argument | Found | LOC | Assessment |
|---|------|----------|-------|-----|------------|
| 1 | get_class | `StLayerMaskOMPV` | **No** | 0 | **Essential** — correct seed, but typedef not in Classes.csv |
| 2 | get_macro_or_global | `StLayerMaskOMPV` | No | 0 | **Reasonable** — checking if it's a macro/global typedef |
| 3 | get_function_code | `StLayerMaskOMPV::find_first_bit` | No | 0 | **Reasonable** — trying to reach the class through its methods |
| 4 | get_caller_function | `R_ST_IterateLayerMask` | Yes | 27 | **Marginal** — hoping callers reveal the type definition |
| 5 | get_macro_or_global | `ST_MAX_LAYERS_PER_SURFACE_OMPV` | Yes | 2 | **Essential** — found the constexpr alias |
| 6 | get_macro_or_global | `ST_MAX_LAYERS_PER_SURFACE_OMPV_NON_UTS` | Yes | 2 | **Essential** — resolved to 256 |
| 7 | get_class | `ntl::bitset` | No | 0 | **Marginal** — trying parent template class |
| 8 | get_function_code | `ntl::bitset<256Ui64,...>::find_first_bit` | Yes | 5 | **Marginal** — probing specialization for num_bits |
| 9 | get_function_code | `R_ST_IterateLayerMask` | Yes | 17 | **Wasteful** — function visible in initial code |
| 10 | get_function_code | `R_ST_GetLayerMask` | Yes | 7 | **Marginal** — probing related functions for context |
| 11 | get_function_code | `ToStLayerMaskOMPV_RO` | Yes | 7 | **Marginal** — probing conversion helpers |
| 12 | get_macro_or_global | `ST_NUM_UINTS_FOR_LAYER_MASK` | Yes | 2 | **Marginal** — probing storage layout |
| 13 | get_macro_or_global | `ST_MAX_LAYERS_PER_SURFACE_OMPV` | Yes (cached) | 2 | **Duplicate** — already retrieved at #5 |
| 14 | get_macro_or_global | `ST_MAX_LAYERS_PER_SURFACE_OMPV_NON_UTS` | Yes (cached) | 2 | **Duplicate** — already retrieved at #6 |
| 15 | get_class | `ntl::bitset<256Ui64, 0Ui64, unsigned long long>` | Yes | 641 | **Wasteful** — 641 LOC dump of the full bitset class, far too late |

**Summary:** The model found the key data at tools #5–6 (the macro chain resolving to 256) but couldn't connect it back to `StLayerMaskOMPV` without the typedef definition. It spent tools #7–15 circling around the problem, retrieving related functions and eventually dumping the entire 641-line bitset class looking for `num_bits`.

#### v2 — With TypeAliasLookup (3 tools, 3 rounds, answered)

| # | Tool | Argument | Found | LOC | Assessment |
|---|------|----------|-------|-----|------------|
| 1 | get_class | `StLayerMaskOMPV` | **Yes** | 3 | **Essential** — now resolved via TypeAliasLookup.csv |
| 2 | get_macro_or_global | `ST_MAX_LAYERS_PER_SURFACE_OMPV` | Yes | 2 | **Essential** — follows template parameter |
| 3 | get_macro_or_global | `ST_MAX_LAYERS_PER_SURFACE_OMPV_NON_UTS` | Yes | 2 | **Essential** — resolves to literal 256 |

**Every call essential. Zero waste.** The LLM followed a straight chain: alias definition → template parameter → constant value.

### What It Was Stuck On

**Tool gap — `typedef`/`using` aliases invisible to `get_class()`.** `StLayerMaskOMPV` is defined as:
```cpp
using StLayerMaskOMPV = ntl::bitset<ST_MAX_LAYERS_PER_SURFACE_OMPV>;
```
This is a `UsingAliasTypedefType` in CodeQL — a subtype of `TypedefType`, which is **not** a `NameQualifyingElement`. `Classes.ql` only queries `NameQualifyingElement`, so the alias was invisible.

The fix was `TypeAliasLookup.csv` — a new CodeQL query + CSV + `get_class()` fallback. See `_rearch/__CSV-maintenance.md` for the full implementation story including the three CodeQL gotchas discovered along the way.

### Was the Conclusion Right?

**v1:** Never answered. The model accumulated enough evidence (macros resolving to 256, bitset class layout) to potentially answer, but couldn't bridge the gap without knowing `StLayerMaskOMPV = ntl::bitset<ST_MAX_LAYERS_PER_SURFACE_OMPV>`. Without the typedef, it couldn't prove `num_bits == ST_MAX_LAYERS_PER_SURFACE_OMPV == 256`.

**v2:** Correctly concluded that `num_bits == 256`, providing a clean evidence chain:
- Line 147: `using StLayerMaskOMPV = ntl::bitset<ST_MAX_LAYERS_PER_SURFACE_OMPV>;`
- Line 56: `inline constexpr uint ST_MAX_LAYERS_PER_SURFACE_OMPV = ST_MAX_LAYERS_PER_SURFACE_OMPV_NON_UTS;`
- Line 51: `inline constexpr uint ST_MAX_LAYERS_PER_SURFACE_OMPV_NON_UTS = 256;`

This directly closes the gap noted in the run_008 analysis (Section 10 item 2): "No lead explicitly confirmed `StLayerMaskOMPV`'s `num_bits` capacity."

### Cross-Lead Summary

CID 15518 run_011 has 4 leads:

| Lead | Question | v1 Tools | v1 Result | v2 Status |
|------|----------|----------|-----------|-----------|
| **1** | `num_bits` capacity of `StLayerMaskOMPV` | 15 | not answered, low | **3 tools, answered, high** |
| 2 | `find_first_bit` / `find_first_bit_from` return range | 8 | answered, high | not re-run |
| 3 | Caller bounds/validation on `layerCount` | 1 | answered, medium | not re-run |
| 4 | Callback operator() bounds on `layerIndex` | 1 | answered, medium | not re-run |

Lead 1 was the bottleneck. Leads 2–4 all answered successfully in v1. With Lead 1 now fixed, a full re-run would have all 4 leads answered — enabling a stronger synthesis.

### Lessons / Improvement Ideas

1. **TypeAliasLookup.csv is the fix.** The `using` alias gap caused 80% of this lead's cost. With the CSV, it's a 3-tool, $0.01 investigation.
2. **The model's "not-found spiral" was rational.** Every v1 tool call was *logically reasonable* given what the model knew — it just couldn't find the one piece of data it needed. This isn't a prompt problem; it's a tool gap.
3. **The model found the answer in v1 but couldn't prove it.** Tools #5–6 gave `ST_MAX_LAYERS_PER_SURFACE_OMPV = 256`, and the flagged code uses `StLayerMaskOMPV`, but without the `using` definition linking the two, the model couldn't close the chain. It answered `false` rather than speculate — correct behavior.
4. **v1 tool #15 (641 LOC bitset dump) was a desperation move.** When all else fails, the model tried downloading the entire class definition. This succeeded (it found the class) but at massive cost. The TypeAliasLookup fix makes this unnecessary.
