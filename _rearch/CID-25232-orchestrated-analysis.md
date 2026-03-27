# CID 25232 — Orchestrated Analysis

## Issue Summary
- **CID**: 25232
- **Type**: Memory — corruptions
- **Message**: Overrunning array `pi->token` of 1024 bytes at byte offset 1024 using index `len` (which evaluates to 1024)
- **Location**: `ddl_parse.cpp:386`
- **Function**: `DDL_ParseExt` (lines 276–578)

The static analyzer flags the null-terminator write `pi->token[len] = 0` at line 386, claiming `len` can reach 1024 (one past the 1024-byte buffer).

---

## run_001

**Model**: azure/gpt-5.1-codex | **Leads**: 5 | **Tool calls**: 20 | **Tokens**: 196,794 | **Cost**: $0.9012 | **Duration**: 902s | **LOC analyzed**: 2,036 total (516 from tools) | **Verdict**: **1007 (False Positive)**

---

### 1. Plan Quality

| Lead | Question | Seed Tool | Overlap? |
|------|----------|-----------|----------|
| 1 | What is the declaration (type and element count) of `parseInfo_t::token`? | `get_class(parseInfo_t)` | No |
| 2 | How is `DDL_MAX_TOKEN_CHARS` defined, and does its value include space for the trailing null terminator? | `get_macro(DDL_MAX_TOKEN_CHARS)` | No |
| 3 | What are the strings (and their lengths) stored in the `punctuation` array referenced at lines 548-565? | `get_global_var(punctuation)` | No |
| 4 | Which callers of `DDL_ParseExt` configure `pi->keepStringQuotes` before the unguarded writes at lines 367-385? | `get_caller_function(DDL_ParseExt)` | No |
| 5 | What maximum value can `len` reach immediately before the null-terminator write at line 386? | `get_macro(DDL_MAX_TOKEN_CHARS)` | Slight with L2 |

**Assessment:**
- **Non-overlapping**: Mostly yes. Leads 1-4 are cleanly separated. Lead 5 shares the same seed tool as Lead 2 (macro lookup), but asks a different question — max `len` value analysis vs. macro semantics. Acceptable overlap.
- **Sufficient**: Yes. The leads cover: buffer declaration (L1), buffer size constant (L2), unchecked memcpy path (L3), caller-controlled flag that gates the unguarded write (L4), and direct bounds reasoning on the flagged line (L5).
- **Seed tools**: All reasonable. `get_class`, `get_macro`, `get_global_var`, and `get_caller_function` are exactly the right entry points for each question.
- **Key weakness**: Lead 3 (punctuation array) is a secondary concern — the flagged line 386 is in the quoted-string path, not the punctuation path. The planner was being thorough covering *all* write paths, but this lead ended up consuming by far the most budget ($0.43) and failed to answer. A tighter plan could have skipped or deprioritized it.

**Plan cost**: $0.1161 (14,797 tokens, 122s) — reasonable for 5 leads.

---

### 2. Per-Lead Investigation Deep-Dive

#### Lead 1 (1 round, answered, high confidence, *token type: `char[DDL_MAX_TOKEN_CHARS]`*)
Chasing the `parseInfo_t::token` declaration. Single `get_class` call returned the struct immediately. Clean, efficient, correct.

| Round | Tool | Args | Cached? | Phase | Needed? |
|-------|------|------|---------|-------|---------|
| seed | `get_class` | `parseInfo_t` | no | seed | yes |

- **Rounds**: 1 / 12 budget
- **Tool calls**: 1 (0 cached)
- **Cost**: $0.0072
- **Duration**: 5s
- **LOC**: 322 (18 from tools)
- **Issues**: None. Textbook-perfect lead execution.

---

#### Lead 2 (1 round, answered, high confidence, *DDL_MAX_TOKEN_CHARS = 1024, null-terminator safe in normal paths*)
Resolved the macro value and verified all parsing loops check `len < DDL_MAX_TOKEN_CHARS - 1` before writes. Very thorough evidence with 11 cited lines.

