# CID 27528 — Lead 1 Deep Dive

## 2026-03-26 — TypeAliasLookup validation (v2 replay, no typedef impact)

### Issue Context
- **Coverity event:** `overrun-local` — Overrunning array `reg_lmap` of 17 bytes at byte offset 63 using index `dst` (which evaluates to 63)
- **File:** `sljitNativeX86_common.c`, line 2642
- **Function:** `sljit_emit_op_flags`
- **Core question:** Can `dst` index exceed the 17-element `reg_lmap` array?

### Lead Assignment
- **Question:** What is the declaration (type and element count) of `reg_lmap` that is indexed at lines 2639, 2640, 2642, 2655, and 2660?
- **Why it matters:** The Coverity warning claims `dst` evaluates to 63, which would be byte offset 63 — far beyond the 17-byte array. Understanding the array size and index constraints is foundational.
- **Seed tool:** `get_global_var(reg_lmap)`

### Run Metrics

| Metric | v1 (original) | v2 (with TypeAliasLookup) | Delta |
|--------|---------------|---------------------------|-------|
| Tool calls | 9 | 9 | 0% |
| Rounds | 9 | 9 | 0% |
| Prompt tokens | 47,914 | 54,039 | +13% |
| Completion tokens | 27,507 | 20,355 | -26% |
| Total tokens | 75,421 | 74,394 | -1% |
| Estimated cost | $0.317 | $0.253 | -20% |
| Duration | 549s | 249s | -55% |
| Answered | true | true | same |
| Confidence | high | **medium** | downgrade |

### Tool Call Sequence (v2)

| # | Tool | Argument | Found | LOC | Assessment |
|---|------|----------|-------|-----|------------|
| 1 | get_global_var | `reg_lmap` | Yes | 4 | **Essential** — gets the array declaration |
| 2 | get_macro_or_global | `FAST_IS_REG` | Yes | 2 | **Essential** — key bounds-checking macro |
| 3 | get_macro_or_global | `REG_MASK` | Yes | 2 | **Essential** — register index mask |
| 4 | get_macro_or_global | `SLJIT_NUMBER_OF_REGISTERS` | Yes | 2 | **Essential** — array size driver |
| 5 | get_macro_or_global | `TMP_REG1` | Yes | 2 | **Essential** — fixed index into reg_lmap |
| 6 | get_macro_or_global | `SLJIT_R0` | Yes | 2 | **Reasonable** — establishes register index base |
| 7 | get_macro_or_global | `reg_map` | Yes | 4 | **Reasonable** — parallel array for context |
| 8 | get_function_code | `sljit_emit_op_flags` | Yes | 185 | **Essential** — full function to see all access patterns |
| 9 | get_function_code | `check_sljit_emit_op_flags` | No | 0 | **Reasonable** — checking for parameter validation |

**No wasteful calls.** This lead was never affected by the typedef gap — it uses `get_global_var` and `get_macro_or_global`, not `get_class`.

### What It Was Stuck On

This lead wasn't stuck in the traditional sense — it answered successfully both times. The high tool count (9) is driven by the **macro indirection chain**: `reg_lmap` → `SLJIT_NUMBER_OF_REGISTERS` → `FAST_IS_REG` → `REG_MASK` → `SLJIT_R0` → `TMP_REG1`. Each macro resolves to or depends on another, requiring sequential lookups.

The one missed opportunity: tool #9 (`check_sljit_emit_op_flags`) failed because the function doesn't exist in the DB. The model was looking for a validation function that would constrain `dst`, and correctly moved on when it wasn't found.

### Was the Conclusion Right?

**v2 finding:** `reg_lmap` is `static const sljit_u8 reg_lmap[SLJIT_NUMBER_OF_REGISTERS + 4]` with 17 entries (indices 0–16). `TMP_REG1 = SLJIT_NUMBER_OF_REGISTERS + 2 = 15`, so `reg_lmap[TMP_REG1]` is safe. However, `reg_lmap[dst]` and `reg_lmap[reg]` are only gated by `FAST_IS_REG`, which masks with `REG_MASK`.

**Assessment:** Factually correct. The model correctly identified the array size, the safe fixed indices, and the potentially problematic dynamic indices. The confidence downgrade from `high` to `medium` in v2 is reasonable — the model is more conservative about whether `FAST_IS_REG` guarantees bounds.

### Cross-Lead Summary

CID 27528 run_004 has 4 leads:

| Lead | Question | Tools | Result |
|------|----------|-------|--------|
| **1** | `reg_lmap` declaration and element count | 9 | answered, medium |
| 2 | `reg_map` declaration and element count | 1 | answered, high |
| 3 | `FAST_IS_REG` definition and constraints on `dst` | 2 | answered, high |
| 4 | `TMP_REG1` definition as index into `reg_map`/`reg_lmap` | 1 | answered, high |

Lead 1 is the heaviest (9 tools) because it explored the full macro chain. Leads 2–4 each got their answer in 1–2 calls. There's significant overlap: Lead 1 looked up `FAST_IS_REG`, `TMP_REG1`, and `reg_map` — the same entities that Leads 2–4 are dedicated to. The plan could have been tighter with 2 leads instead of 4.

### Lessons / Improvement Ideas

1. **No typedef impact.** This lead was unaffected by the TypeAliasLookup change. All tools used (`get_global_var`, `get_macro_or_global`, `get_function_code`) don't touch the class/typedef CSVs.
2. **Macro chains drive high tool counts legitimately.** When a C codebase uses deep `#define` chains (SLJIT-style), each macro must be resolved individually. 9 tools for 6 macros + 1 global + 1 function + 1 miss is reasonable — no tool batching available.
3. **Plan overlap with Leads 2–4.** Lead 1 independently discovered `FAST_IS_REG`, `REG_MASK`, `TMP_REG1`, and `reg_map` — the exact entities assigned to Leads 2–4. A smarter planner could have recognized that Lead 1's macro chain would naturally cover the other leads' territory.
4. **Duration improvement (549s → 249s) despite same tool count.** The 55% speed improvement is likely due to model inference variability or reduced completion tokens (-26%), not the TypeAliasLookup change.
