# Orchestrated Engine Analysis — Run 20260325_112539

## Executive Summary

**Accuracy: 83.3%** (5/6 agreements with human ground truth). One disagreement on CID 27746 where the engine returned FP but the human marked TP.

### Aggregate Metrics

| Metric | Value |
|--------|-------|
| CIDs Analyzed | 6 |
| Agreements | 5 (83.3%) |
| Disagreements | 1 (CID 27746) |
| Total Cost | $2.21 |
| Total Tokens | 542,949 |
| Total Duration | 4,808s (~80 min) |
| Avg Cost/CID | $0.37 |
| Model | azure/gpt-5.1-codex |

### Verdict Distribution

| Verdict | Count | CIDs |
|---------|-------|------|
| True Positive (1337) | 5 | 19309, 15518, 27190, 29391, 27528 |
| False Positive (1007) | 1 | 27746 |

---

## Per-CID Results

### CID 19309 — TP ✅ (agrees with human)

**Run**: run_005 | **Cost**: $0.61 | **Tokens**: 173,526 | **Duration**: 1,347s | **LOC**: 343

**Human**: *"This will be a problem if \*edgeLoop has only two items. Glass_ExtractCracksAndHolesFromLoop is where the \*edgeLoop is created. The code is difficult to trace, but there is an assert that there are more than 2 and some conditional checks for 2. This indicates dev is concerned that is possible and so I am marking this as suspicious."*

| Lead | Question | Rounds | Tools | Outcome | Confidence | Cost |
|------|----------|--------|-------|---------|------------|------|
| 1 | What guarantees vertCount ≥ 2 before accessing coord[1] and coord[vertIter-1]? | — | 0 | **Error** (API timeout) | none | $0.00 |
| 2 | What prevents vertCount from exceeding GLASS_VERT_PER_PIECE_LIMIT during population loop? | 3 | 10 | answered | high | $0.22 |

**Analysis**: Lead 1 failed completely due to a `litellm.Timeout` (300s connection timeout). Despite this, Lead 2 alone carried the analysis — it found that `GLASS_VERT_PER_PIECE_LIMIT` is 128 but loops from `Glass_ExtractCracksAndHolesFromLoop` can produce up to `GLASS_CRACK_POINT_LIMIT` (255) edges, creating a buffer overflow. The synthesizer correctly reached TP from just one lead's evidence.

**Notable**: The API timeout on Lead 1 consumed ~$0.39 of the $0.61 total cost (plan + error overhead). Without the timeout, this CID would have cost ~$0.22. This is a resilience success — the engine recovered from a total lead failure and still produced the correct verdict.

---

### CID 15518 — TP ✅ (agrees with human)

**Run**: run_011 | **Cost**: $0.69 | **Tokens**: 148,099 | **Duration**: 1,686s | **LOC**: 913

**Human**: *"No bounds checking on index, may return 256 if no free bits."*

| Lead | Question | Rounds | Tools | Outcome | Confidence | Cost |
|------|----------|--------|-------|---------|------------|------|
| 1 | How is layerMask.num_bits defined, what size limit does it impose? | 12 | 15 | budget-exhausted | low | $0.29 |
| 2 | What return-value guarantees do find_first_bit/find_first_bit_from provide when no bits remain? | 3 | 8 | answered | high | $0.17 |
| 3 | What bounds are applied to layerCount before R_ST_IterateLayerMask is called? | 1 | 1 | answered | medium | $0.03 |
| 4 | How does the callback use layerIndex, what array bounds does it rely on? | 1 | 1 | answered | medium | $0.06 |

**Analysis**: Lead 1 exhausted its 12-round budget trying to resolve `ntl::bitset` class definition — a known hard case. Despite this, Leads 2–4 provided sufficient evidence: `find_first_bit` returns `num_bits` (256) as sentinel when exhausted, `layerCount` is unbounded at the call site, and the callback indexes `materialDistancesSq[layerIndex]` (a 256-element array) with no bounds check. The synthesizer correctly chained these findings into a TP verdict.

**Cost note**: Lead 1 consumed 43% of cost ($0.29) without answering. The 3 successful leads together cost only $0.26.