| Round | Tool | Args | Cached? | Phase | Needed? |
|-------|------|------|---------|-------|---------|
| seed | `get_macro` | `DDL_MAX_TOKEN_CHARS` | no | seed | yes |

- **Rounds**: 1 / 12 budget
- **Tool calls**: 1 (0 cached)
- **Cost**: $0.0599 (higher cost due to large completion analyzing all parsing paths)
- **Duration**: 55s
- **LOC**: 306 (2 from tools — macro is tiny, analysis came from initial code)
- **Issues**: None. Single tool call was sufficient because the initial code snippet already contained all the parsing loops. The model reasoned across all five parsing paths from context alone.

---

#### Lead 3 (12 rounds, budget exhausted, low confidence, *punctuation contents: UNKNOWN*)
Attempted to retrieve the `punctuation` global array contents. Spent all 12 rounds trying different strategies to find the array initializer — `get_global_var`, `get_macro_or_global` (3 times!), `get_function_code` for nearby functions, `get_class` for nearby types — but each attempt only returned the declaration line without the initializer content.

| Round | Tool | Args | Cached? | Phase | Needed? |
|-------|------|------|---------|-------|---------|
| seed | `get_global_var` | `punctuation` | no | seed | returned declaration only |
| 1 | `get_macro_or_global` | `punctuation` | no | followup | **redundant** — same result |
| 2 | `get_function_code` | `GetParseThreadInfo` | no | followup | speculative — hoping for adjacent code |
| 3 | `get_macro_or_global` | `punctuation` | no | followup | **redundant** — 3rd attempt |
| 4 | `get_function_code` | `SkipWhitespace` | no | followup | speculative |
| 5 | `get_class` | `parseInfo_t` | no | followup | speculative, already retrieved by L1 |
| 6 | `get_class` | `ParseThreadInfo` | no | followup | speculative |
| 7 | `get_function_code` | `DDL_strlen` | no | followup | speculative |
| 8 | `get_macro_or_global` | `punctuation` | no | followup | **redundant** — 4th attempt |
| 9 | `get_class` | `ParseTokenType` | no | followup | speculative |
| 10 | `get_macro_or_global` | `PARSE_TOKEN_UNKNOWN` | no | followup | speculative |
| 11 | `get_macro_or_global` | `DDL_MAX_TOKEN_CHARS` | no | followup | **redundant** — already known from L2 |

**Problems identified:**
1. **Redundant calls**: `get_macro_or_global("punctuation")` was called 3 times after the initial `get_global_var("punctuation")`, despite the anti-duplicate prompt. Same tool + same args = wasted rounds.
2. **No macro→global_var fallback benefit**: The tool literally couldn't return the array initializer — it only returned the declaration line. The model correctly diagnosed this in round 10 but kept trying indirect approaches.
3. **Speculative "adjacency" strategy**: The model tried retrieving nearby functions/classes hoping the tool would return enough surrounding context to include the punctuation array. This is creative but fundamentally a tool limitation — the tools return function/class boundaries, not file ranges.
4. **Should have surrendered earlier**: By round 4-5, the pattern was clear. Round 10 produced a "no_tools" answer acknowledging failure, but the system forced 2 more rounds.

**Cost impact**: $0.4272 — **47% of total run cost** for zero actionable information.

---

#### Lead 4 (5 rounds, answered, high confidence, *caller sets keepStringQuotes: never*)
Traced the call graph from `DDL_ParseExt` → found sole caller `DDL_GetToken` → confirmed it never sets `keepStringQuotes` → verified `parseInfo_t` defaults `keepStringQuotes = false`. Also traced callers of `DDL_GetToken` upstream.

