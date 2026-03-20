# CID 15518 - Comprehensive Tool Strategy and Information Sufficiency Analysis

## Overview
This analysis examines the strategic differences in tool usage between GPT-5.1-codx and GPT-4.1-mini when analyzing the same vulnerability finding (CID 15518), and critically evaluates whether either model obtained sufficient information to make an authoritative security decision.

## Vulnerability Context
- **CID**: 15518
- **Issue**: Buffer management vulnerability related to layer mask operations
- **Key Challenge**: Understanding `StLayerMaskOMPV` typedef structure for security analysis
- **Static Analyzer Claim**: *"Overrunning callee's array of size 256 by passing argument 'layerIndex' (which evaluates to 256)"*

## Tool Usage Pattern Comparison

### GPT-4.1-Mini Strategy
**Pattern**: Repetitive failed requests without adaptation

1. **First Request**: `StLayerMaskOMPV` class lookup
   - **Result**: Received `StLayerMaskOMPVRaw` (incorrect/incomplete typedef)
   - **Response**: Proceeded with incomplete information

2. **Second Request**: `StLayerMaskOMPV` class lookup (identical repeat)
   - **Result**: Received `StLayerMaskOMPVRaw` again (same incomplete result)
   - **Response**: Continued analysis with limited understanding

3. **Function Code Request**: `StLayerMaskOMPV::find_first_bit`
   - **Result**: Received wrapper function only: `return find_first_bit_from_block<FIND_ON>( 0 );`
   - **Critical Miss**: Did not get actual implementation that shows edge case behavior

**Tool Efficiency**: 3 tool calls - 2 wasted on identical failed requests, 1 incomplete function lookup

### GPT-5.1-Codx Strategy
**Pattern**: Adaptive problem-solving with strategic pivoting

1. **First Request**: `StLayerMaskOMPV` class lookup
   - **Result**: Received `StLayerMaskOMPVRaw` (recognized as incomplete)
   - **Response**: Identified typedef limitation

2. **Strategic Adaptation**: Pivoted to global constants approach
   - **Request**: `ST_MAX_LAYERS_PER_SURFACE_OMPV` global variable
   - **Result**: **SUCCESS** - Found relevant global constant
   - **Follow-up**: `ST_MAX_LAYERS_PER_SURFACE_OMPV_NON_UTS` global variable
   - **Result**: **SUCCESS** - Retrieved value `256` (security-critical size limit)

3. **Caller Context**: `get_caller_function` 
   - **Result**: **SUCCESS** - Got full calling context showing array access pattern

**Tool Efficiency**: 4 efficient tool calls with strategic adaptation and comprehensive context gathering

## Information Sufficiency Analysis

### What Each Model Actually Knew

#### GPT-4.1-Mini Information Inventory:
- ✅ Loop condition: `while (layerIndex < layerCount)`
- ✅ Assert: `layerCount <= layerMask.num_bits`
- ✅ Wrapper function: `find_first_bit()` calls `find_first_bit_from_block<FIND_ON>(0)`
- ❌ **Missing**: Actual array size (had no idea if it was 10, 100, or 1000)
- ❌ **Missing**: Caller context and usage patterns
- ❌ **Missing**: Complete `find_first_bit_from_block` implementation
- ❌ **Missing**: What happens when bitset is exhausted

#### GPT-5.1-Codx Information Inventory:
- ✅ Loop condition: `while (layerIndex < layerCount)`
- ✅ Assert: `layerCount <= layerMask.num_bits`
- ✅ **Critical advantage**: Actual array size = 256
- ✅ **Critical advantage**: Caller context showing `materialDistancesSq[layerIndex]` access
- ✅ **Critical advantage**: Size constraint `ST_MAX_LAYERS_PER_SURFACE_OMPV_NON_UTS = 256`
- ❌ **Missing**: Complete `find_first_bit_from_block` implementation
- ❌ **Missing**: What `find_first_bit_from()` returns when no more bits found

### The Fundamental Gap

**Neither model verified the critical assumption**: **What does `find_first_bit_from()` return when there are no more set bits?**

The static analyzer specifically warned: *"passing argument 'layerIndex' (which evaluates to 256)"*

This suggests `find_first_bit_from()` **can** return 256 (or potentially `NPOS`/max value) when no more bits are found, which would:
1. Pass the loop condition `while (layerIndex < layerCount)` if `layerCount > 256`  
2. Cause `callback(256)` to access `materialDistancesSq[256]` - an off-by-one buffer overflow for a 256-element array (indices 0-255)

## Strategic Analysis

### Key Differences

| Aspect | GPT-4.1-Mini | GPT-5.1-Codx |
|--------|--------------|----------------|
| **Problem Recognition** | Failed to recognize typedef limitation | Quickly identified incomplete typedef result |
| **Adaptation Strategy** | Repeated failed approach | Pivoted to alternative information source |
| **Information Gathering** | Incomplete typedef + wrapper function | Complete security-relevant size constants + caller context |
| **Tool Efficiency** | 2 wasted calls + 1 incomplete | 4 efficient adaptive usage |
| **Array Size Knowledge** | ❌ No size information | ✅ Knew exact size = 256 |
| **Caller Context** | ❌ No usage patterns | ✅ Complete calling context |
| **Security Analysis Quality** | Limited by missing fundamentals | Enhanced by actual constraints |

### Superior Information Gathering

GPT-5.1-codx demonstrated **significantly better information gathering** by:

1. **Recognizing Failed Approaches**: Immediately identified that `StLayerMaskOMPVRaw` was not the expected complete definition
2. **Strategic Pivoting**: Adapted to seek global size constants rather than repeating failures
3. **Security-Focused Investigation**: Prioritized actual size limits and usage patterns over incomplete structural data
4. **Comprehensive Context**: Obtained both size constraints AND caller usage patterns

## Critical Analysis: Did Either Have Enough Information?

### The Answer: **NO** - Neither model had sufficient information for authoritative decision

#### Information Adequacy Assessment:

**GPT-4.1-Mini**: **CRITICALLY INSUFFICIENT**
- Working completely blind on array sizes
- No understanding of actual usage patterns
- Incomplete function implementation
- Made security assessment without fundamental constraints

**GPT-5.1-Codx**: **BETTER BUT STILL INSUFFICIENT** 
- Had critical size information (256) and caller context
- **Major advantage**: Could validate static analyzer's specific claim about array size
- **Fatal gap**: Still didn't verify what bitset functions return when exhausted
- Made assumption about library behavior without verification

### The Core Issue Both Models Missed

**Contradictory Evidence Ignored**: The static analyzer provided **direct evidence** contradicting their analysis:

- **Both models concluded**: "Loop condition protects against layerIndex ≥ layerCount"
- **Static analyzer claimed**: "layerIndex evaluates to 256" 
- **Neither investigated**: How this contradiction could be possible

This represents a **fundamental failure in evidence-based reasoning** - both models dismissed contradictory evidence without investigation.

## Root Cause Analysis

### Why GPT-5.1-Codx Didn't Investigate Further

Despite superior tool strategy, GPT-5.1-codx made a critical oversight:

1. **Overconfidence in Logic**: Trusted loop-based protection without verifying dependencies
2. **Assumption Bias**: Assumed bitset functions behave safely without verification  
3. **Evidence Dismissal**: Didn't treat static analyzer's specific claim as challenge to investigate
4. **Missing Investigation**: Never asked "How could layerIndex reach 256 despite loop protection?"

