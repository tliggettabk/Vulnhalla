# CID 29391 Deep Dive: Cost/Duration Regression

**Human verdict:** TP (1337) | **All runs:** 1337 ✅ — verdict always correct, no accuracy regression.

## The Problem: 10x Cost Blowup

| Run | Batch | Leads | Tools | Cost | Duration | Verdict |
|-----|-------|-------|-------|------|----------|---------|
| run_001 | earliest | 3 | 0 | $0.004 | 4s | 1337 ✅ |
| run_002 | earliest | 3 | 0 | $0.007 | 7s | 1337 ✅ |
| run_003 | earliest | 3 | 0 | $0.011 | 16s | 1337 ✅ |
| run_004 | run2 | 3 | 4 | $0.003 | 6s | 1337 ✅ |
| **run_005** | **b12-fast** | **3** | **5** | **$0.04** | **33s** | **1337 ✅** |
| **run_006** | **b12** | **4** | **17** | **$0.34** | **282s** | **1337 ✅** |

## Root Cause: Lead 4 — Caller-Chain Tracing

run_006's planner generated a 4th lead that run_005 didn't:

> **Lead 4**: _"Which functions call GetHalfEdgeMesh() (line 15), and what preconditions do they impose to guarantee the loop at lines 22-28 finds a free slot before the writes at lines 36-37?"_

This lead consumed **10 rounds, 11 tool calls, 72,805 tokens, $0.25, and 221s** — 73% of the total run cost.

### Plan Comparison

| Lead | run_005 (3 leads, $0.04) | run_006 (4 leads, $0.34) |
|------|--------------------------|--------------------------|
| 1 | c_meshPoolSize definition/size | c_meshPoolSize declaration/value |
| 2 | s_meshPoolUsed declaration/allocation | s_meshPool declaration/element count |
| 3 | s_meshPool construction/capacity | s_meshPoolUsed definition/size |
| 4 | — | **Caller preconditions for GetHalfEdgeMesh** |

## Analysis: Lead 4 Was Legitimate

The 4th lead asked the right question. A pool-capacity check could live multiple callers up — a scene manager counting active clippers, a job scheduler limiting concurrency, a factory checking availability before constructing. The immediate caller (`HalfEdgeClipper::HalfEdgeClipper`) having no guard doesn't mean no caller does.

The investigator followed the "FOLLOW DELEGATION CHAINS" rule correctly: don't stop at a pass-through, keep tracing. The 10 rounds were the investigator checking each caller in the chain for a precondition. It found none, but that's genuinely informative — it confirms no caller in the reachable call graph enforces pool capacity.

### Finding

> _"The only observed caller of GetHalfEdgeMesh is HalfEdgeClipper::HalfEdgeClipper, whose body consists solely of the bare call. It performs no availability checks, error handling, or delegation before invoking GetHalfEdgeMesh, so the loop has no caller-supplied precondition guaranteeing a free slot."_ (confidence: low)

This strengthens the TP verdict — the 3-lead runs reached the same verdict but with weaker evidence (they assumed no caller guard without checking).

## Conclusion

The cost blowup is an inherent property of **"prove no caller enforces X" questions**. You can't prove absence without exhausting reachable callers. When a guard *does* exist, the investigator finds it early and stops cheap. When it doesn't, the search necessarily covers the full call chain.

This is not an efficiency bug or a lead-selection error. It's the cost of thorough analysis. The planner non-deterministically generated 3 vs 4 leads across runs — the 4th lead is reasonable and its answer is genuine evidence. The 3-lead runs were cheaper but also less rigorous.

### Potential Mitigations (if cost reduction is desired)

These are trade-offs, not pure wins:

1. **Caller-depth limit** — Cap how many levels up the investigator traces (e.g., 3 callers). Risk: misses a guard that lives higher up.
2. **Cost-aware soft stop** — If a lead exceeds a token/cost threshold, the investigator reports what it found so far with a "low confidence" marker. Risk: incomplete evidence.
3. **Planner cost awareness** — The planner could be told that caller-chain questions are expensive and should only be generated when the local evidence is ambiguous. Risk: misses legitimate FP cases where a caller guard is the key evidence.

None of these are recommended without broader regression testing — the 3-lead runs already got the right answer for this CID, but other CIDs might need the caller-chain evidence to avoid false positives.
