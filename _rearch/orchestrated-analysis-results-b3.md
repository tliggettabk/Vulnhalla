# Batch b3 — Orchestrated Analysis Results (2026-03-26)

## Summary (original run)

| CID | LLM Verdict | Code | Human Says | Match? | Cost | Leads | Tools | Duration |
|-----|------------|------|-----------|--------|------|-------|-------|----------|
| **29468** | More Data | — | Not an issue (FP) | **Inconclusive** | $0.04 | 1 | 3 | 59s |
| **25863** | True Positive | 1337 | FP — padding, not used | **WRONG** | $0.53 | 6 | 22 | 630s |
| **26682** | False Positive | 1007 | Not an issue (FP) | **Correct** | $0.05 | 1 | 2 | 59s |
| **18162** | True Positive | 1337 | TP — no bounds check | **Correct** | $0.10 | 3 | 5 | 90s |
| **16933** | True Positive | 1337 | FP — hardcoded, always found | **WRONG** | $0.06 | 2 | 3 | 88s |

**Original accuracy: 2/5 (40%)**

## Summary (after fixes)

| CID | LLM Verdict | Code | Human Says | Match? | Fix Applied |
|-----|------------|------|-----------|--------|-------------|
| **29468** | False Positive | 1007 | Not an issue (FP) | **Correct** | `max_completion_tokens=16384` in `_llm_call` |
| **25863** | False Positive | 1007 | FP — padding, not used | **Correct** | "FOLLOW DELEGATION CHAINS" in investigator prompt + versioned replay fix |
| **26682** | False Positive | 1007 | Not an issue (FP) | **Correct** | (no fix needed) |
| **18162** | True Positive | 1337 | TP — no bounds check | **Correct** | (no fix needed) |
| **16933** | True Positive | 1337 | FP — hardcoded, always found | **WRONG** | (no fix attempted — requires data-guarantee reasoning) |

**Post-fix accuracy: 4/5 (80%)**

---

## Per-CID Analysis

### CID 29468 — More Data (inconclusive) — DEEP DIVE

**Issue**: Coverity flagged `&dismemberBoneIndex` (a 1-byte `byte` local) at line 411 as being overrun by 3 bytes when passed to `XModelGetBoneIndex()`.

**Plan**: Only 1 lead generated — "How does `XModelGetBoneIndex()` use the outIndex pointer at lines 404 and 411?"

**Investigation (Lead 1)**: 3 rounds, 3 tool calls, all found. Traced the full call chain:
1. `XModelGetBoneIndex()` (line 2248) — thin wrapper, calls Init then Internal
2. `XModelGetBoneIndex_Init()` (line 2217) — the key function. Under `#if USING(CLIENT_GAME)`:
   - **Line 2223**: `if (*index < 128)` — reads the caller's byte immediately
   - **Line 2225**: `localByte = index + 4` — forms pointer arithmetic 4 bytes past the buffer (the Coverity trigger)
   - **BUT line 2229**: `localByte = index` — immediately reassigns back to the original pointer
   - **Line 2230**: `*localByte = XMODELGETBONEINDEX_CHECKBYTE` — writes only 1 byte (a sentinel)
   - The `index + 4` pointer is **never dereferenced** — it's dead code / obfuscation
3. `XModelGetBoneIndex_Internal()` (line 1258) — iterates bones, writes `*index = truncate_cast<byte>(offset + localBoneIndex)` — single byte write only

**Investigator conclusion**: "The function assumes the caller supplies at least one writable byte (and even forms `index + 4`), but it only ever writes to the first byte." Confidence: high.

**Synthesizer failure**: The raw response was **truncated** — only produced the Evidence Summary paragraph (step 1 of 4). No Data Flow Analysis, Guard Assessment, or status code was emitted. The synthesizer stopped mid-output, causing the verdict parser to classify it as "More Data" (no code found).

**Root cause of failure**: Synthesizer truncation. The investigation had enough evidence to conclude FP (1007) — the `index + 4` pointer arithmetic is dead code that's immediately overwritten by `localByte = index`. Coverity flagged the pointer formation, not an actual write. This is a **false positive** — the human agrees: "localByte is set to a random memory location, it is not dereferenced and is set correctly 2 lines later."

**What should have happened**: The plan should have been richer (e.g., a second lead asking "Is the `index + 4` pointer ever dereferenced?" or "What does `XModelGetBoneIndex_Check` do?"). But even with 1 lead, the evidence was sufficient for FP. The synthesizer just failed to complete its output.

**Failure category**: Synthesizer truncation (not a reasoning failure)

**Correct verdict**: FP (1007) — `index + 4` pointer is never dereferenced; only `*index` (1 byte) is ever written.

### CID 25863 — TP 1337 (WRONG, human says FP) — DEEP DIVE + FIX

**Issue**: Coverity flagged uninitialized use of `drawState.atlasDataOffsets`, `drawState.flareSurfGlob`, and `drawState.padding` when passed to `FX_DrawModularParticles` at line 104.

**Original run**: $0.53, 630s, 6 leads, 22 tool calls. Verdict: TP (1337).

**Original plan (6 leads)**:
1. How are `atlasDataOffsets`, `flareSurfGlob`, and `padding` declared in `FxDrawState`?
2. What does `DebugWipe` do? → Found: no-op macro, struct stays uninitialized
3. What does `R_BeginFlareSurfs` store into `flareSurfGlob`? → **Budget exhausted** (12 rounds)
4. How does `FX_DrawModularParticles` use `atlasDataOffsets`? → Found delegation to `DrawSpriteParticles` but **stopped there**
5. Under what control flow is `flareSurfGlob` dereferenced? → Found conditional init via `drawFlares` flag
6. Where is `padding` read in `FX_DrawModularParticles`? → Found: never read