| Round | Tool | Args | Cached? | Phase | Needed? |
|-------|------|------|---------|-------|---------|
| seed | `get_caller_function` | `DDL_ParseExt` | no | seed | yes |
| 1 | `get_function_code` | `DDL_GetToken` | no | followup | yes — needed caller source |
| 2 | `get_function_code` | `DDL_ParseExt` | no | followup | yes — needed to cite the guarded writes |
| 3 | `get_caller_function` | `DDL_GetToken` | no | followup | yes — traced upstream callers |
| 4 | `get_class` | `parseInfo_t` | no | followup | yes — confirmed default value |

- **Rounds**: 5 / 12 budget
- **Tool calls**: 5 (0 cached)
- **Cost**: $0.2220
- **Duration**: 221s
- **LOC**: 737 (433 from tools, avg 87 LOC/call — large functions)
- **Issues**: Clean execution. Each call was purposeful. The high LOC/call reflects that `DDL_ParseExt` itself is 302 lines and `DDL_GetToken` brings in 13 more. No drift, no redundancy.
- **Key insight found**: `keepStringQuotes` is always false → the unguarded closing-quote write at lines 381-384 never executes → the flagged overflow at line 386 is unreachable.

---

#### Lead 5 (1 round, answered, high confidence, *max len at line 386: DDL_MAX_TOKEN_CHARS when keepStringQuotes=true, else DDL_MAX_TOKEN_CHARS-1*)
Pure control-flow reasoning over the initial code plus the cached macro value. Correctly identified that:
- Normal loop: `len` maxes at `DDL_MAX_TOKEN_CHARS - 1` = 1023
- Closing quote with `keepStringQuotes=true`: `len` reaches `DDL_MAX_TOKEN_CHARS` = 1024 (off-by-one)
- But this only matters if `keepStringQuotes` is true (deferred to Lead 4)

| Round | Tool | Args | Cached? | Phase | Needed? |
|-------|------|------|---------|-------|---------|
| seed | `get_macro` | `DDL_MAX_TOKEN_CHARS` | **yes** (cached from L2) | seed | yes |

- **Rounds**: 1 / 12 budget
- **Tool calls**: 1 (1 cached)
- **Cost**: $0.0306
- **Duration**: 31s
- **LOC**: 306 (2 from tools)
- **Issues**: None. The model leveraged cached data and performed all reasoning from the initial code snippet. Excellent efficiency.

---

### 3. Finding Quality

| Lead | Cites Lines? | Factual? | Answers Question? | Drifts? | Confidence Appropriate? |
|------|-------------|----------|-------------------|---------|------------------------|
| 1 | Yes (line 27) | Yes | Yes — type + size | No | High — correct |
| 2 | Yes (11 lines) | Yes | Yes — value + null-terminator analysis | No | High — correct |
| 3 | N/A (unanswered) | N/A | No — budget exhausted | N/A | Low — correct |
| 4 | Yes (lines 32, 363, 583) | Yes | Yes — caller analysis + flag default | No | High — correct |
| 5 | Yes (lines 1, 381-398) | Yes | Yes — max len analysis | No | High — correct |

**Standout**: Lead 5's finding is exceptionally precise — it identifies the exact off-by-one path (closing quote → `len++` to 1024 → terminator write at index 1024), then correctly notes this depends on `keepStringQuotes` being true. This chains perfectly with Lead 4's finding that the flag is always false.

**No drift**: No lead strayed into another lead's territory or attempted to deliver a verdict. Clean separation.

---

### 4. Synthesis Readiness

**Do the findings chain together?** Yes, excellently:
1. L1: `token` is `char[1024]` → valid indices 0-1023
2. L2: All loop writes guarded by `len < 1023` → `len` maxes at 1023 in normal paths
3. L5: The *only* way `len` reaches 1024 is via the `keepStringQuotes` closing-quote block
4. L4: `keepStringQuotes` is always `false` → that block never executes
5. ∴ `len` never reaches 1024 → `pi->token[len] = 0` at line 386 is always in-bounds

