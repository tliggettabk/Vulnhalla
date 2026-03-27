# Orchestrated Analysis Architecture

## Problem
The single-conversation approach (v10–v20) encodes control flow as prompt rules.
The LLM ignores them: duplicate tool calls, infinite loops, no fact convergence.
Procedural logic belongs in Python; reasoning belongs in the LLM.

## Architecture: Plan → Investigate → Synthesize

### Phase 1: PLAN (1 LLM call)
- **Input:** Issue description + code + hint questions
- **Output:** JSON array of leads
  ```json
  [
    {"id": "A", "question": "What does find_first_bit_from return when no bit is set?",
     "why": "Determines if sentinel value 256 can reach callback",
     "tool": "get_function_code", "args": {"function_name": "find_first_bit_from"}},
    ...
  ]
  ```
- **Prompt:** Lightweight. "You are a security researcher. Given this issue, identify
  3–5 investigation leads. For each, state the question, why it matters, and
  which tool to start with."
- **No reasoning rules here** — just decomposition.

### Phase 2: INVESTIGATE (N agents, Python-orchestrated)
- Python fans out leads. Per lead:
  1. Python calls the initial tool.
  2. Sends tool result + lead question to a focused LLM call.
  3. Agent can request up to **3 follow-up tools** (Python executes, deduplicates globally).
  4. Agent returns structured JSON:
     ```json
     {"lead_id": "A", "answer": "find_first_bit_from returns num_bits (256) when no bit found",
      "confidence": "high", "evidence": "Line 42: return num_bits;"}
     ```
- **Deduplication:** Python tracks all tool calls across agents. If agent B requests
  the same tool+args as agent A already called, it gets the cached result.
- **Dead ends:** If all tools return "not found," the agent returns
  `{"answer": "could not determine", "confidence": "none"}`.
  This absence becomes evidence in Phase 3.
- **No cumulative context** — each agent sees only its own lead + tool results.

### Phase 3: SYNTHESIZE (1 LLM call)
- **Input:** Original issue + code + all lead findings
- **Output:** Verdict + status code + explanation
- **Prompt carries the heavy rules:**
  - Assertions are NO-OPs (transitive)
  - No concrete bound → guard is ineffective
  - Analyzer's numbers are facts
  - "Could not determine" = unbounded
- This is the only call that reasons about the full picture.

## Control Flow (Python)

```
plan_leads = llm_plan(issue, code, hints)

findings = {}
tool_cache = {}
for lead in plan_leads:             # could parallelize later
    result = investigate(lead, tool_cache, max_tools=3)
    findings[lead.id] = result

verdict = llm_synthesize(issue, code, findings)
```

## What This Fixes

| v20 Problem | Orchestrated Solution |
|---|---|
| Duplicate tool calls (28+ in Run 50) | Python deduplicates globally via tool_cache |
| Infinite loops (29 rounds, no verdict) | Hard cap: 3 tools per lead, finite leads |
| SUFFICIENCY never flips YES | No sufficiency tracking — planner decides upfront |
| Evidence extraction captures junk | Structured JSON output per agent |
| Soft tool limit ignored | No soft limits — Python controls all tool execution |
| Model reasons + manages state simultaneously | Reasoning (LLM) separated from state (Python) |

## Open Questions

1. **Can leads spawn sub-leads?** Lean yes, within the 3-tool budget.
2. **Should Phase 3 be allowed to request a second investigation round?**
   Maybe — if synthesis identifies a critical gap, run one more targeted lead.
3. **Parallelism** — leads are independent; could run concurrently. Worth it?
4. **How to handle the planner producing bad leads?** Cap at 5 leads max;
   if planner returns garbage, fall back to a default lead set.
5. **Token budget** — estimate ~$0.10–0.20 per finding (comparable to v15).
