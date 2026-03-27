# CSV Maintenance Guide

How to create and update the lookup CSVs consumed by Vulnhalla's `db_lookup.py`.

---

## EnumLookup.csv

### Why it exists

`Classes.ql` uses CodeQL's `NameQualifyingElement`, which covers namespaces, classes, structs, unions, and typedefs — but **not** standalone `enum class` types (C++11 scoped enums). Those types were invisible to `get_class()`, causing the LLM to burn tool calls searching for them.

`EnumLookup.csv` fills that gap. It has the same column schema as `Classes.csv` so `get_class()` can use it as a seamless fallback.

### Schema

| Column | Example |
|--------|---------|
| `type` | `"Enum"` |
| `class_name` | `"hknpLevelOfDetail"` (qualified name) |
| `file` | `"D:/mapped_drives/cod/trunk/.../hknpTypes.h"` |
| `start_line` | `707` |
| `end_line` | `728` (post-fix; CodeQL raw value is often == start_line) |
| `simple_name` | `"hknpLevelOfDetail"` |

### How to regenerate

All commands assume the workspace root is `C:\Users\tliggett\source\repos\Vulnhalla` and the CodeQL DB is at `C:\code\codeQL_CoD\codeql`.

#### Step 1 — Run the CodeQL query

```powershell
& "C:\tmp\CQL\codeql-win64\codeql\codeql.cmd" query run `
    "data\queries\cpp\tools\EnumLookup.ql" `
    --database="C:\code\codeQL_CoD\codeql" `
    --output="C:\code\codeQL_CoD\codeql\EnumLookup.bqrs" `
    --threads=4
```

#### Step 2 — Decode BQRS → raw CSV

```powershell
& "C:\tmp\CQL\codeql-win64\codeql\codeql.cmd" bqrs decode `
    "C:\code\codeQL_CoD\codeql\EnumLookup.bqrs" `
    --format=csv `
    --output="C:\code\codeQL_CoD\codeql\EnumLookup_raw.csv"
