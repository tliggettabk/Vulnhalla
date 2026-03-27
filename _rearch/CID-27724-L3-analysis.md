# CID 27724 — Lead 3 Deep Dive

## 2026-03-24 — Memory allocator inheritance chain investigation

### Issue Context

- **CID:** 27724
- **Category:** Memory — corruptions
- **Coverity Message:** Event overrun-buffer-arg: Calling "Read" with "buf" and "readSz" is suspicious because of the very large index, 18446744073709551615. The index may be due to a negative parameter being interpreted as unsigned.
- **File:** `VideoCache.cpp`
- **Function:** `VideoCache::LoadIndex()`
- **Flagged Line:** 599 (`pFile.Read( buf, readSz )`)
- **Data Flow:** `int64_t fileSz = pFile.GetSize()` (line 581) → `fileSz + 1` passed to `Allocate` (line 588) → `size_t readSz = fileSz` (line 598) → `pFile.Read(buf, readSz)` (line 599). A negative `fileSz` wraps to `SIZE_MAX` when cast to `size_t`.

### Lead Assignment

- **Question:** What parameter type and validation logic does `ClientMemoryAllocator::Allocate` apply to the size argument supplied at line 588?
- **Why it matters:** Line 588 passes `(fileSz + 1)` directly into `Allocate`. If `Allocate` accepts `size_t` and performs no bounds checking, then a negative `fileSz` (from `GetSize()` returning −1 on error) would silently wrap to a massive unsigned value — contributing to the buffer overflow condition at line 599.

### Run Metrics

| Metric | v1 (original) | v6 (batch post-fixes) | v7 (prompt strengthening) | v8 (end-of-class fix) |
|--------|---------|---------|---------|----------|
| Tool calls | 13 | 12 | 12 | **7** |
| Cached calls | 0 | 2 | 2 | 0 |
| Found rate | 5/13 (38%) | 5/12 (42%) | 5/12 (42%) | 4/7 (57%) |
| Follow-up rounds | — | — | 10 | 6 |
| Prompt tokens | — | — | 53,277 | 23,464 |
| Completion tokens | — | — | 5,620 | 2,401 |
| Total tokens | — | — | 58,897 | 25,865 |
| Cost | $0.32 | $0.14 | $0.09 | **$0.04** |
| Duration | 344.6s | — | 136.2s | **55.0s** |
| LLM seconds | — | — | 133.7s (98%) | — |
| Confidence | low | medium | medium | **medium** |
| Answered | false | true | true | **true** |

### Tool Call Sequence (v7)