### The Missing Investigation

**Neither model pursued the critical question**: What does `find_first_bit_from()` return when no more set bits are found?

**Likely answer**: Returns `NPOS` (typically `~0` or similar large value) which could be ≥ 256, bypassing loop protection and causing the exact overflow the static analyzer detected.

## Conclusions

### Strategic Superiority vs Information Adequacy

1. **GPT-5.1-codx demonstrated vastly superior tool strategy**:
   - Efficient adaptive usage vs repetitive failures
   - Security-focused information gathering vs blind analysis
   - Complete context gathering vs missing fundamentals

2. **However, both failed the evidence-based reasoning test**:
   - Neither investigated contradictory static analyzer evidence
   - Both made assumptions about library behavior without verification
   - Neither recognized the gap between their logic and analyzer findings

### Key Insights for LLM Security Analysis

1. **Tool Strategy Matters**: GPT-5.1-codx's superior approach was essential for getting security-relevant information
2. **Information Quality > Quantity**: Knowing actual size constraints was more valuable than multiple failed requests  
3. **Evidence-Based Reasoning Critical**: Both failed to investigate contradictory evidence from static analyzer
4. **Assumption Verification Essential**: Security conclusions require validating external dependencies

### Recommendations

**For improving LLM security analysis**:
1. **Mandate contradiction investigation**: When static analyzer findings conflict with analysis, require investigation
2. **Assumption validation**: Before concluding "secure," verify critical dependencies 
3. **Evidence-based reasoning**: Treat static analyzer claims as evidence to validate, not dismiss
4. **Strategic tool usage**: Promote adaptive investigation strategies over repetitive failed approaches

Research shows that **strategic intelligence in tool usage** combined with **evidence-based reasoning** is more critical for security analysis than raw analytical capability. GPT-5.1-codx's superior tool strategy was undermined by failing to investigate contradictory evidence - a lesson applicable across all vulnerability types.

---

## Run History & Cost Analysis

### How to Read This Section
Each Vulnhalla LLM analysis run produces two files per run in `output/results/c/15518/`:
- `{N}_raw.json` — prompt metadata (function tree, code context, prompt text)
- `{N}_final.json` — full conversation log (system/user/assistant/tool messages)

Token counts for a run appear in the terminal output as:
```
LLM token usage totals: prompt=NNNN, completion=NNNN, total=NNNN, findings=N
```
If terminal output is unavailable, estimate from `{N}_final.json`: line count, number of rounds, and number of tool calls. Each round resends the full growing conversation, so cost scales quadratically with rounds.

### Pricing Reference (Azure OpenAI GPT-5.1 Codex, pay-as-you-go)
- **Input**: ~$2.50 / 1M tokens
- **Output**: ~$10.00 / 1M tokens
- Adjust rates if using provisioned throughput or enterprise agreements.

### Per-Run Summary

<!-- 
  TO ADD A FUTURE RUN:
  1. Run step 5.2 per x02-updateLineNums/step5_llm_analysis.md
  2. Record terminal output token totals (prompt, completion, total)
  3. Check output/results/c/15518/ for new {N}_raw.json and {N}_final.json
  4. Read {N}_final.json to get: line count, rounds, tool calls, "too many tools" warnings, final status code
  5. Add a new row to the table below and a new entry in the detail section
  6. Update the "All Runs Combined" totals
-->

| Run | Model | Prompt Version | Rounds | Tool Calls | Throttle Warnings | Final Status | Correct? | Est. Prompt Tokens | Est. Completion | Est. Total | Est. Cost |
|-----|-------|---------------|--------|------------|-------------------|-------------|----------|-------------------|----------------|-----------|-----------|
| 1 | gpt-4.1-mini | v1 (simple hints) | 4 | 4 | 0 | 1007 (FP) | NO | ~4,500 | ~800 | ~5,300 | ~$0.02 |
| 2 | gpt-5.1-codex | v1 (simple hints) | 6 | 4 | 0 | 1007 (FP) | NO | ~8,000 | ~2,000 | ~10,000 | ~$0.04 |
| 3 | gpt-5.1-codex | v2 (evidence-based + 7337) | 15 | 12 | 7 | 1007 (FP) | NO | ~40,000 | ~5,000 | ~45,000 | ~$0.15 |
| 4 | gpt-5.1-codex | v3 (+ assert warning) | 12 | 11 | 6 | 1007 (FP) | NO | ~25,000 | ~3,500 | ~28,500 | ~$0.10 |
| **5** | **gpt-5.1-codex** | **v4 (detailed bounds hints)** | **28** | **27** | **22** | **1337 (TP)** | **YES** | **201,697** | **27,294** | **228,991** | **~$0.77** |
| 6 | gpt-5.1-codex | v5 (current prompts) | 7 | 6 | 0 | 1007 (FP) | NO | 18,832 | 5,526 | 24,358 | $0.0683 |
| 7–20 | gpt-5.1-codex | v5–v8 iterations | — | — | — | 1007 (FP) | NO | — | — | — | — |
| **21** | **gpt-5.1-codex** | **v9 (context field + "disabled in release")** | **12** | **11** | **1** | **1007 (FP)** | **NO** | **~30,000** | **~15,000** | **~45,000** | **~$0.15** |
| 22 | gpt-5.1-codex | v10 (NO-OPs + transitive) | 12 | 11 | 1 | — (timeout) | CRASH | — | — | — | — |
| **23** | **gpt-5.1-codex** | **v10 (NO-OPs + transitive + 300s timeout)** | **7** | **6** | **0** | **1337 (TP)** | **YES** | **~15,000** | **~8,000** | **~23,000** | **~$0.09** |
| **24** | **gpt-5.1-codex** | **v11 (trimmed — 3 bullets)** | **11** | **10** | **0** | **1337 (TP)** | **YES** | **30,322** | **15,685** | **46,007** | **$0.17** |
| **25** | **gpt-5.1-codex** | **v11 (trimmed — 3 bullets)** | **14** | **13** | **4** | **1337 (TP)** | **YES** | **98,771** | **12,747** | **111,518** | **$0.19** |
| **26** | **gpt-5.1-codex** | **v10 (revert test)** | **14** | **13** | **4** | **1337 (TP)** | **YES** | **40,212** | **19,702** | **59,914** | **$0.21** |
| **27** | **gpt-5.1-codex** | **v12 (user cuts)** | **5** | **4** | **0** | **1337 (TP)** | **YES** | **11,366** | **3,628** | **14,994** | **$0.04** |
| **28** | **gpt-5.1-codex** | **v13 (+ verify claims)** | **16** | **15** | **6** | **1337 (TP)** | **YES** | **48,800** | **21,490** | **70,290** | **$0.25** |

*Runs 5, 24–28 have exact token counts from terminal output. Runs 1-4 and 21-23 are estimates based on conversation size and round count.*

### Run Details

#### Run 1 — gpt-4.1-mini, v1 prompts
- **File**: `1_final.json` (82 lines, 6.6 KB)
- **Behavior**: 4 clean tool calls, no throttling. Got `StLayerMaskOMPVRaw` twice (identical repeat), got `find_first_bit` wrapper. Never found array size.
- **Conclusion**: *"The assertion and loop condition ensure that the callback is never called with an out-of-bounds index."*
- **Failure**: Relied on `core_assert` as security control; never verified array size or sentinel return value.