**Why it failed**: The synthesizer saw uninitialized fields passed to `FX_DrawModularParticles` and assumed they were consumed. Lead 4 discovered the delegation to `DrawSpriteParticles` at line 46 but **didn't trace into it** — the investigator's scope ended at `FX_DrawModularParticles`. Without knowing what the downstream consumer actually reads, the synthesizer had to assume the worst.

**Root cause**: Investigator didn't follow the delegation chain. The answer was one tool call away.

#### Fix 1: Investigator prompt — "FOLLOW DELEGATION CHAINS"

Added to `orchestrator_investigate.yaml`:
```
FOLLOW DELEGATION CHAINS:
If the function you are investigating simply forwards a pointer,
struct, or buffer to a callee (e.g. calls helper(ptr) without
accessing ptr itself), do NOT stop at that function. Look up the
callee to determine whether the data is actually used there. Keep
following the chain until you find where the data is concretely
read, written, or dereferenced — or until you confirm it is never
accessed. A function that only passes data through is not a sink.
```

#### Fix 2: Versioned finding preference in `_replay_synthesize`

The `_replay_synthesize` method hardcoded loading `2_{N}_final.json` (base version only). Changed to glob for `2_{lid}_final_v*.json` and prefer the highest version number, falling back to the base file.

#### Replay result — Lead 4 v2

With the prompt fix, Lead 4 traced **12 levels deep**:

`FX_DrawModularParticles` → `ParticleManager::DrawSpriteParticles` → `ParticleSystem::DrawSpriteParticles` → `ParticleEmitter::DrawSpriteParticles` → `DrawElements_SpriteCommon` → `DrawElements_CPUSpriteCommonDraw` → `SpriteDrawPostCull` → `AddCodeSurfEmitterData` → `FX_SpriteReset` → `FX_QuadGenQuad` → `FX_AddAtlasDataReserveCodeSurfBuffers`

**Key new finding**: `atlasDataOffsets` is a **write-first cache**. At line 842, the code checks `atlasDataOwners[cacheSlot] == packedFrames` before reading `atlasDataOffsets[cacheSlot]`. Since `atlasDataOwners` was zeroed by `Core_ZeroMemory` (line 44), the cache always **misses** on first access (zero ≠ any real pointer), taking the miss path (line 848) which **writes** into `atlasDataOffsets` before ever reading the uninitialized value. The uninitialized data is never consumed.

- **Rounds**: 12 | **Tools**: 12 | **Cost**: $0.33 | **Duration**: 155s
- **Confidence**: high

#### Re-synthesize result

With the v2 finding loaded, the synthesizer correctly concluded **False Positive (1007)** — matching the human triage.

- v4 synthesize: prompt=3,473, completion=3,915, duration=49s

### CID 26682 — FP 1007 (Correct)
Clean, efficient run. Single lead confirmed `DObjGetBoneIndex` only writes 1 byte through `*outIndex`, matching the 1-byte `boneIndex` buffer. No overrun possible. Matches human triage.

### CID 18162 — TP 1337 (Correct)
Solid analysis. 3 leads covered: (1) loop bound is 24 via `BG_SCRIPTED_CAMERA_MAX_CHARACTERS`, (2) callee arrays are only 20 elements with no bounds checks, (3) `HasCharacterModels` also doesn't guard. Engine correctly identified indices 20-23 can overrun the 20-element arrays. Matches human ("no bounds checking, devs put in assert shows concern").

### CID 16933 — TP 1337 (WRONG, human says FP)
2 leads found: (1) `BG_Omnvar_GetIndexByName` can return `UINT_MAX` on failed lookup, (2) `BG_Omnvar_GetDef` only has `core_assert_index` (compiled out in production). The engine concluded a missing omnvar entry leads to OOB. The human says the value `"ai_fulllight"` is hardcoded and always present in the lookup table, so the failure path is unreachable. Root cause: the engine analyzed reachability of the *code path* but not the *data guarantee* — it doesn't know the omnvar table is statically populated.

---

## Patterns

- **Correct FP (26682)**: single focused lead, clear data-flow, low cost — the engine excels at these.
- **Correct TP (18162)**: well-scoped multi-lead plan covering bound, callee, and alternative guard — textbook win.
- **Wrong TP (16933)**: engine finds a *theoretical* vulnerability path but misses static data guarantees. Requires reasoning about data population, not just code paths.
- **Fixed: 29468**: Synthesizer truncation due to missing `max_completion_tokens`. Fix: set `max_completion_tokens=16384` in `_llm_call`. Verdict flipped from inconclusive → correct FP.
- **Fixed: 25863**: Investigator stopped at delegation boundary. Fix: "FOLLOW DELEGATION CHAINS" prompt addition. Lead 4 traced 12 levels deep, found uninitialized values are never read. Verdict flipped from wrong TP → correct FP.

## Code Changes Made

1. **`src/llm/orchestrator.py`** — `_llm_call()`: Added `"max_completion_tokens": 16384` to `completion_params` dict. Prevents reasoning-model output truncation.
2. **`data/prompts/orchestrator_investigate.yaml`** — Added "FOLLOW DELEGATION CHAINS" section instructing investigators to trace into callees when a function only forwards data.
3. **`src/llm/orchestrator.py`** — `_replay_synthesize()`: Changed finding loader to prefer latest versioned file (`2_{lid}_final_v*.json`) over base version. Bug fix: replays now use updated lead findings.
4. **`src/vulnhalla.py`** — Added `batch` parameter to `IssueAnalyzer.__init__()`. Uses `issues-{batch}.csv` instead of `issues.csv` when set.
5. **`_rearch/__copilot.md`** — Updated run examples with batch parameter documentation.