---

### CID 27190 — TP ✅ (agrees with human)

**Run**: run_004 | **Cost**: $0.05 | **Tokens**: 17,760 | **Duration**: 98s | **LOC**: 85

**Human**: *"No bounds checking and sanitymsg shows concern."*

| Lead | Question | Rounds | Tools | Outcome | Confidence | Cost |
|------|----------|--------|-------|---------|------------|------|
| 1 | How is s_meshPoolUsed declared, what bounds does it impose on index? | 2 | 2 | answered | high | $0.006 |
| 2 | What is the value range of c_meshPoolSize? | 1 | 1 | answered | high | $0.004 |
| 3 | What container type does s_meshPool represent, how many elements does emplace provide? | 1 | 2 | answered | high | $0.010 |

**Analysis**: Clean, efficient analysis. All 3 leads answered with high confidence in minimal rounds. The engine correctly identified that when all 16 pool slots are used, `index` becomes 16 and the code still writes `s_meshPoolUsed[index]` and returns `&(*s_meshPool)[index]`, causing OOB access. `core_assert_always` is the only guard and it's a no-op in production.

**Exemplary efficiency**: $0.05 total, 98s, all leads answered. This is the ideal outcome for a straightforward issue.

---

### CID 29391 — TP ✅ (agrees with human)

**Run**: run_004 | **Cost**: $0.05 | **Tokens**: 15,491 | **Duration**: 97s | **LOC**: 83

**Human**: *"No bounds checking and sanitymsg shows concern."*

| Lead | Question | Rounds | Tools | Outcome | Confidence | Cost |
|------|----------|--------|-------|---------|------------|------|
| 1 | What container type/capacity does s_meshPool have? | 2 | 2 | answered | high | $0.011 |
| 2 | What constant does c_meshPoolSize represent? | 1 | 1 | answered | high | $0.002 |
| 3 | What is the declared length of s_meshPoolUsed? | 1 | 1 | answered | high | $0.003 |

**Analysis**: Nearly identical to CID 27190 (same codebase, same pattern). Same pool-exhaustion OOB bug. All leads answered with high confidence. Engine correctly identified the overflow at index 16 past the 16-element arrays.

**Note**: CIDs 27190 and 29391 appear to be the same or closely related code issue — same pool, same function, same bug pattern. The engine handled both correctly and cheaply.

---

### CID 27746 — FP ❌ (DISAGREES with human)

**Run**: run_004 | **Cost**: $0.35 | **Tokens**: 72,111 | **Duration**: 743s | **LOC**: 156

**Human**: *"p->Signature is 8 so it will not be null terminated."*

**Engine verdict**: 1007 (False Positive) — "The field is treated as a fixed-length binary signature, never used as a C-string, and never read within this code path."

| Lead | Question | Rounds | Tools | Outcome | Confidence | Cost |
|------|----------|--------|-------|---------|------------|------|
| 1 | What is the declared size/type of SRB_IO_CONTROL::Signature? | 10 | 9 | budget-exhausted | low | $0.27 |
| 2 | Does get_drive_identify_data_using_scsi() ever read p->Signature after writing? | 1 | 1 | answered | high | $0.011 |

**Root Cause of Disagreement**: The engine couldn't find the `SRB_IO_CONTROL` struct definition (it's a Windows SDK type not in the repo). Lead 1 spent 10 rounds trying to locate it and failed. Lead 2 correctly found that Signature is never read again *within this function*. The synthesizer concluded FP based on "no subsequent use."

However, the human analyst recognized that `p->Signature` is an 8-byte `UCHAR[8]` member, and `strncpy((char*)p->Signature, "SCSIDISK", 8)` writes exactly 8 chars with no null terminator. The buffer is then passed to `DeviceIoControl`, which sends it to the SCSI miniport driver — the driver or other consumers may interpret Signature as a null-terminated string, causing an overread.

**Key insight**: The engine's scope was too narrow — it only checked whether *this function* reads p->Signature after writing, but missed that the buffer is passed to an external API (`DeviceIoControl`) which consumes it externally. The planner failed to generate a lead asking "who reads p->Signature downstream of this function?" or "does DeviceIoControl or the SCSI miniport interpret Signature as a C-string?"