```

This produces ~15,829 raw rows. Most `end_line` values will equal `start_line` (CodeQL limitation for `Enum` types). Many rows have bad start lines (CodeQL points to forward declarations, macro usages, or includes far above the actual enum definition).

#### Step 3 — Fix end-lines with the smart parser

```powershell
python data\queries\cpp\tools\fix_enum_endlines.py "C:\code\codeQL_CoD\codeql"
```

This script uses a **smart structural parser** (not naive brace-matching) that:

1. Opens `src.zip` from the DB folder
2. For each raw row, scans a 6-line window forward (and 1 line backward) from `start_line`
3. **Classifies** what's at the start line:
   - **Forward declaration** (`enum Name : type;`) → **skip** (no code to extract)
   - **Wrong enum** (scan window hits a different enum's keyword) → **skip**
   - **Macro-based** (`MAKE_ENUM(NAME)`, no real braces) → **skip**
   - **No enum keyword** in window (CodeQL start_line is too far above) → **skip**
   - **Real definition** (`enum [class] Name ... {`) → **brace-match** from `{`
   - **Typedef** (`typedef enum ... { ... } Name;`) → brace-match, verify name after `}`
4. After brace-matching, **post-verifies** the span contains our enum name
5. Deduplicates identical (name, file, start, end) rows

#### Smart parser vs naive parser

| Metric | Smart parser | Naive parser |
|--------|-------------|-------------|
| Right code returned | 10,760 | 10,886 |
| Wrong code returned | **0** | **3,039** |
| Accuracy | **100.0%** | 78.2% |
| Skipped (was wrong code) | 3,039 | — |
| Skipped (covered by other rows) | 154 | — |
| Real losses (not in CSV) | **0** | — |

The 154 "skipped but naive got right" cases are all duplicate raw rows where CodeQL reported a bad start line far above the actual enum — but the same enum is captured from a different raw row with a correct start line.

#### Intentionally excluded: gigantic enums

3 unique enums (10 raw rows after dedup) are excluded because they exceed the 500-line brace-match limit:

| Enum | File | Span |
|------|------|------|
| `Bind` | `com_keys.h` | 442 lines |
| `D3D12_MESSAGE_ID` | `d3d12sdklayers.h` (Windows SDK) | 956 lines |
| `WorkerCmdType` | `sys_workercmds_decl.h` | 1,593 lines |

These are intentionally left out. Enums this large are impractical for LLM consumption (they would blow the context window) and the value names within them are better discovered through targeted code search than by dumping the entire definition.

#### Step 4 — Verify

```powershell
# Spot-check a known enum
Select-String "C:\code\codeQL_CoD\codeql\EnumLookup.csv" -Pattern "hknpLevelOfDetail"
# Expected: ...,707,728,"hknpLevelOfDetail"

# Full accuracy check against source
$env:PYTHONIOENCODING="utf-8"
python _analysis\tools\test_smart_parser.py "C:\code\codeQL_CoD\codeql"
```

### How it's consumed

In `src/codeql/db_lookup.py`, `get_class()` first searches `Classes.csv`. If not found, it falls back to `EnumLookup.csv` with the same name-matching logic. The orchestrator tool description includes "enum" so the LLM knows to try `get_class` for enum types.

### Files involved

| File | Role |
|------|------|
| `data/queries/cpp/tools/EnumLookup.ql` | CodeQL query — selects all named `Enum` types |
| `data/queries/cpp/tools/fix_enum_endlines.py` | Post-processor — smart parser fixes `end_line` from `src.zip` |
| `_analysis/tools/test_smart_parser.py` | Full accuracy harness — compares smart vs naive against all 15,829 rows |
| `_analysis/tools/show_smart_losses.py` | Shows cases smart parser skips that naive got right (with CSV coverage check) |
| `_analysis/tools/check_both_skip.py` | Checks for real misses where both parsers skip |
| `src/codeql/db_lookup.py` | `get_class()` — consumes the CSV as fallback |
| `src/llm/orchestrator.py` | Tool description says "class/struct/union/enum" |

### When to re-run

Re-run Steps 1–3 whenever:
- The CodeQL database is rebuilt (new snapshot)
- `EnumLookup.ql` is modified
- `src.zip` contents change (new source extraction)

---

## TypeAliasLookup.csv

### Why it exists

`Classes.ql` queries `NameQualifyingElement`, which covers classes, structs, unions, and namespaces. C++ `typedef` and `using` type aliases (`TypedefType` in CodeQL) are **not** `NameQualifyingElement` subtypes, so they're invisible to `get_class()`.

This surfaced in CID 15518 run_011, where Lead 1 asked for `StLayerMaskOMPV` — a `using StLayerMaskOMPV = ntl::bitset<ST_MAX_LAYERS_PER_SURFACE_OMPV>;` alias. `get_class()` returned "not found", and the LLM burned 15 tool calls (60% of the run's budget) trying every possible tool to locate it.

`TypeAliasLookup.csv` fills that gap. Same column schema as `Classes.csv` and `EnumLookup.csv` so `get_class()` can use it as a seamless fallback.

### Why it was hard

Three CodeQL bugs/gotchas made the query deceptively difficult to get right:

#### 1. `matches()` uses SQL LIKE semantics — `_` is a wildcard

The initial filter to exclude compiler-internal names like `__int64` was:

```ql
not t.getName().matches("__%")
```

In CodeQL, `matches()` uses **SQL LIKE** semantics where `_` means "any single character" (not a literal underscore). So `__%` matches *any string with 2+ characters* — which silently filtered out **every named typedef in the database** except single-character names like `T`, `U`, `F`. The query returned only 86 rows with no errors or warnings.

**Fix:** Use `regexpMatch("^__.*")` instead of `matches("__%")`.

#### 2. `@kind problem` silently corrupts multi-column results

The initial query used `@kind problem` (copied from other queries) with 6 `select` columns. Problem queries expect exactly 2 columns (element + message). With 6 columns, CodeQL ran without error but produced garbled or truncated results.

**Fix:** Use `@kind table` for any query with more than 2 output columns.

#### 3. `getLocation().getFile()` silently drops rows

When a `TypedefType` has no file location (common for compiler builtins and template instantiations), the expression `t.getLocation().getFile().toString()` doesn't return `null` — it *silently excludes the entire row* from the result set. This is standard CodeQL semantics (failed navigation = no binding = row dropped), but it's easy to miss.

**Fix:** Null-safe helper predicates:

```ql
private string getFilePath(TypedefType t) {
  if exists(t.getLocation().getFile())
  then result = t.getLocation().getFile().toString()
  else result = ""
}
```

#### 4. Template instantiation explosion

Without filtering, the query returned **554,694 rows** — each template instantiation of a typedef (e.g., `std::remove_reference<int>::type`, `std::remove_reference<float>::type`, …) produces a separate row. A single `bdRemoteTaskRef` typedef appeared 78,608 times across translation units.

**Fix:** Two-stage reduction:
- In the QL query: `not t.getQualifiedName().matches("%<%")` excludes template instantiation aliases
- Post-decode: Python deduplication by qualified name (one row per unique name)

This reduced the CSV from 554K → 280K → **32,303 rows** (4.7 MB).

### Schema

| Column | Example |
|--------|---------|
| `type` | `TypeAlias` |
| `class_name` | `StLayerMaskOMPV` (qualified name) |
| `file` | `D:/mapped_drives/cod/trunk/.../SuperTerrainDefines.h` |
| `start_line` | `147` |
| `end_line` | `147` (same as start — aliases are single-line) |
| `simple_name` | `StLayerMaskOMPV` |

Note: Unlike `Classes.csv`, values are **not** double-quoted (CodeQL `@kind table` output differs from `@kind problem`).

### CodeQL type hierarchy

Understanding this was key to writing the correct query:

```
UserType
  └── TypedefType          ← base class (covers both styles)
        ├── CTypedefType           ← C-style:  typedef int MyInt;
        └── UsingAliasTypedefType  ← C++11:    using MyInt = int;
```

`TypedefType` is a `UserType` but **not** a `NameQualifyingElement`. That's why `Classes.ql` never sees it. The library source is at:
`C:\tmp\CQL\codeql-win64\codeql\qlpacks\codeql\cpp-all\6.1.3\semmle\code\cpp\TypedefType.qll`

### How to regenerate

All commands assume the workspace root is `C:\Users\tliggett\source\repos\Vulnhalla` and the CodeQL DB is at `C:\code\codeQL_CoD\codeql`.

#### Step 1 — Run the CodeQL query

```powershell
& "C:\tmp\CQL\codeql-win64\codeql\codeql.exe" query run `
    --database="C:\code\codeQL_CoD\codeql" `
    --additional-packs="C:\Users\tliggett\source\repos\Vulnhalla\data\queries" `
    --output="C:\code\codeQL_CoD\codeql\TypeAliasLookup.bqrs" `
    -- "data\queries\cpp\tools\TypeAliasLookup.ql"
```

Expect ~25s compile, ~45s evaluate for a large codebase.

#### Step 2 — Decode BQRS → raw CSV

```powershell
& "C:\tmp\CQL\codeql-win64\codeql\codeql.exe" bqrs decode `
    --format=csv `
    --output="C:\code\codeQL_CoD\codeql\TypeAliasLookup_raw.csv" `
    "C:\code\codeQL_CoD\codeql\TypeAliasLookup.bqrs"
```

This produces ~280K rows (after template filtering in the query). Many are duplicates across translation units.

#### Step 3 — Deduplicate by qualified name

```python
import csv, os

infile = r"C:\code\codeQL_CoD\codeql\TypeAliasLookup_raw.csv"
outfile = r"C:\code\codeQL_CoD\codeql\TypeAliasLookup.csv"

seen = set()
unique_rows = []
with open(infile, encoding="utf-8") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    for row in reader:
        qn = row["name"]
        if qn not in seen:
            seen.add(qn)
            unique_rows.append(row)

with open(outfile, "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(unique_rows)

print(f"Deduplicated: {len(unique_rows):,} rows, "
      f"{os.path.getsize(outfile) / (1024*1024):.1f} MB")
```

Expected output: ~32,303 rows, ~4.7 MB.

#### Step 4 — Verify

```powershell
# Spot-check a known typedef
Select-String "C:\code\codeQL_CoD\codeql\TypeAliasLookup.csv" -Pattern "StLayerMaskOMPV"
# Expected: TypeAlias,StLayerMaskOMPV,...SuperTerrainDefines.h,147,147,StLayerMaskOMPV

# Verify row count
(Get-Content "C:\code\codeQL_CoD\codeql\TypeAliasLookup.csv" | Measure-Object).Count
# Expected: ~32,304 (header + 32,303 data rows)
```

### How it's consumed

In `src/codeql/db_lookup.py`, `get_class()` searches **all three CSVs** (Classes, EnumLookup, TypeAliasLookup) in a unified loop. On the first pass, only exact matches are accepted. If no exact match is found across any CSV, it recurses with `less_strict=True` to allow substring matching. This ensures an exact typedef hit (e.g., `StLayerMaskOMPV`) is returned instead of a substring class hit (e.g., `StLayerMaskOMPVRaw`).

### Related prompt changes

When this CSV was added, two misleading prompt guidance strings were also removed:
- `prompt_loader.py`: Removed "try get_global_var for typedef" from `fuzzy_class_note` — `get_global_var` queries `GlobalOrNamespaceVariable` which never finds typedefs
- `llm_analyzer.py`: Removed "Try get_global_var for the typedef" from the fuzzy-match failure message

### Files involved

| File | Role |
|------|------|
| `data/queries/cpp/tools/TypeAliasLookup.ql` | CodeQL query — selects all named non-template `TypedefType` entries |
| `src/codeql/db_lookup.py` | `get_class()` — unified search across Classes, EnumLookup, TypeAliasLookup |
| `src/utils/prompt_loader.py` | Removed misleading "try get_global_var" guidance |
| `src/llm/llm_analyzer.py` | Removed misleading "try get_global_var" guidance |
| `src/llm/orchestrator.py` | Tool description says "class/struct/union/enum" (should also mention typedef) |

### When to re-run

Re-run Steps 1–3 whenever:
- The CodeQL database is rebuilt (new snapshot)
- `TypeAliasLookup.ql` is modified
- You need to pick up newly added `typedef` / `using` aliases in the codebase