# Orchestrated Engine Analysis — Batch b12 Run 20260326_175828

## Executive Summary

**Accuracy: 88.2%** (15/17 agreements with human ground truth). Two disagreements (CID 27746, CID 27724), two inconclusive (CID 22293, CID 23745).

### Aggregate Metrics

| Metric | Value |
|--------|-------|
| CIDs Analyzed | 19 |
| Agreements | 15 (88.2%) |
| Disagreements | 2 (CID 27746, CID 27724) |
| Inconclusive (NMD) | 2 (CID 22293, CID 23745) |
| Total Cost | $3.54 |
| Total Tokens | 977,532 |
| Total Duration | 3,292s (~55 min) |
| Avg Cost/CID | $0.19 |
| Avg Duration/CID | 173s |
| Total Leads | 58 (avg 3.1/CID) |
| Tool Hit Rate | 140/155 (90%) |
| Model | azure/gpt-5.1-codex |

### Verdict Distribution

| Verdict | Count | CIDs |
|---------|-------|------|
| True Positive (1337) | 15 | 19309, 15518, 27190, 29391, 27528, 25193, 25232, 27724, 24015, 22768, 21656, 27054, 25987, 20212, 29415 |
| False Positive (1007) | 2 | 27746, 27241 |
| Need More Data (7331) | 2 | 22293, 23745 |

---

## Per-CID Results (sorted by duration)

| CID | Dur | Cost | Leads | Rnds | Tools | Tokens | LOC | Plan | Investigate | Synthesize | Engine | Human | Match |
|-----|-----|------|-------|------|-------|--------|-----|------|-------------|------------|--------|-------|-------|
| 25193 | 52s | $0.07 | 4 | 6 | 5/5 | 21,685 | 144 | 32s | 10s | 9s | TP | TP | ✅ |
| 27054 | 56s | $0.06 | 4 | 6 | 7/7 | 27,387 | 104 | 25s | 20s | 11s | TP | TP | ✅ |
| 27190 | 56s | $0.06 | 3 | 5 | 5/5 | 19,991 | 85 | 23s | 24s | 10s | TP | TP | ✅ |
| 21656 | 67s | $0.08 | 3 | 5 | 6/6 | 23,435 | 83 | 21s | 26s | 21s | TP | TP | ✅ |
| 22768 | 68s | $0.08 | 3 | 5 | 5/5 | 23,439 | 87 | 14s | 25s | 29s | TP | TP | ✅ |
| 25987 | 72s | $0.07 | 3 | 5 | 6/5 | 23,670 | 84 | 16s | 34s | 22s | TP | TP | ✅ |
| 27528 | 77s | $0.11 | 2 | 4 | 6/6 | 46,200 | 386 | 19s | 41s | 18s | TP | TP | ✅ |
| 29415 | 84s | $0.11 | 4 | 6 | 6/6 | 27,640 | 118 | 26s | 34s | 24s | TP | TP | ✅ |
| 24015 | 94s | $0.09 | 3 | 5 | 7/7 | 29,510 | 136 | 25s | 50s | 19s | TP | TP | ✅ |
| 22293 | 113s | $0.10 | 2 | 4 | 3/3 | 19,451 | 48 | 30s | 45s | 38s | NMD | FP | 🔍 |
| 25232 | 115s | $0.14 | 3 | 5 | 6/6 | 46,195 | 1,279 | 56s | 32s | 27s | TP | TP | ✅ |
| 23745 | 134s | $0.17 | 3 | 5 | 11/9 | 48,419 | 145 | 21s | 84s | 29s | NMD | FP | 🔍 |
| 27724 | 171s | $0.18 | 3 | 5 | 3/3 | 34,634 | 502 | 72s | 58s | 42s | TP | FP | ❌ |
| 20212 | 203s | $0.37 | 4 | 6 | 22/20 | 172,149 | 1,124 | 24s | 160s | 18s | TP | TP | ✅ |
| 27241 | 269s | $0.24 | 3 | 5 | 4/4 | 38,148 | 435 | 43s | 22s | 204s | FP | FP | ✅ |
| 29391 | 282s | $0.34 | 4 | 6 | 17/13 | 99,093 | 496 | 50s | 221s | 11s | TP | TP | ✅ |
| 15518 | 312s | $0.43 | 3 | 5 | 17/12 | 105,707 | 334 | 34s | 246s | 32s | TP | TP | ✅ |
| 27746 | 382s | $0.38 | 2 | 4 | 11/10 | 85,338 | 169 | 17s | 334s | 31s | FP | TP | ❌ |
| 19309 | 686s | $0.49 | 2 | 4 | 8/8 | 85,441 | 362 | 328s | 321s | 36s | TP | TP | ✅ |