**Gap**: Lead 3 (punctuation array) failed. This means the `memcpy(pi->token, *punc, l)` at line 563 is technically unverified for bounds safety. However:
- The flagged line is 386 (quoted-string path), not 563 (punctuation path)
- Punctuation strings in parsers are typically very short (1-3 chars: `==`, `!=`, `<<`, etc.)
- The synthesizer correctly ignored this gap and focused on the flagged path

**Verdict quality**: The synthesizer produced a well-structured 4-section verdict (Evidence Summary → Data Flow Analysis → Guard Assessment → Verdict) with correct **1007 (False Positive)** classification. The reasoning is sound — the overflow scenario requires `keepStringQuotes=true`, which never happens.

---

### 5. LOC Analysis

| Lead | Initial LOC | Tool LOC | Total LOC | Avg LOC/call | Tool calls |
|------|-------------|----------|-----------|-------------|------------|
| Lead 1 | 304 | 18 | 322 | 18.0 | 1 |
| Lead 2 | 304 | 2 | 306 | 2.0 | 1 |
| Lead 3 | 304 | 61 | 365 | 5.1 | 12 |
| Lead 4 | 304 | 433 | 737 | 86.6 | 5 |
| Lead 5 | 304 | 2 | 306 | 2.0 | 1 |
| **Run total** | — | 516 | **2,036** | — | 20 |

**Key observations:**
- **Lead 3**: 12 tool calls returned only 61 LOC total (avg 5.1/call). Classic "spinning without progress" — high rounds + low LOC = the tools couldn't deliver the needed data.
- **Lead 4**: Highest LOC (433 from tools) with a very high avg of 86.6/call — correctly pulling large function bodies for call-graph analysis. Efficient use of budget.
- **Leads 2 & 5**: Only 2 LOC from tools (a macro definition), but both reasoned extensively from the 304-line initial code snippet. Demonstrates that "LOC analyzed" undercounts intellectual work when the initial snippet is rich.
- **Total LOC (2,036)** is reasonable for this complexity. The issue touches a single 302-line function with straightforward data-flow dependencies.

---

### 6. Cost & Efficiency

| Component | Tokens | Cost | Duration | % of Total Cost |
|-----------|--------|------|----------|----------------|
| Planner | 14,797 | $0.1161 | 122s | 12.9% |
| Lead 1 | 4,766 | $0.0072 | 5s | 0.8% |
| Lead 2 | 9,900 | $0.0599 | 55s | 6.6% |
| Lead 3 | 99,316 | $0.4272 | 432s | **47.4%** |
| Lead 4 | 52,668 | $0.2220 | 221s | 24.6% |
| Lead 5 | 7,238 | $0.0306 | 31s | 3.4% |
| Synthesizer | ~8,109* | ~$0.0382* | 35s | 4.2% |
| **Total** | **196,794** | **$0.9012** | **902s** | 100% |

*Synthesizer tokens estimated from total minus sum of leads/planner.*

**Efficiency verdict**:
- **Without Lead 3**: The run would have cost ~$0.47, taken ~470s, and reached the same correct verdict. Lead 3's failure consumed **47.4% of budget** for zero value.
- **$/LOC**: $0.9012 / 2,036 ≈ $0.00044/LOC. Removing Lead 3: $0.47 / 1,671 ≈ $0.00028/LOC.
- **Leads 1, 2, 5** are extremely efficient (combined $0.10, 91s, all answered with high confidence).
- **Lead 4** is moderately expensive ($0.22) but delivered the most critical finding — this was money well spent.

---

### 7. Lead Breakdown Summary

- **Lead 1** (1 round, answered, high confidence, *token declaration: `char[DDL_MAX_TOKEN_CHARS]`*) — Retrieved `parseInfo_t` struct definition. Found `token` is a fixed 1024-byte array. Textbook single-call execution. Correct.

