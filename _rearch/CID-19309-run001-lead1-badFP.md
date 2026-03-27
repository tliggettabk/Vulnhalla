# CID 19309 — run_001 Lead 1 — Bad FP Analysis

## Alert
Array overrun on `coord[vertIter - 1]` in `Glass_AreaX2AndScaledCentroidForEdgeLoop` at line 836.  
`vertIter = vertCount - 1` (unsigned), so if `vertCount` is 0, it wraps to 4294967295.

## Engine Verdict: 1007 (FP) — WRONG
## Human Verdict: TP (Reportable) — CORRECT
## Correct Verdict: 1337 (TP)

---

## What Lead 1 Investigated
**Question**: What enforces that vertCount is at least 2 before vertIter is set to vertCount - 1 at line 834?

The investigator traced the full call chain (11 rounds, 12 tool calls):
1. `Glass_AreaX2AndScaledCentroidForEdgeLoop` ← called from `Glass_SetupShard` (line 1196)
2. `Glass_SetupShard` ← iterates `shard->loops[]` populated by `Glass_ExtractCracksAndHolesFromLoop`
3. Examined `Glass_ExtractCracksAndHolesFromLoop` to determine how `loop->vertCount` is set

## Lead 1's Claim
> The upstream builder only records loops with at least three vertices. For holes, `priorIndex < borderCount - 2` (line 999) guarantees vertCount ≥ 3. For the outer loop, `borderCount >= 2` is asserted (line 1027) and `borderCount == 2` returns early (lines 1028-1041), so any loop reaching line 1067 has borderCount ≥ 3.

## Verification

### Hole path (lines 986–1021) — ✅ CORRECT

`loop->vertCount = borderCount - priorIndex` (line 1015).

Line 999 is `core_assert( priorIndex < borderCount - 2 )` — an assert (no-op in production). However, the claim holds **structurally**:
- `priorIndex` was stored as a prior `borderCount` value (set at line 981)
- The `if` at line 946 catches `priorIndex == borderCount - 2` and routes to a different branch
- So the hole branch (line 986) structurally requires `priorIndex < borderCount - 2`
- Therefore `borderCount - priorIndex ≥ 3` → `vertCount ≥ 3` ✅

### Outer loop path (lines 1027–1067) — ❌ INCORRECT

The code:
```
line 1027: core_assert( borderCount >= 2 );     ← NO-OP in production
line 1028: if ( borderCount == 2 ) { return; }  ← catches exactly 2
line 1067: loop->vertCount = borderCount;        ← reached when borderCount != 2
```

**There is no runtime code that prevents `borderCount` from being 0 or 1.**

- The assert at line 1027 is stripped in production
- The `if (borderCount == 2)` check only catches the value 2
- If `borderCount == 1`: falls through, `loop->vertCount = 1`, then caller does `vertIter = 0` → `coord[vertIter - 1]` = `coord[UINT_MAX]` → **overrun**

### Can borderCount == 1?

Yes. A single-edge circular list (`edge->next == edge`) enters the do-while at line 942, processes one edge, increments `borderCount` to 1, exits the loop, and reaches line 1027 with `borderCount == 1`.

## Root Cause of Engine Error

The investigator conflated the assert (`core_assert(borderCount >= 2)`) with an actual runtime guard. It saw the assert + the `== 2` early return and concluded `borderCount >= 3` for all paths. But the assert is stripped, and `== 2` doesn't cover `< 2`. The guard simply isn't there.

## What the Human Said

> "This will be a problem if *edgeLoop has only two items. Glass_ExtractCracksAndHolesFromLoop is where the *edgeLoop is created. The code is difficult to trace, but there is an assert that there are more than 2 and some conditional checks for 2. This indicates dev is concerned that is possible and so I am marking this as suspicious."

The human's reasoning: the assert's existence signals the developer's worry that borderCount < 2 is possible. If the dev was confident it couldn't happen, the assert wouldn't be there. This is a sound security heuristic.

## Lesson for Engine Improvement

The synthesizer's Guard Assessment correctly identified `core_assert_index` at line 825 as "Ineffective — assertions are compiled out in production." But it then marked the builder's structural guarantee (which depends on a *different* assert at line 1027) as "Effective." The engine inconsistently applied the assert-stripping rule.

A potential prompt improvement: when the synthesizer evaluates a guard chain that spans multiple functions, it should verify that **every link** in the chain is a real runtime check, not just the ones in the flagged function.