---

## Disagreement Analysis

### CID 27746 — FP ❌ (engine=FP, human=TP)

**Persistent failure** — This CID has never been correct across any run.

| Run | Date | Verdict | Human | Match |
|-----|------|---------|-------|-------|
| run_003 | Mar 25 | NMD | TP | ❌ |
| run_004 | Mar 25 | FP | TP | ❌ |
| run_005 | Mar 26 (b12) | FP | TP | ❌ |

**Leads this run**:
- **Lead 1** (11 rounds, low confidence, `SRB_IO_CONTROL::Signature` size: unknown) — Exhaustively searched for the struct definition. Spent $0.32 and failed — it's a Windows SDK type not in the repo.
- **Lead 2** (1 round, high confidence, local reads of `p->Signature` after write: none) — Found no local code reads the field after strncpy.

**Root cause**: `strncpy((char*)p->Signature, "SCSIDISK", 8)` writes exactly 8 bytes into an 8-byte `UCHAR[8]` field with no null terminator. The buffer is then passed to `DeviceIoControl`, which sends it to the SCSI miniport driver — an external consumer the engine cannot trace into. The planner failed to generate a lead asking about downstream consumers of the buffer via `DeviceIoControl`.

### CID 27724 — TP ❌ (engine=TP, human=FP) — NEW REGRESSION

**Verdict flip**: Previously correct (FP in run_002, run_003), now wrong (TP).

| Run | Date | Verdict | Human | Match |
|-----|------|---------|-------|-------|
| run_002 | Mar 24 | FP | FP | ✅ |
| run_003 | Mar 25 | FP | FP | ✅ |
| run_004 | Mar 26 (b12) | TP | FP | ❌ |

**Leads this run**:
- **Lead 1** (1 round, high confidence): `GetSize()` returns signed int64_t, can be negative on errors.
- **Lead 2** (1 round, high confidence): `File::Read` treats size as in/out reference.
- **Lead 3** (1 round, high confidence): `ParseCacheIndexLine` uses the data and len unchecked.

**Root cause**: The engine found the *potential* for negative `GetSize()` return values flowing into allocation/indexing, but failed to trace the **guard chain**: `if (!pFile.IsValid()) break;` at the call site prevents `GetSize()` from ever returning -1 in this path. Previous runs correctly identified this guard; this run's planner didn't generate a lead asking about preconditions at the call site.

---

## Inconclusive Cases

### CID 22293 — NMD 🔍 (engine=NMD, human=FP)

**History**: NMD (run_001) → FP (b12-fast) → NMD (b12). Non-deterministic.

**Root cause**: Cannot prove `LOCAL_CLIENT_COUNT <= STATIC_MAX_LOCAL_CLIENTS`. The engine found `STATIC_MAX_LOCAL_CLIENTS = 1` but couldn't resolve `LOCAL_CLIENT_COUNT`. Human says "textbook memset" — bounds are safely related.

### CID 23745 — NMD 🔍 (engine=NMD, human=FP)

**History**: NMD (run_001) → TP (b12-fast) → NMD (b12). Also non-deterministic.

**Root cause**: Same constant-relationship pattern as 22293. The engine found the array dimensions but couldn't prove the loop bound stays within array bounds.

---

## Cross-Run Comparison (b12 vs Previous Best)

