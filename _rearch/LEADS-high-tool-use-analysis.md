# High Tool-Use Leads Analysis

**Date:** 2026-03-24  
**Source:** `output\results_orchestrated\c\run_leads_batch_20260323.csv`  
**Compared against:** `output\results_orchestrated\c\run_leads_20260322_114133.csv` (original full run)

## Original vs. Batch Replay Comparison (high-tool-use leads)

| CID | Lead | Orig Calls / Conf / $ | Replay Calls / Conf / $ | Verdict |
|-----|------|-----------------------|-------------------------|---------|
| 27724 | 1 | 13 / low / $0.29 | **1 / high / $0.01** | Fixed |
| 27724 | 2 | 13 / low / $0.27 | **2 / high / $0.03** | Fixed |
| 27724 | 3 | 13 / low / $0.32 | 10 / low / $0.08 | Still spinning |
| 25987 | 1 | 12 / low / $0.38 | **1 / high / $0.009** | Fixed |
| 25987 | 2 | 12 / low / $0.17 | **2 / high / $0.01** | Fixed |
| 25987 | 3 | 10 / med / $0.34 | 6 / med / $0.11 | Slightly better |
| 20212 | 1 | 10 / med / $0.09 | **4 / high / $0.05** | Fixed |
| 20212 | 2 | 13 / low / $0.50 | 13 / low / $0.86 | Still spinning (fixed separately with v4 replay) |
| 20212 | 3 | 13 / low / $0.20 | **10 / high / $0.17** | Improved |
| 29415 | 2 | 14 / low / $0.67 | 11 / med / $0.50 | Slightly better |

## Three Leads That Still Waste Tool Calls

### 1. CID 29415 / Lead 2 — 11 calls, $0.50, medium confidence

**Question:** "What numeric range can localClientNum take…"

**Tool call sequence:**