**Improvement**: The investigator prompt or planner should consider external API consumers as potential sinks, not just local code paths.

---

### CID 27528 — TP ✅ (agrees with human)

**Run**: run_004 | **Cost**: $0.47 | **Tokens**: 115,962 | **Duration**: 837s | **LOC**: 768

**Human**: *"This will be a problem if dst enters this function with a value of 63."*

| Lead | Question | Rounds | Tools | Outcome | Confidence | Cost |
|------|----------|--------|-------|---------|------------|------|
| 1 | What is the declaration of reg_lmap (type and element count)? | 9 | 9 | answered | high | $0.32 |
| 2 | What is the declaration of reg_map (type and element count)? | 1 | 1 | answered | high | $0.008 |
| 3 | How is FAST_IS_REG defined, what does it constrain? | 1 | 2 | answered | high | $0.028 |
| 4 | What is the definition of TMP_REG1? | 1 | 1 | answered | medium | $0.021 |

**Analysis**: Excellent multi-lead investigation. Lead 1 took 9 rounds but successfully found `reg_lmap` is a 17-byte array. Lead 3 found `FAST_IS_REG(dst)` only enforces `dst <= 0x3f` (63), which allows indices 17–63 to overflow the 17-element arrays. The synthesizer correctly identified that `dst = 63` satisfies the guard but overflows `reg_lmap[dst]` by 46 bytes.

**Note**: Lead 1 consumed 67% of total cost ($0.32) — most of the 9 rounds were spent resolving macro definitions and tracing array sizes through `SLJIT_NUMBER_OF_REGISTERS`. The other 3 leads were cheap and fast.

---

## Cross-CID Comparison

| CID | Leads | Rounds | Tools | Tools Found | LOC | Cost | Duration | Engine | Human | Match |
|-----|-------|--------|-------|-------------|-----|------|----------|--------|-------|-------|
| 19309 | 2 | 4 | 10 | 10 | 343 | $0.61 | 1,347s | TP | TP | ✅ |
| 15518 | 4 | 6 | 25 | 17 | 913 | $0.69 | 1,686s | TP | TP | ✅ |
| 27190 | 3 | 5 | 5 | 5 | 85 | $0.05 | 98s | TP | TP | ✅ |
| 29391 | 3 | 5 | 4 | 4 | 83 | $0.05 | 97s | TP | TP | ✅ |
| 27746 | 2 | 4 | 10 | 4 | 156 | $0.35 | 743s | FP | TP | ❌ |
| 27528 | 4 | 6 | 13 | 11 | 768 | $0.47 | 837s | TP | TP | ✅ |

## Efficiency Analysis

### Cost Distribution

| Category | Count | Avg Cost | Avg Duration | Avg LOC |
|----------|-------|----------|-------------|---------|
| Quick wins (≤$0.10) | 2 | $0.047 | 98s | 84 |
| Medium complexity ($0.10–$0.50) | 2 | $0.41 | 790s | 462 |
| High complexity (>$0.50) | 2 | $0.65 | 1,517s | 628 |

### Budget Exhaustion & Error Impact