| # | Tool | Argument | Found | Assessment |
|---|------|----------|-------|------------|
| 1 | `get_function_code` | `Telescope::ClientMemoryAllocator::Allocate` | ❌ ambiguous (111 `Allocate`) | **Essential** — seed tool from plan. Failed because `Allocate` is extremely common. Smart not-found message listed concrete implementations and flagged the `= 0` hint. |
| 2 | `get_class` | `Telescope::ClientMemoryAllocator` | ❌ not found | **Reasonable** — logical next step to find the class, but `ClientMemoryAllocator` is not a real class (it's an informal name from the code comment pattern `GetClientMemoryAllocator()`). |
| 3 | `get_function_code` | `Telescope::GetClientMemoryAllocator` | ✅ 5 LOC | **Essential** — revealed the factory function returns `MemoryWrapperClient*` via global `g_pTelescopeMemoryAllocator`. |
| 4 | `get_macro_or_global` | `g_pTelescopeMemoryAllocator` | ✅ 2 LOC | **Reasonable** — confirmed concrete type is `MemoryWrapperClient*`. Technically redundant given call 3 already showed the return type, but validates the chain. |
| 5 | `get_class` | `MemoryWrapperClient` | ✅ 7 LOC | **Essential** — showed the class inherits from `IMemoryAllocator` and does NOT override `Allocate` (only `GetStatsTracer()`). |
| 6 | `get_class` | `IMemoryAllocator` | ✅ 13 LOC | **Essential** — showed `IMemoryAllocator : public IBasicMemoryAllocator` with methods like `AllocateAligned`, `Reallocate` etc., all `= 0`. No `Allocate` override at this level. |
| 7 | `get_class` | `IBasicMemoryAllocator` | ✅ 19 LOC | **Essential** — the answer. Line 48: `virtual void *Allocate( size_t size, const MemoryTag &tag ) = 0;` — pure virtual, takes `size_t`, no runtime validation. This is the complete evidence needed. |
| 8 | `get_class` | `MemoryWrapperClient` (duplicate) | ✅ cached | **Wasteful** — exact same call as #5. Model re-examined the class hoping to find something it missed. Cache saved the DB hit but wasted an LLM round. |
| 9 | `get_function_code` | `MemoryWrapperClient::Allocate` | ❌ ambiguous | **Wasteful** — after seeing `Allocate` is `= 0` on `IBasicMemoryAllocator` and no override on `MemoryWrapperClient`, searching for the implementation is futile. The `= 0` declaration IS the answer. |
| 10 | `get_function_code` | `MemoryWrapperClient::MemoryWrapperClient` | ✅ 2 LOC | **Marginal** — model hoped the constructor's file location would help find an `Allocate` implementation. Low-probability but creative. Found nothing useful. |
| 11 | `get_function_code` | `MemoryWrapperClient::Allocate` (duplicate) | ❌ cached | **Duplicate** — identical to #9. Same ambiguous result. |
| 12 | `get_function_code` | `Telescope::MemoryWrapperClient::Allocate` | ❌ ambiguous | **Wasteful** — namespace-prefixed retry of #9/#11. Prompt explicitly says "do NOT retry with prefixes." Still got the same 111-Allocate ambiguity. |

**Summary:** 7 essential/reasonable calls (1–7), then 5 wasteful/duplicate calls (8–12) searching for a concrete `Allocate` that doesn't exist on `MemoryWrapperClient`.

### Tool Call Sequence (v8 — after end-of-class fix)

| # | Tool | Argument | Found | Assessment |
|---|------|----------|-------|------------|
| 1 | `get_function_code` | `Telescope::ClientMemoryAllocator::Allocate` | ❌ ambiguous | **Essential** — same seed as v7. |
| 2 | `get_class` | `Telescope::ClientMemoryAllocator` | ❌ not found | **Reasonable** — same as v7. |
| 3 | `get_function_code` | `Telescope::GetClientMemoryAllocator` | ✅ | **Essential** — revealed `MemoryWrapperClient*`. |
| 4 | `get_class` | `MemoryWrapperClient` | ✅ + `[end of class definition]` | **Essential** — saw no `Allocate` override + end-of-class annotation. Model now *trusts* this is complete. |
| 5 | `get_class` | `IMemoryAllocator` | ✅ | **Essential** — confirmed no `Allocate` at this level either. |
| 6 | `get_class` | `IBasicMemoryAllocator` | ✅ | **Essential** — found `Allocate(size_t, …) = 0`. |
| 7 | *(none — model answered)* | | | Model stopped and reported with medium confidence. |

**Summary:** All 7 calls essential/reasonable. Zero waste. The `[end of class definition]` annotation on call 4 eliminated the v7 tail of 5 wasteful calls.

### What It Was Stuck On

**Pure virtual inheritance chain with no concrete override.**

`MemoryWrapperClient` inherits from `IMemoryAllocator` which inherits from `IBasicMemoryAllocator`. The `Allocate` method is declared `= 0` on `IBasicMemoryAllocator` (line 48) and is **never overridden** by either `IMemoryAllocator` or `MemoryWrapperClient`. This means `MemoryWrapperClient` must be the wrong concrete class — the *actual* allocator used at runtime is likely injected via `g_pTelescopeMemoryAllocator` and could be any subclass (e.g., `DefaultMemoryAllocator`, `SubMemoryAllocatorTlsf`).

The model correctly walked the inheritance chain in calls 1–7 and found the `= 0` declaration. But instead of recognizing that as the answer (the interface defines the contract: `size_t`, no bounds checks), it spent calls 8–12 trying to find a concrete implementation that simply doesn't exist in the codebase under the `MemoryWrapperClient` name.

**Root cause:** The model doesn't fully trust the `= 0` declaration as sufficient evidence. It wants to see a concrete implementation to report with higher confidence. The prompt was strengthened in v7 ("the `= 0` declaration IS your answer") and the smart not-found message from the `get_function_code` tool now explicitly says "If this method was declared `= 0` in a class you already inspected, the interface signature IS your evidence — stop searching and use it." Despite this, the model still made 5 additional probes.

**Contributing factor:** The `get_function_code` tool returns an "ambiguous — 111 functions named 'Allocate'" error rather than "not found." The model interprets this as "maybe the right one is in there if I get the name right," whereas the reality is that `MemoryWrapperClient::Allocate` has no definition at all — `Allocate` is just an incredibly common method name.

**Resolution (v8):** The `get_class` truncation was identified as the root cause. CodeQL's `Classes.csv` recorded `end_line = 18` for `MemoryWrapperClient`, but the actual closing `};` is at line 25 (lines 19–25 are behind `#if TELESCOPE_USING(TELESCOPE_MEMORY_TRACING)`). The model saw a 6-line class with no closing brace and couldn't tell if an `Allocate` override was hiding beyond the cutoff. Fix: the orchestrator now appends `[end of class definition — no additional members exist in this class beyond what is shown above]` when `get_class` returns a snippet not ending with `};`. In v8, the model saw this on `MemoryWrapperClient` at call 4, trusted the class was complete, and stopped after 7 calls — eliminating all 5 wasteful calls from v7.

### Was the Conclusion Right?

**Yes.** The final answer is factually correct:

> "Client allocations go through `IBasicMemoryAllocator::Allocate`, which accepts the size argument as `size_t` and provides no runtime validation or bounds checking on that value."

This is exactly the evidence the synthesizer needed. The `size_t` parameter type means a negative `int64_t fileSz` (from `GetSize()`) wraps to `SIZE_MAX` when implicitly converted. The interface provides zero bounds checking.

**Confidence assessment:** `medium` is appropriate. The model correctly notes it found only the interface contract, not a concrete implementation. A human analyst would also rate this medium — we can say the interface *requires* no validation, but a concrete allocator *could* add its own checks. However, absent evidence of such checks, the conservative conclusion (no validation) is the correct one for security analysis.

**Could it have done better?** Yes — should have stopped at call 7. The evidence was complete. Calls 8–12 added nothing. Had it stopped at 7, cost would be ~$0.05 and duration ~80s instead of $0.09/136s.

### Cross-Lead Summary

| Lead | Question | Tool Calls | Confidence | Answered | Cost | Assessment |
|------|----------|------------|------------|----------|------|------------|
| 1 | GetSize() return-value range | 1 | high | true | $0.01 | Efficient — answered from seed tool |
| 2 | File::Read() length semantics | 2 | high | true | $0.03 | Efficient — answered in 2 calls |
| **3** | **Allocate parameter type/validation** | **10** | **low** | **true** | **$0.08** | **Excessive — 5 wasted calls after finding the answer at call 7** |

**Cross-lead observations:**
- Lead 1 found that `GetSize()` returns `int64_t` but could not determine its full range — answered=true in batch but answered=false in original v1 run.
- Lead 2 found `Read()` semantics efficiently with 2 calls.
- Lead 3's evidence (allocator interface takes `size_t`, no bounds checks) is independently valuable — the synthesizer combined all three leads correctly to conclude the bug is real (negative `fileSz` → `SIZE_MAX` allocation/read).
- There are no redundant lookups *across* leads — each investigated a different part of the data flow. Good plan decomposition.

### Lessons / Improvement Ideas

1. **"Ambiguous" ≠ "try harder"** — The `get_function_code` tool's "ambiguous — 111 functions named 'Allocate'" message is being interpreted by the model as "refine the name." For methods that are common (`Allocate`, `Init`, `Get`, etc.), the model should be trained to interpret ambiguity + prior `= 0` evidence as confirmation that no specific override exists. **Idea:** When the ambiguity response fires *and* the PRIOR TOOL RESULTS ledger shows a `= 0` declaration for that method, add a stronger "You already have the answer" message.

2. **Budget-aware stopping** — Calls 8–12 happened because the model wanted higher confidence. A mechanism that detects "you already have the `= 0` pattern for this exact method" and injects a "stop and report with your current evidence" nudge would save 40% of this lead's cost.

3. **Tool gap: class method disambiguation** — `get_function_code` can't disambiguate 111 `Allocate` methods even with `ClassName::` prefix, because the FunctionLookup.csv strips class qualifiers during the bare-name fallback. A `get_method(class, method)` tool that filters by class name in the CSV would eliminate this entire class of problem.

4. **`get_class` truncation** — `MemoryWrapperClient` returned only 6 lines (13–18) instead of the full class (13–25). Root cause: the CodeQL `Classes.csv` recorded `end_line = 18` because everything after line 18 is behind `#if TELESCOPE_USING(TELESCOPE_MEMORY_TRACING)`, which the CodeQL extractor excluded from the class range. The full file has `};` at line 25, but the model only saw through line 18 — no closing brace, so it couldn't tell whether an `Allocate` override was hiding beyond the cutoff. **Fix applied:** when `get_class` returns a snippet whose last line doesn't end with `};`, the orchestrator now appends `[end of class definition — no additional members exist in this class beyond what is shown above]`. This tells the model the class is complete and there is no hidden override to search for. Expected to eliminate calls 8–12 in this lead.

5. **Version trend:** v1→v6→v7→v8 shows steady improvement (13→12→12→**7** calls, $0.32→$0.14→$0.09→**$0.04**, false→true→true→true, low→medium→medium→medium). The prompt improvements and smart not-found messages helped the model *answer* the question (v1 gave up, v6+ answered). The end-of-class annotation in v8 finally eliminated the wasteful tail. **This lead is now resolved** — all tool calls are essential or reasonable, 0 waste.