#### Run 2 — gpt-5.1-codex, v1 prompts
- **File**: `2_final.json` (99 lines, 7.4 KB)
- **Behavior**: 4 tool calls with adaptive pivoting to global vars. Found `ST_MAX_LAYERS_PER_SURFACE_OMPV_NON_UTS = 256` and caller context.
- **Conclusion**: *"Loop guard keeps layerIndex < layerCount (≤256)."*
- **Failure**: Better tool strategy but still assumed `layerCount` is always bounded; didn't investigate sentinel behavior.

#### Run 3 — gpt-5.1-codex, v2 prompts (evidence-based analysis, 7337 status code)
- **File**: `3_final.json` (296 lines, 19 KB)
- **Behavior**: 12 tool calls, hit throttle 7 times. Found constants and `core_assert` macro definition. More thorough investigation but kept requesting same class definition.
- **Conclusion**: *"Loop guard enforces layerIndex < layerCount ensuring callback never receives 256."*
- **Failure**: Enhanced prompt drove deeper investigation, but model still trusted loop guard without verifying `layerCount` is actually bounded at runtime.

#### Run 4 — gpt-5.1-codex, v3 prompts (+ "don't rely on assertions")
- **File**: `4_final.json` (171 lines, 14 KB)
- **Behavior**: 11 tool calls, hit throttle 6 times. Found the same constants chain. Repeatedly requested `get_class("StLayerMaskOMPV")` getting same result.
- **Conclusion**: *"Loop guard keeps callback indices < layerCount, and layerCount is bounded by the same 256-bit mask capacity."*
- **Failure**: Despite explicit instruction not to rely on assertions, still assumed `layerCount ≤ 256` is enforced.

#### Run 5 — gpt-5.1-codex, v4 prompts (detailed bounds-tracing hints) ✅
- **File**: `5_final.json` (864 lines, 48 KB)
- **Exact tokens**: prompt=201,697, completion=27,294, total=228,991
- **Behavior**: 28 rounds, 27 tool calls, throttled 22 times. ~73% of all tokens across all runs. Found full `ntl::bitset` class (656 lines), `find_first_bit_from_block` implementation, `core_assert` macro, and complete constant chain.
- **Conclusion**: *"Passing layerCount > 256 lets layerIndex reach the sentinel value 256, causing the callback to index past an array[256]."*
- **Success factors**: Detailed hint questions forced mathematical verification of bounds. Model verified `core_assert` is debug-only, traced sentinel return value (`num_bits = 256`), and correctly identified that `layerCount` has no runtime enforcement in release builds.
- **Inefficiency**: ~20 of 27 tool calls were redundant (see breakdown below).

#### Run 5 Tool Call Breakdown

**Necessary & Productive Calls (~7-10 of 27)**

| # | Tool Call | Purpose | Result | Verdict |
|---|-----------|---------|--------|---------|
| 1 | `get_class("StLayerMaskOMPV")` | Find array structure | Got `StLayerMaskOMPVRaw` with `data[ST_NUM_UINTS_FOR_LAYER_MASK]` | Productive (1st time) |
| 2 | `get_global_var("ST_NUM_UINTS_FOR_LAYER_MASK")` | Trace constant chain | `= ST_MAX_LAYERS_PER_SURFACE_OMPV / (sizeof(uint32_t) * 8)` | Productive |
| 3 | `get_global_var("ST_MAX_LAYERS_PER_SURFACE_OMPV")` | Continue chain | `= ST_MAX_LAYERS_PER_SURFACE_OMPV_NON_UTS` | Productive |
| 4 | `get_global_var("ST_MAX_LAYERS_PER_SURFACE_OMPV_NON_UTS")` | Find final value | **= 256** (critical) | Productive |
| 5 | `get_function_code("find_first_bit")` | Understand sentinel behavior | Returns `find_first_bit_from_block(0)` | Productive |
| 6 | `get_function_code("find_first_bit_from")` | Trace return values | Returns `num_bits` when not found | Productive |
| 7 | `get_function_code("find_first_bit_from_block")` | Confirm sentinel = num_bits | `return num_bits;` (line 611) | Productive |
| 8 | `get_class("ntl::bitset")` | Get full bitset definition | `num_bits = T_SIZE` enum, full 656-line class | Productive |
| 9 | `get_macro("core_assert")` | Verify if debug-only | Confirmed: just an assert macro | Productive |

**Unnecessary / Redundant Calls (~18-20 of 27)**

| Pattern | Count | What Happened |
|---------|-------|---------------|
| `get_class("StLayerMaskOMPV")` repeated | ~8x | Always returned the same 3-line `StLayerMaskOMPVRaw` snippet. Kept retrying hoping for the actual `ntl::bitset` typedef. |
| `get_macro` on `inline constexpr` vars | ~6x | Tried `ST_NUM_UINTS_FOR_LAYER_MASK`, `ST_MAX_LAYERS`, `ST_LAYER_MASK_NUM_BITS`, `ST_MAX_SURFACE_LAYERS`, `ST_LAYER_MASK_UINTS`, `R_ST_MAX_ELEVATION_LAYERS` — all returned "not found" because they're `inline constexpr` globals, not preprocessor macros. |
| `get_global_var` on non-existent names | ~3x | Tried `StLayerMaskOMPV::num_bits`, `StLayerMaskOMPV`, `ST_LAYER_MASK_TYPE` — none exist as standalone globals. |
| Re-tracing already-found constants | ~3x | After tool-call limit messages reset context, re-requested `ST_MAX_LAYERS_PER_SURFACE_OMPV` and `ST_MAX_LAYERS_PER_SURFACE_OMPV_NON_UTS` that were already retrieved. |

**Root cause of redundancy**: The tool-call limit (6) kicked in after round 6. Each subsequent "You called too many tools!" system message appeared to reset the model's working memory, causing it to re-request data it already had. The `get_class` tool also consistently returned `StLayerMaskOMPVRaw` instead of the full `ntl::bitset` typedef that `StLayerMaskOMPV` actually resolves to, leaving the model stuck in a retry loop.

### Key Observations

1. **Prompt quality was the decisive factor** — same model (gpt-5.1-codex) got it wrong 3 times with weaker prompts, right once with detailed bounds-tracing hints.
2. **Cost scales quadratically with rounds** — Run 5 used ~73% of all tokens due to the 28-round loop, mostly from redundant tool calls.
3. **The "too many tools" throttle is counterproductive** — it resets the model's working memory, causing it to re-request data it already had, inflating both rounds and cost.
4. **Potential optimization**: If the tool-call limit were raised or the throttle message included a summary of already-retrieved data, Run 5 could likely have completed in ~8 rounds at ~1/4 the cost.

### Run 5 Deep Analysis (vs. CID-15518-analysis-guide.md)

The analysis guide defines the correct assessment approach and expected answer. Run 5 is the **only run that passed** all criteria.

#### Guide Criteria vs. Run 5 Reasoning