| # | Tool | Args | Found |
|---|------|------|-------|
| 1 | get_macro | LOCAL_CLIENT_0 | True |
| 2 | get_macro | MAX_LOCAL_CLIENTS | True |
| 3 | get_class | LocalClientNum_t | **False** |
| 4 | get_macro_or_global | cl_maxLocalClients | True |
| 5 | get_macro_or_global | LOCAL_CLIENT_0 | True (duplicate of #1) |
| 6 | get_macro_or_global | LOCAL_CLIENT_0_CHAR | True |
| 7 | get_macro_or_global | MAX_LOCAL_CLIENTS | True (duplicate of #2) |
| 8 | get_macro_or_global | LocalClientNum_t | **False** |
| 9 | get_class | enum LocalClientNum_t | **False** |
| 10 | get_function_code | CL_TransientsVisibility_FillVisibilityHintBitArray | True |
| 11 | get_function_code | CL_Main_Init | **False** |

**Root cause:** `LocalClientNum_t` is an enum **not in EnumLookup.csv**. The LLM hits `get_class` 3× (all fail), then tries `get_macro_or_global` as fallback. Also wastes calls duplicating: `LOCAL_CLIENT_0` fetched by `get_macro` (#1) then re-fetched by `get_macro_or_global` (#5); same for `MAX_LOCAL_CLIENTS` (#2 → #7).

**Waste:** 5 calls are duplicates or futile retries against a data gap.

### 2. CID 27724 / Lead 3 — 10 calls, low confidence

**Question:** "What parameter type and validation logic do…"

**Tool call sequence:**

| # | Tool | Args | Found |
|---|------|------|-------|
| 1 | get_function_code | Telescope::ClientMemoryAllocator::Allocate | **False** |
| 2 | get_class | Telescope::ClientMemoryAllocator | **False** |
| 3 | get_function_code | Telescope::GetClientMemoryAllocator | True |
| 4 | get_class | MemoryWrapperClient | True |
| 5 | get_function_code | MemoryWrapperClient::Allocate | **False** |
| 6 | get_class | IMemoryAllocator | True |
| 7 | get_class | IBasicMemoryAllocator | True |
| 8 | get_function_code | MemoryWrapperClient::Allocate( size_t size, const MemoryTag &tag ) | **False** |
| 9 | get_function_code | MemoryWrapperClient::Allocate(size_t,const MemoryTag &) | **False** |
| 10 | get_class | MemoryWrapperClient | True (duplicate of #4) |

**Root cause:** `MemoryWrapperClient::Allocate` is an **inherited virtual method** — the Allocate implementation lives in the parent class, not in MemoryWrapperClient itself. FunctionLookup.csv only has the constructor/destructor/GetStatsTracer for MemoryWrapperClient, not Allocate. The LLM tries 3 different signature formats (#5, #8, #9), all fail. Then re-fetches the class (#10) to re-read what methods exist.

**Waste:** 4 calls are futile retries of the same missing inherited method. 1 is a duplicate class fetch.

### 3. CID 25987 / Lead 3 — 6 calls, 4 failed, medium confidence

**Question:** "What is the definition (type, length, and initialization) of…"

**Tool call sequence:**

| # | Tool | Args | Found |
|---|------|------|-------|
| 1 | get_global_var | s_waterDynamics_PhysicsBehavior_ActionDelay | True |
| 2 | get_macro_or_global | PHYSICS_WORLD_ID_COUNT | **False** |
| 3 | get_class | PhysicsRT_WorldId | **False** |
| 4 | get_function_code | WaterDynamics_Physics_GetWorldContext | True |
| 5 | get_macro_or_global | PHYSICS_WORLD_ID_GAME_AND_TEMP_COUNT | **False** |
| 6 | get_macro_or_global | PHYSICS_WORLD_ID_LAST | **False** |

**Root cause:** `PHYSICS_WORLD_ID_COUNT`, `PHYSICS_WORLD_ID_GAME_AND_TEMP_COUNT`, `PHYSICS_WORLD_ID_LAST` are all **not in Macros.csv**. `PhysicsRT_WorldId` IS in EnumLookup.csv but `get_class` (#3) failed because the EnumLookup fallback in `get_class()` wasn't wired up when this batch ran (March 23; fallback added March 24).

**Waste:** Call #3 should now succeed with the EnumLookup fallback. Calls #2, #5, #6 are a Macros.csv data gap.

**Update:** This lead should work much better now — `PhysicsRT_WorldId` will be found via `get_class` → EnumLookup fallback, giving the LLM the enum values it needs without the macro lookups.

## Summary of Root Causes

| Root Cause | Affected Leads | Fix |
|---|---|---|
| **Enum not in EnumLookup.csv** | 29415/L2 (`LocalClientNum_t`) | Add to CSV or improve CodeQL query coverage |
| **Inherited virtual method not in FunctionLookup** | 27724/L3 (`MemoryWrapperClient::Allocate`) | ✅ Fixed — see Post-Fix Replays below |
| **Macros missing from Macros.csv** | 25987/L3 (`PHYSICS_WORLD_ID_*`) | Expand Macros.ql or add manual entries |
| **EnumLookup fallback not yet deployed** | 25987/L3 (`PhysicsRT_WorldId`) | ✅ Fixed (March 24) — see Post-Fix Replays below |
| **LLM retries same lookup with different formatting** | 27724/L3, 29415/L2 | ✅ Prompt + code improvement (smart not-found suggestions) |
| **LLM duplicates earlier successful lookups** | 29415/L2 | Prompt improvement: remind LLM of prior results |

---

## Post-Fix Replays (2026-03-24)

### Changes Made

1. **`data/prompts/orchestrator_investigate.yaml`**: Added `PURE VIRTUAL / ABSTRACT METHODS` section
   telling the LLM not to retry lookups for `= 0` methods, and to look for concrete
   implementations in subclasses/parent classes instead.

2. **`src/codeql/db_lookup.py`**: Added `find_method_implementations()` — when
   `get_function_code("Class::method")` fails, searches FunctionLookup.csv for other
   `::method` implementations. Uses namespace hint to prioritize same-namespace results
   (e.g. when `Telescope::Foo::Allocate` fails, suggests `Telescope::DefaultMemoryAllocator::Allocate`).

3. **`src/llm/orchestrator.py`**: Wired up the suggestion in `_execute_tool()` — appends
   "Other implementations of 'method' exist: X, Y, Z. If the method is inherited or
   pure virtual (= 0), try one of these concrete implementations instead." to the not-found
   response.

### CID 25987 / Lead 3 — EnumLookup fallback fix

| Metric | Original (Mar 22) | Batch v3 (Mar 23) | v4 Replay (Mar 24) |
|--------|--------------------|--------------------|---------------------|
| Tool calls | 10 | 6 | **3** |
| Confidence | medium | medium | **high** |
| Cost | $0.34 | $0.11 | **$0.02** |
| Duration | — | 141s | **45s** |
| Answered | True | True | **True** |

`get_class('PhysicsRT_WorldId')` now succeeds via EnumLookup fallback (call #3). The LLM
gets the full enum definition, answers in 3 rounds with high confidence, and no longer
needs the missing macros.

### CID 27724 / Lead 3 — Pure virtual method fix

| Metric | Original (Mar 22) | Batch v3 (Mar 23) | v4 (prompt only) | v5 (prompt + suggestions) |
|--------|--------------------|--------------------|-------------------|---------------------------|
| Tool calls | 13 | 10 | 10 | 11 |
| Confidence | low | low | low | **medium** |
| Cost | $0.32 | $0.08 | $0.14 | **$0.07** |
| Duration | — | — | 248s | **82s** |
| Answered | **False** | **False** | **False** | **True** |

The tool call count didn't drop (the LLM still explores the class hierarchy), but the
critical difference: v5 **answered correctly** whereas all prior versions gave up.

The LLM's answer: `Allocate` takes `size_t size` (from `IBasicMemoryAllocator` line 48,
pure virtual `= 0`). No runtime validation or bounds checking in the interface.
This is the correct finding for the vulnerability analysis — if `fileSz` is negative,
casting to `size_t` wraps to a huge value with no allocator guards.

**Why the tool call count didn't drop:** The hierarchy walk (calls 1-6) is legitimate
investigation — it establishes *what* `Allocate` is. The problem was calls 7-8
(`MemoryWrapperClient::Allocate` and `Telescope::MemoryWrapperClient::Allocate`) which
fail because the method is pure virtual and has no implementation on the wrapper. But
after these fail with the new suggestions, the LLM absorbs that information and concludes
based on the interface signature rather than spinning further.

---

## Methodology: How This Analysis Was Done

This section documents the process so it can be repeated for future batch runs.

### Step 1: Load the batch results CSV

```powershell
Import-Csv "output\results_orchestrated\c\run_leads_batch_20260323.csv" `
  | Select-Object cid, lead_id, answered, confidence, tool_calls, estimated_cost_usd `
  | Format-Table -AutoSize
```

Look for leads with high `tool_calls` (≥6), low/medium confidence, or high cost. These are the candidates for waste analysis.

### Step 2: Find the original run for comparison

```powershell
# Find which CSV has the same CIDs
Import-Csv "output\results_orchestrated\c\run_leads_20260322_114133.csv" `
  | Select-Object -ExpandProperty cid -Unique
```

Then pull the same CIDs from the original:

```powershell
Import-Csv "output\results_orchestrated\c\run_leads_20260322_114133.csv" `
  | Where-Object { $_.cid -match '^(29415|27724|20212|25987)$' } `
  | Select-Object cid, lead_id, answered, confidence, tool_calls, estimated_cost_usd `
  | Format-Table -AutoSize
```

Compare original vs. replay side-by-side. Leads that dropped from 13→1 calls are "fixed." Leads that stayed at 10+ calls are still wasting.

### Step 3: Inspect tool call details for still-spinning leads

```powershell
Import-Csv "output\results_orchestrated\c\run_tool_calls_batch_20260323.csv" `
  | Where-Object { $_.cid -eq '29415' -and $_.lead_id -eq '2' } `
  | Select-Object round, tool, args, found `
  | Format-Table -AutoSize -Wrap
```

For each still-spinning lead, look for:
- **Repeated failed lookups** — same tool called 2-3× with slightly different args, all returning False
- **Duplicate successful lookups** — same data fetched twice via different tools (e.g., `get_macro` then `get_macro_or_global` for the same name)
- **Escalation patterns** — `get_class` fails → tries `get_macro_or_global` → tries `get_function_code` to find the definition indirectly

### Step 4: Check the source CSVs for data gaps

For each failed lookup, verify whether the data actually exists in the CSV:

```python
# Check EnumLookup.csv
with open(r'C:\code\codeQL_CoD\codeql\EnumLookup.csv', 'r', encoding='utf-8-sig') as f:
    for r in csv.DictReader(f):
        if 'LocalClientNum' in r.get('simple_name', ''):
            print('FOUND:', r)

# Check FunctionLookup.csv / FunctionTree.csv
with open(r'C:\code\codeQL_CoD\codeql\FunctionLookup.csv', 'r', encoding='utf-8') as f:
    for line in f:
        if 'MemoryWrapperClient' in line and 'Allocate' in line:
            print(line.strip())

# Check Macros.csv
with open(r'C:\code\codeQL_CoD\codeql\Macros.csv', 'r', encoding='utf-8') as f:
    for line in f:
        if 'PHYSICS_WORLD_ID' in line:
            print(line.strip())
```

This distinguishes:
- **Data gap** — the item genuinely isn't in the CSV (fix the CodeQL query or add manual entry)
- **Naming mismatch** — the item exists but under a different name (fix the lookup logic in `db_lookup.py`)
- **Inherited/virtual** — the method exists in a parent class but not under the child class name (harder to fix)

### Step 5: Classify and document

For each wasted lead, document:
1. The full tool call sequence (tool, args, found)
2. The root cause (data gap / naming mismatch / inherited method / stale code)
3. Whether a fix already exists or is needed
4. Cost impact ($saved if fixed)

### Key files involved

| File | Purpose |
|---|---|
| `output\results_orchestrated\c\run_leads_batch_*.csv` | Per-lead summary: tool_calls, confidence, cost, answered |
| `output\results_orchestrated\c\run_tool_calls_batch_*.csv` | Per-tool-call detail: tool, args, found, result_summary |
| `output\results_orchestrated\c\run_leads_20260322_114133.csv` | Original full run for comparison |
| `C:\code\codeQL_CoD\codeql\EnumLookup.csv` | Enum definitions lookup |
| `C:\code\codeQL_CoD\codeql\FunctionLookup.csv` | Function signature + location lookup |
| `C:\code\codeQL_CoD\codeql\FunctionTree.csv` | Function call tree with source ranges |
| `C:\code\codeQL_CoD\codeql\Classes.csv` | Class/struct/union definitions |
| `C:\code\codeQL_CoD\codeql\Macros.csv` | Macro definitions |
| `src\codeql\db_lookup.py` | Python code that implements `get_class`, `get_function_code`, etc. |