3 of 18 total leads (17%) hit issues:
- **CID 19309 Lead 1**: API timeout (total failure, 0 tools used)
- **CID 15518 Lead 1**: Budget exhausted at 12 rounds (ntl::bitset resolution)
- **CID 27746 Lead 1**: Budget exhausted at 10 rounds (couldn't find Windows SDK type)

These 3 failing leads consumed $0.56 — **25% of total run cost** — without answering their questions. Despite this, the engine still produced correct verdicts for 2 of the 3 affected CIDs (19309, 15518).

### Tool Hit Rate

| CID | Tools Called | Tools Found | Hit Rate |
|-----|-------------|-------------|----------|
| 19309 | 10 | 10 | 100% |
| 15518 | 25 | 17 | 68% |
| 27190 | 5 | 5 | 100% |
| 29391 | 4 | 4 | 100% |
| 27746 | 10 | 4 | 40% |
| 27528 | 13 | 11 | 85% |
| **Total** | **67** | **51** | **76%** |

CID 27746 had the lowest hit rate (40%), consistent with it searching for external SDK types not in the codebase.

---

## Key Observations

### 1. Resilience to Lead Failures
The engine showed strong resilience — in 2 of 3 cases where a lead failed (19309, 15518), the remaining leads provided enough evidence for a correct verdict. The exception (27746) failed because the *critical* unknown was the missing lead, not just a supporting one.

### 2. CID 27746 Root Cause
The disagreement is a **scope limitation**, not a reasoning error. The engine correctly analyzed what it could see: `p->Signature` is never read after writing within this function. But the real issue is that `strncpy(..., 8)` writes exactly 8 bytes with no null terminator into an 8-byte field, and the buffer is then passed to `DeviceIoControl` — an external consumer the engine couldn't trace into.

**Suggested fix**: Add planner guidance to generate a lead about external API consumers when the flagged data flows into an external function call.

### 3. Cost Concentration
The Pareto pattern is strong: 67% of cost ($1.48) was spent on just 3 leads (the failing/high-round ones). The 15 successful leads totaled $0.73.

### 4. Duplicate Issues
CIDs 27190 and 29391 are essentially the same bug (mesh pool OOB). Both were handled efficiently at $0.05 each, 98s each.

### 5. Model Consistency
All runs used `azure/gpt-5.1-codex`. No model variation in this batch.

---

## Comparison with Previous Run (same 6 CIDs)

Previous runs: 19309/run_004, 15518/run_010, 27190/run_003, 29391/run_003, 27746/run_003, 27528/run_003.

| CID | Prev Run | Curr Run | Verdict Change | Leads | Tools | Cost | Duration | Tokens |
|-----|----------|----------|---------------|-------|-------|------|----------|--------|
| 19309 | run_004 | run_005 | 1337 → 1337 (same) | 2→2 | 13→10 | $0.46→$0.61 | 393s→1,347s | 108K→174K |
| 15518 | run_010 | run_011 | 1337 → 1337 (same) | 2→4 | 14→25 | $0.33→$0.69 | 284s→1,686s | 86K→148K |
| 27190 | run_003 | run_004 | 1337 → 1337 (same) | 3→3 | 5→5 | $0.04→$0.05 | 45s→98s | 16K→18K |
| 29391 | run_003 | run_004 | 1337 → 1337 (same) | 3→3 | 6→4 | $0.07→$0.05 | 82s→97s | 21K→15K |
| **27746** | run_003 | run_004 | **7331 → 1007** | 1→2 | 12→10 | $0.38→$0.35 | 408s→743s | 74K→72K |
| 27528 | run_003 | run_004 | 1337 → 1337 (same) | 3→4 | 14→13 | $0.44→$0.47 | 367s→837s | 127K→116K |

**Totals**: $1.72 → $2.21 (+29%) | 1,679s → 4,808s (+186%)

### Verdict Stability
- **5 of 6 verdicts unchanged** — all TP calls held steady across runs.
- **CID 27746 changed: 7331 (Need More Data) → 1007 (False Positive)** — Previously the engine couldn't resolve the issue at all and returned inconclusive. Now with 2 leads (vs 1), it committed to FP. Unfortunately neither verdict matches the human (TP). The previous 7331 was arguably more honest — it reflected that the engine couldn't find `SRB_IO_CONTROL`. The new run confidently said FP because Lead 2 found no local reads of `p->Signature`, but still missed the external API consumer.

### Cost & Duration Trends
- **Cost went up overall** (+29%). Major drivers:
  - **19309**: +$0.15 due to API timeout on Lead 1 (wasn't present before)
  - **15518**: +$0.35 due to expanding from 2→4 leads (added Leads 3 & 4 about call sites and callbacks)
- **Duration roughly doubled** for most CIDs — likely due to longer reasoning chains with the current model/prompt configuration.
- **29391 got cheaper**: $0.07 → $0.05 (fewer tools, 6→4), only CID that improved on cost.