| Guide Question | Expected Answer | Run 5 Answer | Pass? |
|----------------|-----------------|--------------|-------|
| **What constrains `layerCount`?** | Only `core_assert` (debug-only) — no runtime enforcement in release | *"core_assert is debug-only and compiled out in release builds... layerCount has no runtime enforcement in release"* | ✅ |
| **Is the loop guard sufficient?** | NO — `while (layerIndex < layerCount)` fails if `layerCount > 256` | *"The while condition does NOT prevent layerIndex from reaching num_bits if layerCount itself exceeds 256"* | ✅ |
| **What are the actual bounds?** | `layerMask.num_bits = 256`, array size = 256 (indices 0-255) | Traced full chain: `ST_MAX_LAYERS_PER_SURFACE_OMPV_NON_UTS = 256` → `num_bits = T_SIZE = 256` | ✅ |
| **What does `find_first_bit_from` return when exhausted?** | Returns `num_bits` (256) — the sentinel value | *"find_first_bit/find_first_bit_from return either a valid bit index in [0, num_bits-1] or the sentinel value num_bits (256)"* — confirmed via `find_first_bit_from_block` source (line 611: `return num_bits;`) | ✅ |
| **Don't rely on assertions** | `core_assert` is disabled in release | Retrieved `core_assert` macro definition, confirmed it's a debug assert | ✅ |

#### Guide "Common Mistakes" Check

| Mistake | Runs 1-4 | Run 5 |
|---------|----------|-------|
| ❌ Assuming loop guard prevents all overruns without validating upper bound | All 4 made this mistake | ✅ Avoided — explicitly identified `layerCount` as unbounded |
| ❌ Relying on assertions (disabled in release) | Runs 1-2 cited `core_assert` as protection; Runs 3-4 still implicitly relied on it | ✅ Avoided — retrieved macro, confirmed debug-only |
| ❌ Assuming `layerCount ≤ 256` without investigating constraint source | All 4 assumed this | ✅ Avoided — traced constraint chain, found no runtime enforcement |

#### Evidence Chain Assembled by Run 5

The model built the following complete evidence chain (despite the redundant tool calls):

1. **Array size**: `StLayerMaskOMPVRaw.data[ST_NUM_UINTS_FOR_LAYER_MASK]` → `ST_NUM_UINTS_FOR_LAYER_MASK = ST_MAX_LAYERS_PER_SURFACE_OMPV / 32` → `ST_MAX_LAYERS_PER_SURFACE_OMPV = ST_MAX_LAYERS_PER_SURFACE_OMPV_NON_UTS` → **256**
2. **Sentinel value**: `find_first_bit()` → `find_first_bit_from_block(0)` → loops through blocks → `return num_bits;` when not found → **256**
3. **Bitset definition**: `ntl::bitset<T_SIZE>` → `enum { num_bits = T_SIZE }` → confirms **num_bits = 256**
4. **Assert is debug-only**: `core_assert(expr)` → `core_assert_macro(AssertType::Assert, ...)` → debug assert, **compiled out in release**
5. **Vulnerability path**: caller passes `layerCount > 256` → assert is inactive → `find_first_bit_from` returns sentinel 256 → `256 < layerCount` passes loop guard → `callback(256)` → **out-of-bounds on array[256]**

#### Why Runs 1-4 Failed

All four earlier runs made the same logical error the guide specifically warns about:

> *"❌ Assuming loop guard prevents all overruns without validating upper bound"*

They each reasoned: *"layerIndex < layerCount, and layerCount ≤ num_bits (by assert), therefore layerIndex < 256, therefore safe."* This syllogism is valid **only if the assert actually runs in production** — which it doesn't. The enhanced v4 prompt forced Run 5 to verify each step of the constraint chain rather than accept it at face value.

#### Conclusion

Run 5 demonstrates that **prompt engineering is the primary lever for analysis quality** on this class of vulnerability. The same model (gpt-5.1-codex) failed 3 consecutive times with weaker prompts. The v4 prompt's specific bounds-tracing questions (e.g., *"What is the EXACT size?"*, *"What is the relationship between array size and upper bound constraint?"*) forced the model to verify rather than assume — exactly the methodology the analysis guide prescribes.

---

#### Run 6 — gpt-5.1-codex, v5 prompts (current system prompts, 2026-03-19) ❌
- **File**: `9_final.json` (741 lines, ~37 KB)
- **Exact tokens**: prompt=18,832, completion=5,526, total=24,358
- **Cost**: $0.0683 (from litellm)
- **Duration**: 69.4s
- **Decision**: 1007 (FP) — **INCORRECT** (should be 1337 TP)

##### Tool Call Breakdown

| # | Tool | Args | Result | Needed? |
|---|------|------|--------|---------|
| 1 | `get_class` | `StLayerMaskOMPV` | Got `StLayerMaskOMPVRaw` with `data[ST_NUM_UINTS_FOR_LAYER_MASK]` | Yes — first attempt at structure |
| 2 | `get_global_var` | `StLayerMaskOMPV` | Not found | Reasonable follow-up to failed class lookup |
| 3 | `get_macro` | `ST_MAX_LAYERS` | Not found (inline constexpr, not a macro) | Reasonable — trying to trace array size |
| 4 | `get_macro` | `ST_NUM_UINTS_FOR_LAYER_MASK` | Not found (same reason) | Reasonable — second attempt |
| 5 | `get_function_code` | `StLayerMaskOMPV::find_first_bit` | Got wrapper: `return find_first_bit_from_block<FIND_ON>(0)` | Yes — needed for sentinel behavior |
| 6 | `get_class` | `ntl::bitset` | Got full 656-line bitset class including `num_bits = T_SIZE`, `find_first_bit_from_block`, `operator[]`, etc. | Yes — critical for understanding bounds |

**No redundant tool calls.** 6 unique calls, 0 throttle warnings. This is the most efficient run.

##### What the LLM Knew vs. What It Concluded

**Had access to (from Round 7, bitset class)**:
- `num_bits = T_SIZE` enum — the sentinel value
- `find_first_bit_from_block()` returning `num_bits` when exhausted (line 611)
- `operator[]` with `NTL_ASSERT(pos < num_bits)` — debug-only bounds check
- Full `reference` inner class