- **Lead 2** (1 round, answered, high confidence, *DDL_MAX_TOKEN_CHARS: 1024, null-safe*) — Retrieved macro definition, then analyzed all 5 parsing paths from initial code. All use `len < DDL_MAX_TOKEN_CHARS - 1` guard before writes. Correct and thorough.

- **Lead 3** (12 rounds, budget exhausted, low confidence, *punctuation contents: unknown*) — Chasing the `punctuation` global array initializer to check the `memcpy` at line 563. Tools could only return the declaration, not the initializer content. Burned 12 rounds and $0.43 on redundant `get_macro_or_global` calls and speculative adjacency lookups. Never answered, but didn't impact the verdict — the flagged line is in the quoted-string path, not punctuation.

- **Lead 4** (5 rounds, answered, high confidence, *caller sets keepStringQuotes: never*) — Traced `DDL_ParseExt` call graph, found sole caller `DDL_GetToken`, confirmed it never sets `keepStringQuotes`. Verified default is `false`. This was the pivotal finding that proved the overflow path unreachable. Correct.

- **Lead 5** (1 round, answered, high confidence, *max len at line 386: 1024 only if keepStringQuotes=true*) — Pure control-flow analysis showing the off-by-one exists in theory but depends on the flag. Correctly deferred to Lead 4 for reachability. Leveraged cached macro result. Correct.

---

### 8. Suggested Improvements

#### Tool / Infrastructure
1. **`get_global_var` should return initializer content**: Lead 3's entire failure stems from the tool returning only the declaration line for the `punctuation` array. If the tool returned the full initializer (even if large), Lead 3 would have answered in 1 round and saved $0.42.
2. **Add a "get_file_range" or "get_lines" tool**: Several Lead 3 attempts tried to find the array by retrieving adjacent functions. A simple line-range tool would have solved this immediately.

#### Investigator Prompt
3. **Anti-redundancy enforcement needs strengthening**: Lead 3 called `get_macro_or_global("punctuation")` 3 times with the same args. The anti-duplicate system should hard-block identical calls.
4. **Earlier surrender signal**: The model correctly diagnosed failure at round 10 ("Unable to answer") but the system forced 2 more rounds. When the model explicitly says "unable to answer" with no tools requested, the lead should terminate immediately.

#### Planner
5. **Deprioritize non-flagged paths**: The flagged line is 386 (quoted-string path). Lead 3 investigated the punctuation path at line 563 — a different code path entirely. The planner should annotate which leads are "primary" (directly relevant to the flagged line) vs. "secondary" (covering other potential overflow paths) and cap the budget for secondary leads.

#### Cost Optimization
6. **Budget cap per lead**: If Lead 3 had been capped at 4-6 rounds (or ~$0.15), total run cost would have dropped to ~$0.60 with the same verdict quality.
7. **Early termination on repeated tool failures**: If the same tool returns the same unhelpful result 2+ times, auto-stop the lead.

---

### 9. Verdict Assessment

**Final verdict: 1007 (False Positive)** — **Correct and well-supported.**

The core logic chain is:
1. `pi->token` is `char[1024]` (valid indices 0-1023)
2. All normal character writes guard `len < 1023`
3. The only unguarded write (closing quote at line 383-384) only executes when `keepStringQuotes == true`
4. `keepStringQuotes` is initialized to `false` and no caller ever sets it to `true`
5. Therefore `len` never reaches 1024 at line 386 → no overflow

**Nuance the synthesizer handled well**: It acknowledged that the overflow *is theoretically possible* if `keepStringQuotes` were ever set to `true`, but correctly concluded that based on current call chains this never happens. This is a "dead code guards the bug" pattern — the vulnerability exists in the code but is unreachable.

**One caveat not discussed**: If a *future* caller sets `keepStringQuotes = true`, the overflow becomes real. The synthesizer could have noted this as a latent risk, but for a point-in-time vulnerability assessment, 1007 is correct.