| CID | Prev Dur | B12 Dur | Dur Δ | Prev $ | B12 $ | $ Δ | Verdict Δ |
|-----|----------|---------|-------|--------|-------|-----|-----------|
| 25193 | 53s | 52s | -2% | $0.06 | $0.07 | +24% | same |
| 27054 | 47s | 56s | +19% | $0.05 | $0.06 | +17% | same |
| 27190 | 42s | 56s | +35% | $0.05 | $0.06 | +9% | same |
| 21656 | 44s | 67s | +51% | $0.06 | $0.08 | +29% | same |
| 22768 | 50s | 68s | +37% | $0.05 | $0.08 | +61% | same |
| **25987** | **201s** | **72s** | **-64%** | $0.12 | $0.07 | -43% | same |
| **27528** | **837s** | **77s** | **-91%** | $0.47 | $0.11 | -77% | same |
| 29415 | 119s | 84s | -30% | $0.13 | $0.11 | -19% | same |
| 24015 | 124s | 94s | -24% | $0.11 | $0.09 | -22% | same |
| 22293 | 197s | 113s | -43% | $0.24 | $0.10 | -60% | FP→NMD ⚠️ |
| 25232 | 140s | 115s | -18% | $0.28 | $0.14 | -50% | same |
| 23745 | 178s | 134s | -25% | $0.21 | $0.17 | -21% | TP→NMD |
| **27724** | **907s** | **171s** | **-81%** | $0.29 | $0.18 | -38% | **FP→TP ❌** |
| 20212 | 282s | 203s | -28% | $0.25 | $0.37 | +48% | same |
| 27241 | 222s | 269s | +21% | $0.15 | $0.24 | +62% | TP→FP ✅ |
| **29391** | **33s** | **282s** | **+744%** | $0.04 | $0.34 | +752% | same |
| 15518 | 1,686s | 312s | -82% | $0.69 | $0.43 | -38% | same |
| 27746 | 743s | 382s | -49% | $0.35 | $0.38 | +9% | same |
| 19309 | 1,347s | 686s | -49% | $0.61 | $0.49 | -20% | same |

### Biggest Improvements
- **CID 27528**: 837s → 77s (-91%), $0.47 → $0.11 (-77%)
- **CID 15518**: 1,686s → 312s (-82%), $0.69 → $0.43 (-38%)
- **CID 27724**: 907s → 171s (-81%) — but verdict regressed
- **CID 25987**: 201s → 72s (-64%)
- **CID 19309**: 1,347s → 686s (-49%)

### Regressions
- **CID 29391**: 33s → 282s (+744%) — planner over-generated (4 leads, 17 tools)
- **CID 27724**: verdict regressed FP→TP (now wrong)
- **CID 22293**: verdict regressed FP→NMD (was correct, now inconclusive)

---

## Efficiency Analysis

### Cost Tiers

| Tier | Count | Avg Cost | Avg Duration |
|------|-------|----------|-------------|
| Cheap (<$0.10) | 9 | $0.07 | 69s |
| Medium ($0.10–$0.25) | 5 | $0.15 | 155s |
| Expensive (>$0.25) | 5 | $0.40 | 429s |

### Phase Distribution

| Phase | Avg Duration | % of Total |
|-------|-------------|------------|
| Plan | 44s | 25% |
| Investigate | 89s | 52% |
| Synthesize | 35s | 20% |

### Summary vs Previous Runs

| Metric | Run1 (Mar 24-25) | Run2 (Mar 25) | b12-fast (Mar 26) | **b12 (Mar 26)** |
|--------|-----------------|--------------|-------------------|-----------------|
| CIDs | 19 | 6 | 11 | **19** |
| Accuracy | 100% (15/15) | 83.3% (5/6) | 91% (10/11) | **88.2% (15/17)** |
| Total Cost | $2.99 | $2.21 | $1.28 | **$3.54** |
| Avg $/CID | $0.16 | $0.37 | $0.12 | **$0.19** |
| Avg Dur/CID | ~200s | 801s | 93s | **173s** |
| Tool Hit Rate | ~76% | 76% | — | **90%** |

---

## Suggested Improvements

1. **CID 27724 guard tracing**: Planner should always generate a lead asking "what preconditions/guards exist at the call site before the flagged operation?" when the issue involves function return values.

2. **CID 27746 external API knowledge**: Add common Windows SDK type definitions to the knowledge base, or teach the planner to ask about downstream consumers of buffers passed to external APIs.

3. **CID 29391 planner over-generation**: Simple pool-overflow CID went from 3 leads to 4 leads and 17 tool calls. Consider a planner heuristic: if code is <100 LOC with straightforward patterns, cap at 3 leads.

4. **CID 22293/23745 constant resolution**: Both fail on `LOCAL_CLIENT_COUNT ≤ STATIC_MAX_LOCAL_CLIENTS`. A dedicated constant-resolution tool or lead could help.

---

*Generated from run_cids_20260326_175828.csv on March 27, 2026*