**Did NOT obtain**:
- The actual value of `T_SIZE` / `num_bits` (never traced the constant chain `ST_MAX_LAYERS_PER_SURFACE_OMPV_NON_UTS = 256`)
- The `core_assert` macro definition (to verify it's debug-only)
- Caller context showing how `layerCount` is set

**LLM's final reasoning**: *"layerIndex is always checked by `while (layerIndex < layerCount)` before callback is invoked, so the callback can never see a value equal to or greater than `layerCount` (256). When `find_first_bit` returns `num_bits` (e.g., 256), the loop condition fails and the callback is not called."*

##### Failure Analysis

The model made the **same fundamental error as Runs 1-4**: it assumed the loop guard is sufficient without verifying that `layerCount` is itself bounded.

| Guide "Common Mistake" | Run 6 Committed It? |
|-------------------------|---------------------|
| Assuming loop guard prevents all overruns without validating upper bound | **YES** — concluded loop guard is sufficient |
| Relying on assertions (disabled in release builds) | **Partially** — didn't retrieve `core_assert` definition, but implicitly trusted it by not questioning `layerCount` bounds |
| Assuming `layerCount ≤ 256` without investigating constraint source | **YES** — stated `layerCount` is 256 without verifying |

**The critical irony**: The model *retrieved the full bitset class* including `find_first_bit_from_block` which returns `num_bits` as a sentinel. It correctly identified that `find_first_bit` returns `num_bits` (256) when exhausted. But it then assumed `layerCount` would be ≤ 256, so `256 < layerCount` would be false. It never asked: **what if `layerCount > 256`?**

**Missing tool calls that could have changed the outcome**:
- `get_macro("core_assert")` → would have revealed it's debug-only
- `get_global_var("ST_MAX_LAYERS_PER_SURFACE_OMPV_NON_UTS")` → would have revealed the 256 constant, prompting comparison with `layerCount`
- `get_caller_function` or caller context → would have shown how `layerCount` is passed

##### Comparison with Run 5

| Aspect | Run 5 (v4 prompts) ✅ | Run 6 (v5 prompts) ❌ |
|--------|----------------------|----------------------|
| Rounds | 28 | 7 |
| Tool calls | 27 (20 redundant) | 6 (0 redundant) |
| Tokens | 228,991 | 24,358 |
| Cost | ~$0.77 | $0.0683 |
| Traced constant chain | Yes (found 256) | No |
| Verified core_assert is debug-only | Yes | No |
| Investigated sentinel + layerCount interaction | Yes | No |
| Correct answer | Yes (1337 TP) | No (1007 FP) |

**Key insight**: Run 6 was **10x cheaper and 10x faster** than Run 5, but got the wrong answer. The v5 prompts lack the detailed bounds-tracing hint questions that forced Run 5 to verify assumptions. **Efficiency without accuracy is worthless for security analysis.**

##### Suggested Improvements

1. **Restore bounds-tracing hints** from v4 prompts — the questions like *"What is the EXACT size of the array?"* and *"What is the relationship between the array size and the upper bound constraint?"* are what drove Run 5 to the correct answer
2. **Add a "verify your assumptions" step** in the prompt — the model should be required to list assumptions and verify each one before concluding
3. **Prompt should explicitly warn**: *"If the static analyzer says a value evaluates to X, investigate how that value X can be reached, don't just dismiss it"*
4. **The tool-call efficiency was excellent** — the problem is entirely in the reasoning, not the tool strategy

---

### Runs 7–20 — Skipped (All FP, Same Failure Mode)

Runs 7–20 (file IDs 10–23) tested incremental prompt variations (v5 through v8) — adding evidence-based language, contradiction-investigation bullets, assumption-validation requirements, and various phrasings of "don't rely on assertions." **All concluded FP** with the same fundamental error as Run 6: the model assumed `layerCount ≤ 256` without verifying the constraint source. None are documented individually because:

1. **Same failure mode** — every run trusted the loop guard `while (layerIndex < layerCount)` without questioning whether `layerCount` itself is bounded at runtime. No new diagnostic insight beyond what Run 6 already demonstrated.
2. **No novel tool behavior** — tool call patterns were minor variations on Run 6's approach (class lookup → global var → function code → bitset class). No run discovered a new investigation path.
3. **The breakthrough required a qualitative change** — incremental prompt wording adjustments couldn't overcome the core problem. What ultimately worked was changing the *framing* of assertions from "disabled in release builds" (which the model interpreted as conditional) to "are NO-OPs" (which it treated as absolute). That change happened between Run 20 and Run 21.

---

#### Run 21 (ID 24) — gpt-5.1-codex, v9 prompts (context field + "disabled in release builds") ❌
- **File**: `24_final.json`
- **Tokens**: ~45,000 (est.)
- **Cost**: ~$0.15
- **Rounds**: 12 | **Tool calls**: 11 | **Throttle warnings**: 1
- **Decision**: 1007 (FP) — **INCORRECT**

##### Key Changes in This Prompt Version (v9)
- Added `context` field to all 5 tool definitions in `tools.yaml`, requiring the model to state its reasoning before each tool call
- Assertion language still said "disabled in release builds"

##### Tool Calls

| # | Tool | Args | Notes |
|---|------|------|-------|
| 1 | `get_class` | `StLayerMaskOMPV` | Standard opener |
| 2 | `get_global_var` | `StLayerMaskOMPV` | Typedef not found as global |
| 3 | `get_function_code` | `StLayerMaskOMPV::find_first_bit` | Got wrapper |
| 4 | `get_function_code` | `StLayerMaskOMPV::find_first_bit_from` | Good — traced return semantics |
| 5 | `get_macro` | `ST_NUM_UINTS_FOR_LAYER_MASK` | Not found (inline constexpr) |
| 6 | `get_class` | `StLayerMaskOMPVRaw` | Got same data |
| 7 | `get_macro` | `ST_NUM_UINTS_FOR_LAYER_MASK` | **Duplicate** of #5 |
| 8 | `get_function_code` | `StLayerMaskOMPV::find_first_bit_from_block` | Confirmed sentinel = `num_bits` |
| 9 | `get_macro` | `ST_MAX_LAYERS` | Not found |
| 10 | `get_function_code` | `R_ST_IterateLayerMask` | Re-fetched function under analysis |
| **11** | **`get_macro`** | **`core_assert`** | **← THE SMOKING GUN** |

##### Why This Run Matters

**Tool call #11 is the critical evidence.** The model called `get_macro("core_assert")` with context: *"Need to know if core_assert is active in release; can't rely for guard."*

This reveals the problem with "disabled in release builds" — the model interpreted it as: *"I should check whether this IS a release build, and whether core_assert IS active."* It treated the prompt instruction as a conditional fact to verify rather than an absolute rule to follow. It spent its 11th (and last allowed) tool call investigating whether the assertion is active, then hit the tool limit. The forced final answer still concluded FP because the model assumed `layerCount ≤ 256` — the `core_assert` lookup was too late and on the wrong question.

**This run directly motivated the NO-OPs language change**: switching from *"assertions are disabled in release builds"* to *"assertions are NO-OPs. Do not look them up; do not check if they are active. Treat every assertion as if it does not exist."*

##### Final Reasoning (incorrect)
> *"The loop guard `while (layerIndex < layerCount)` is evaluated before every callback invocation, so the callback only ever receives values in the half-open range `[0, layerCount)`; if `layerCount` were 256, the maximum `layerIndex` passed is 255."*

Same error as all prior FP runs — assumed `layerCount ≤ 256` without verifying.

---

#### Run 22 (ID 25) — gpt-5.1-codex, v10 prompts (NO-OPs + transitive rule) ⚠️ TIMEOUT
- **File**: `25_final.json`
- **Rounds**: 12 | **Tool calls**: 11
- **Decision**: CRASH — LiteLLM timeout at 120s during final answer generation with 32 messages

**Why it's skipped**: Infrastructure failure, not a prompt problem. The model was trending toward TP (zero `core_assert` lookups, investigating the right constants). Fixed by increasing `timeout` from 120s to 300s in `llm_analyzer.py`.

---

#### Run 23 (ID 26) — gpt-5.1-codex, v10 prompts (NO-OPs + transitive + 300s timeout) ✅
- **File**: `26_final.json`
- **Tokens**: ~23,000 (est.)
- **Cost**: ~$0.09
- **Duration**: 143s
- **Rounds**: 7 | **Tool calls**: 6 | **Throttle warnings**: 0
- **Decision**: 1337 (TP) — **CORRECT**

##### Key Changes in This Prompt Version (v10)
- Assertion language changed to: *"assertions are NO-OPs. Do not look them up; do not check if they are active. Treat every assertion as if it does not exist."*
- Added transitive rule: *"if a guard like `x < limit` looks safe but `limit` is only bounded by an assertion, then `limit` is unbounded and the guard itself is broken."*
- Timeout increased from 120s to 300s

##### Tool Calls

| # | Tool | Args | Notes |
|---|------|------|-------|
| 1 | `get_class` | `StLayerMaskOMPV` | Standard opener |
| 2 | `get_global_var` | `StLayerMaskOMPV` | Typedef not found |
| 3 | `get_function_code` | `StLayerMaskOMPV::find_first_bit` | Got wrapper |
| 4 | `get_function_code` | `StLayerMaskOMPV::find_first_bit_from` | Traced return semantics |
| 5 | `get_function_code` | `StLayerMaskOMPV::find_first_bit_from_block` | Confirmed sentinel = `num_bits` (line 611) |
| 6 | `get_macro` | `ST_NUM_UINTS_FOR_LAYER_MASK` | Not found (inline constexpr) |

**Zero `core_assert` lookups.** The NO-OPs language worked exactly as intended — the model never tried to investigate whether assertions are active.

##### Why This Run Succeeded

The model applied the transitive rule correctly:
1. Saw `core_assert(layerCount <= layerMask.num_bits)` on line 216
2. Immediately treated it as non-existent (NO-OPs rule)
3. Concluded: `layerCount` has no runtime bound → guard `layerIndex < layerCount` is broken when `layerCount > num_bits`
4. Combined with sentinel: `find_first_bit_from` returns `num_bits` (256) when exhausted → `256 < 257` passes → `callback(256)` → overrun

##### Final Reasoning (correct)
> *"Because assertions are no-ops, `layerCount` can exceed `layerMask.num_bits` at runtime. When the mask contains no bits, `layerIndex` becomes the sentinel `layerMask.num_bits` (e.g., 256). With `layerCount = 257`, the guard evaluates `256 < 257` → true, so `callback(256)` executes even though the valid layer indices are 0–255, overrunning any 256-entry array."*

##### Comparison: Run 23 vs Run 5 (both TP)

| Aspect | Run 5 (v4 — bounds hints) ✅ | Run 23 (v10 — NO-OPs) ✅ |
|--------|------------------------------|--------------------------|
| Rounds | 28 | 7 |
| Tool calls | 27 (20 redundant) | 6 (0 redundant) |
| Tokens | 228,991 | ~23,000 |
| Cost | ~$0.77 | ~$0.09 |
| core_assert lookups | 1 (to verify debug-only) | 0 (treated as non-existent) |
| Correct answer | Yes | Yes |
| How it got there | Brute-force verification | Transitive reasoning from NO-OPs rule |

**Run 23 is ~10x cheaper than Run 5 and gets the same correct answer.** The NO-OPs + transitive rule achieved what detailed bounds-tracing hints achieved, but through reasoning guidance rather than investigation mandates.

---

#### Run 24 (ID 27) — gpt-5.1-codex, v11 prompts (trimmed — 3 bullets) ✅
- **File**: `27_final.json`
- **Exact tokens**: prompt=30,322, completion=15,685, total=46,007
- **Cost**: $0.17
- **Duration**: 199s
- **Rounds**: 11 | **Tool calls**: 10 | **Throttle warnings**: 0
- **Decision**: 1337 (TP) — **CORRECT**

##### Key Changes in This Prompt Version (v11)
- Trimmed Answer Guidelines section 3 from 6 bullets to 3 (removed assertion-laundering, verify-both-operands, and concrete-values-of-guards bullets — now redundant with the NO-OPs + transitive rule)
- Prompt tokens decreased from 1911 → 1710 (saved 201 tokens per round)
- Saved pre-trim backup as `system_messages.v10-working.yaml`

##### Tool Calls

| # | Tool | Args | Notes |
|---|------|------|-------|
| 1 | `get_class` | `StLayerMaskOMPV` | Standard opener |
| 2 | `get_global_var` | `StLayerMaskOMPV` | Typedef not found |
| 3 | `get_function_code` | `StLayerMaskOMPV::find_first_bit` | Got wrapper |
| 4 | `get_function_code` | `StLayerMaskOMPV::find_first_bit_from` | Traced return semantics |
| 5 | `get_function_code` | `ntl::bitset::find_first_bit_from_block` | Confirmed sentinel |
| 6 | `get_macro` | `ST_NUM_UINTS_FOR_LAYER_MASK` | Not found |
| 7 | `get_global_var` | `ST_NUM_UINTS_FOR_LAYER_MASK` | Found constant chain |
| 8 | `get_global_var` | `ST_MAX_LAYERS_PER_SURFACE_OMPV` | Chain link |
| 9 | `get_global_var` | `ST_MAX_LAYERS_PER_SURFACE_OMPV_NON_UTS` | **= 256** |
| 10 | `get_function_code` | `R_ST_IterateLayerMask` | Re-fetched (hit tool limit) |

**Zero `core_assert` lookups** — NO-OPs language still effective in trimmed prompt.

##### Observations

The trimmed prompt still produces the correct TP answer, but at **2x the cost of Run 23** ($0.17 vs $0.09). The model spent Rounds 6–10 chasing the constant chain (`ST_NUM_UINTS_FOR_LAYER_MASK` → `ST_MAX_LAYERS_PER_SURFACE_OMPV` → `ST_MAX_LAYERS_PER_SURFACE_OMPV_NON_UTS` → 256), which Run 23 did not need because it stopped after 6 calls and reasoned transitively without needing the concrete value.

This raises an interesting question: **does cutting the verbose bullets force the model to do more tool-call investigation to compensate for less guidance?** Run 23's v10 prompt had 6 bullets including "verify BOTH operands" and "concrete values of guards" — which may have actually *shortened* the analysis by steering the model toward the transitive reasoning path sooner, rather than sending it down the constant-tracing rabbit hole.

##### Final Reasoning (correct)
> *"Because `core_assert(layerCount <= layerMask.num_bits)` is a no-op in release builds, there is no effective runtime guard tying `layerCount` to the 256 valid mask entries. When the mask is empty, `find_first_bit_from()` returns the constant `layerMask.num_bits = 256`. If `layerCount` is set to 257, the guard `while (layerIndex < layerCount)` evaluates `256 < 257` → passes → `callback(256)` → out-of-bounds."*

---

#### Run 25 (ID 28) — gpt-5.1-codex, v11 prompts (trimmed — confirmation run) ✅
- **File**: `28_final.json`
- **Exact tokens**: prompt=98,771, completion=12,747, total=111,518
- **Cost**: $0.19
- **Duration**: 176s
- **Rounds**: 14 | **Tool calls**: 13 (10 real + 3 rejected post-limit) | **Throttle warnings**: 4
- **Decision**: 1337 (TP) — **CORRECT**

##### Tool Calls

| # | Tool | Args | Needed? | Notes |
|---|------|------|---------|-------|
| 1 | `get_class` | `StLayerMaskOMPV` | Yes | Standard opener |
| 2 | `get_global_var` | `StLayerMaskOMPV` | Marginal | Typedef not found |
| 3 | `get_class` | `StLayerMaskOMPVRaw::find_first_bit` | Wasted | Class lookup for a function — wrong tool |
| 4 | `get_function_code` | `StLayerMaskOMPVRaw::find_first_bit` | Yes | Got wrapper |
| 5 | `get_class` | `ntl::bitset` | Yes | Got full 656-line bitset class |
| 6 | `get_macro` | `ST_LAYER` | Wasted | Partial name, not found |
| 7 | `get_class` | `StLayerMaskOMPVRaw` | Wasted | Already had this from #1 |
| 8 | `get_macro` | `ST_NUM_UINTS_FOR_LAYER_MASK` | Wasted | Not found (inline constexpr) |
| 9 | `get_macro` | `ST_NUM_LAYER_MASK_BITS` | Wasted | Not found (doesn't exist) |
| 10 | `get_class` | `StLayerMask` | Wasted | Hit tool limit |
| 11 | `get_function_code` | `R_ST_IterateLayerMask` | Rejected | Post-limit |
| 12 | `get_macro` | `ST_MAX_LAYERS` | Rejected | Post-limit |
| 13 | `get_global_var` | `StLayerMaskOMPV` | Rejected | Post-limit, duplicate of #2 |

**Zero `core_assert` lookups** — NO-OPs language still effective.

##### Observations

This run confirms v11 produces TP but exposes a **consistency problem**: the model's tool strategy varies significantly between runs. Compare:

| Aspect | Run 24 (v11, 1st) | Run 25 (v11, 2nd) |
|--------|-------------------|-------------------|
| Rounds | 11 | 14 |
| Tool calls | 10 | 13 (10+3 rejected) |
| Tokens | 46,007 | 111,518 |
| Cost | $0.17 | $0.19 |
| Found constant chain via `get_global_var`? | Yes (calls 7-9) | No — never tried `get_global_var` for constants |
| Wasted macro lookups | 1 | 4 |
| Post-limit tool requests | 0 | 3 |

Run 25 burned 4 rounds (11-14) requesting tools after the limit, each resending the full conversation — inflating prompt tokens from ~30K to ~99K. It also never pivoted from `get_macro` to `get_global_var` for the inline constexpr constants, unlike Run 24 which made that pivot at call #7.

Despite the inefficiency, the model still reached the correct conclusion through the transitive reasoning path: assertion is a no-op → `layerCount` unbounded → sentinel 256 passes guard → overrun.

##### v11 Trim Verdict After 2 Runs

Both v11 runs got TP, but both were significantly less efficient than Run 23's single v10 run:

| | Run 23 (v10) | Run 24 (v11) | Run 25 (v11) |
|---|---|---|---|
| Rounds | 7 | 11 | 14 |
| Tools | 6 | 10 | 13 |
| Tokens | ~23,000 | 46,007 | 111,518 |
| Cost | ~$0.09 | $0.17 | $0.19 |

**Run 26 disproved this theory** — see below. Run 23's efficiency was simply lucky variance, not prompt-driven.

##### Final Reasoning (correct)
> *"If the caller supplies `layerCount > layerMask.num_bits` (the only 'guard' is `core_assert`, which is a no-op) and the mask has no set bits, then `find_first_bit_from()` returns `layerMask.num_bits` (e.g., 256). The loop guard `while (layerIndex < layerCount)` is true, so `callback(layerIndex)` is invoked with an out-of-range index (256), overrunning any 256-sized target array."*

---

#### Run 26 (ID 29) — gpt-5.1-codex, v10 prompts (revert test) ✅
- **File**: `29_final.json`
- **Exact tokens**: prompt=40,212, completion=19,702, total=59,914
- **Cost**: $0.21
- **Duration**: 218s
- **Rounds**: 14 | **Tool calls**: 13 (10 real + 3 rejected) | **Throttle warnings**: 4
- **Decision**: 1337 (TP) — **CORRECT**
- **Purpose**: Revert to v10 to test if Run 23's efficiency was prompt-driven or lucky

##### Tool Calls

| # | Tool | Args | Notes |
|---|------|------|-------|
| 1 | `get_class` | `StLayerMaskOMPV` | Standard opener |
| 2 | `get_global_var` | `StLayerMaskOMPV` | Not found |
| 3 | `get_class` | `StLayerMaskOMPVRaw` | Got struct |
| 4 | `get_macro` | `ST_NUM_UINTS_FOR_LAYER_MASK` | Not found (inline constexpr) |
| 5 | `get_class` | `StLayerMask` | Not found |
| 6 | `get_macro` | `ST_MAX_LAYERS` | Not found (partial name) |
| 7 | `get_global_var` | `ST_NUM_UINTS_FOR_LAYER_MASK` | Got value |
| 8 | `get_global_var` | `ST_MAX_LAYERS_PER_SURFACE_OMPV` | Got chain |
| 9 | `get_global_var` | `ST_MAX_LAYERS_PER_SURFACE_OMPV_NON_UTS` | **= 256** |
| 10 | `get_function_code` | `StLayerMaskOMPV::find_first_bit_from` | Hit limit — never executed |
| 11 | `get_function_code` | `ntl::bitset::find_first_bit` | Rejected post-limit |
| 12 | `get_function_code` | `ntl::bitset::find_first_bit_from_block` | Rejected post-limit |
| 13 | `get_function_code` | `R_ST_IterateLayerMask` | Rejected post-limit |

**Zero `core_assert` lookups** — NO-OPs language still effective.

##### Key Observation: Run 23 Was Lucky

Run 26 used the **identical v10 prompt** as Run 23 but produced completely different efficiency:

| Aspect | Run 23 (v10, original) | Run 26 (v10, revert) |
|--------|------------------------|----------------------|
| Rounds | 7 | 14 |
| Tool calls | 6 | 13 (10+3 rejected) |
| Tokens | ~23,000 | 59,914 |
| Cost | ~$0.09 | $0.21 |
| Wasted macro lookups | 0 | 2 |
| Post-limit tool requests | 0 | 3 |
| Found sentinel via `find_first_bit_from`? | Yes (call #4) | No — hit tool limit before executing call #10 |

Same prompt, same CID, same model — **2.5x cost difference**. This proves Run 23's efficiency was stochastic variance in the model's tool selection strategy, not a property of v10's extra bullets.

##### Updated Verdict: v10 vs v11

| | Run 23 (v10) | Run 26 (v10) | Run 24 (v11) | Run 25 (v11) |
|---|---|---|---|---|
| Rounds | 7 | 14 | 11 | 14 |
| Tools | 6 | 13 | 10 | 13 |
| Tokens | ~23,000 | 59,914 | 46,007 | 111,518 |
| Cost | ~$0.09 | $0.21 | $0.17 | $0.19 |

**Conclusion**: The extra 3 bullets in v10 do not reliably produce more efficient runs. Run 23 was an outlier. **Use v11 (trimmed)** — fewer prompt tokens per round, same TP accuracy, and the efficiency difference is model variance, not prompt variance.

**Update**: Run 27 (v12) achieved $0.04 / 5 rounds / 4 tools — best ever. See Run 27 detail below.

##### Final Reasoning (correct)
> *"Because `core_assert(layerCount <= layerMask.num_bits)` is a no-op in release builds, there is no effective runtime guard tying `layerCount` to the 256 valid mask entries. When the mask is empty, `find_first_bit_from()` returns the constant `layerMask.num_bits = 256`. If `layerCount` is set to 257, the guard `while (layerIndex < layerCount)` evaluates `256 < 257` → passes → `callback(256)` → out-of-bounds."*

---

#### Run 27 (ID 30) — gpt-5.1-codex, v12 prompts (user cuts) ✅ ⭐ BEST RUN
- **File**: `30_final.json`
- **Exact tokens**: prompt=11,366, completion=3,628, total=14,994
- **Cost**: $0.04
- **Duration**: 58s
- **Rounds**: 5 | **Tool calls**: 4 | **Throttle warnings**: 0
- **Decision**: 1337 (TP) — **CORRECT**
- **Prompt tokens per round**: 1,784 (down from 1,911 in v10, 1,710 in v11)
- **Purpose**: Test user's further-trimmed prompt (v12)

##### Tool Calls

| # | Tool | Args | Notes |
|---|------|------|-------|
| 1 | `get_class` | `StLayerMaskOMPV` | Standard opener — got StLayerMaskOMPVRaw |
| 2 | `get_function_code` | `StLayerMaskOMPV::find_first_bit` | Got wrapper |
| 3 | `get_function_code` | `StLayerMaskOMPV::find_first_bit_from` | Got delegation + sentinel return |
| 4 | `get_function_code` | `StLayerMaskOMPV::find_first_bit_from_block` | Confirmed `return num_bits` sentinel |

**4/4 productive calls. Zero wasted. Zero post-limit rejections. Zero `core_assert` lookups.**

The model went straight for the sentinel chain: class → find_first_bit → find_first_bit_from → find_first_bit_from_block. Never bothered chasing constants — it inferred `num_bits = 256` from the bitset template parameter and the static analyzer's description.

##### Comparison: All TP Runs

| | Run 5 (v4) | Run 23 (v10) | Run 24 (v11) | Run 25 (v11) | Run 26 (v10) | **Run 27 (v12)** |
|---|---|---|---|---|---|---|
| Rounds | 28 | 7 | 11 | 14 | 14 | **5** |
| Tools | 27 | 6 | 10 | 13 | 13 | **4** |
| Tokens | 228,991 | ~23,000 | 46,007 | 111,518 | 59,914 | **14,994** |
| Cost | ~$0.77 | ~$0.09 | $0.17 | $0.19 | $0.21 | **$0.04** |
| Wasted calls | 20 | 0 | 1 | 4 | 2 | **0** |
| Strategy | Brute force | Lucky efficient | Constant chase | Post-limit loop | Constant chase | **Direct sentinel chain** |

##### What Changed in v12

User trimmed the prompt further from v11. Key difference: removed extraneous guidelines while keeping the core NO-OPs and transitive rules.

**Caveat**: This could be lucky variance like Run 23. Needs confirmation runs.

##### Final Reasoning (correct)
> *"The only guard is `core_assert(layerCount <= layerMask.num_bits)`, which is a no-op at runtime, so `layerCount` can exceed `layerMask.num_bits`. When no more bits are set, `layerIndex` becomes the sentinel `layerMask.num_bits` (e.g., 256) and the loop condition `layerIndex < layerCount` still holds (e.g., `256 < 512`), causing `callback(256)`. This overruns callbacks that index 0–255 arrays."*

---

#### Run 28 (ID 31) — gpt-5.1-codex, v13 prompts (+ verify claims rule) ✅ ⚠️ WORST TP RUN
- **File**: `31_final.json`
- **Exact tokens**: prompt=48,800, completion=21,490, total=70,290
- **Cost**: $0.25
- **Duration**: 369s
- **Rounds**: 16 | **Tool calls**: 15 (10 real + 5 rejected) | **Throttle warnings**: 6
- **Decision**: 1337 (TP) — **CORRECT**
- **Prompt tokens per round**: 1,828 (up from 1,784 in v12 — 18 tokens added by "verify claims" rule)
- **Purpose**: Test adding "verify the analyzer's key claims" to main instructions

##### Tool Calls

| # | Tool | Args | Needed? | Notes |
|---|------|------|---------|-------|
| 1 | `get_class` | `StLayerMaskOMPV` | Yes | Standard opener — got StLayerMaskOMPVRaw |
| 2 | `get_global_var` | `StLayerMaskOMPV` | Marginal | Not found |
| 3 | `get_class` | `StLayerMask` | Wasted | Not found |
| 4 | `get_global_var` | `ST_NUM_UINTS_FOR_LAYER_MASK` | Yes | Got constant chain |
| 5 | `get_global_var` | `ST_MAX_LAYERS_PER_SURFACE_OMPV` | Yes | Chain continuing |
| 6 | `get_global_var` | `ST_MAX_LAYERS_PER_SURFACE_OMPV_NON_UTS` | Yes | **= 256** ✔️ Verifying analyzer's claim |
| 7 | `get_function_code` | `StLayerMask::find_first_bit` | Yes | Got wrapper |
| 8 | `get_function_code` | `ntl::bitset::find_first_bit_from_block` | Yes | Confirmed sentinel `return num_bits` |
| 9 | `get_function_code` | `ntl::bitset::has_fringe_bits` | Marginal | Exploring edge case in bitset |
| 10 | `get_global_var` | `r_st_db::StLayerMaskOMPV` | Wasted | Hit limit — still chasing typedef |
| 11 | `get_function_code` | `ntl::bitset::find_first_bit_from` | Rejected | Post-limit |
| 12 | `get_class` | `StLayerMaskOMPVRaw` | Rejected | Post-limit, already had from #1 |
| 13 | `get_global_var` | `StLayerMaskOMPVRaw` | Rejected | Post-limit |
| 14 | `get_macro` | `StLayerMaskOMPV` | Rejected | Post-limit |
| 15 | `get_function_code` | `ntl::bitset::get_index` | Rejected | Post-limit |

**Zero `core_assert` lookups** — NO-OPs language still effective.

**Did it verify the analyzer's claims?** Partially:
- ✔️ Verified `num_bits = 256` via constant chain (calls 4–6) — **the new rule worked**
- ✔️ Verified sentinel return `num_bits` from `find_first_bit_from_block` (call 8)
- ✖️ Never verified what the callback actually indexes
- ✖️ Never found callers

**What went wrong**: The model dutifully obeyed the "verify key claims" rule but got stuck trying to resolve the `StLayerMaskOMPV` typedef — it spent calls 2, 3, 10, 12–14 trying different approaches to find the typedef, never succeeding. This typedef obsession consumed 6 of 15 calls. The constant chain (calls 4–6) was productive verification, but the model didn't know when to stop chasing the typedef.

##### Impact of "Verify Claims" Rule

| | Run 27 (v12, no rule) | Run 28 (v13, with rule) |
|---|---|---|
| Rounds | 5 | 16 |
| Tools | 4 | 15 (10+5 rejected) |
| Tokens | 14,994 | 70,290 |
| Cost | $0.04 | $0.25 |
| Verified 256? | No — trusted analyzer | Yes — constant chain |
| Verified sentinel? | Yes (3 calls) | Yes (1 call) |
| Wasted on typedef | 0 | 6 calls |

**Verdict**: The "verify key claims" rule successfully forced constant verification but also triggered an obsessive typedef chase. The rule needs refinement or removal — it made the run **6x more expensive** than v12. The model was already verifying the mechanism (sentinel chain) in v12; the extra cost came from verifying the *value* (256) which the analyzer had already reported accurately.

**Recommendation**: Remove the "verify claims" rule from main instructions. The existing EVIDENCE-BASED ANALYSIS and ASSUMPTION VALIDATION rules are sufficient. The "verify claims" rule is too vague and causes the model to over-investigate known values.

##### Final Reasoning (correct)
> *"Supplying `layerCount > 256` with an empty layer mask makes `callback(256)` run, overrunning its 256-element storage."*