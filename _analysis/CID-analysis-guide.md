# CID-Analysis Guide

## Scope
Analyze ONLY the CIDs from the **latest run**. Check `output\results\c\run_summary.json` first — it tells you exactly which CIDs were in this run and how many findings. Do NOT go back and analyze CIDs from prior runs unless explicitly asked.

## Data Sources
- **Primary:** `output\results\c\run_summary.json` — has cost, tokens, decisions, duration, **prompt_file**
- **Per-CID summary:** `output\results\c\{CID}\{id}_summary.json` — same as run_summary but stored with the CID output files
- **Conversation detail:** `output\results\c\{CID}\{id}_final.json` — full LLM conversation log
- **Input context:** `output\results\c\{CID}\{id}_raw.json` — prompt, function info, model metadata
- **Cost reference:** See `POST_RUN_ANALYSIS_GUIDE.md` for pricing and status codes

## Per-CID Analysis Checklist
For each CID in the latest run:

1. **Cost & prompt** — estimated cost in $ for the run total and per finding, and which `prompt_file` was used (from `{id}_summary.json` or `run_summary.json`)
2. **Tool call deep-dive** — read `_final.json` and analyze EACH tool call in detail:
   - Create a table: tool name, args, what it returned, was it needed?
   - Were any redundant (same tool called twice with same args)?
   - Did it fail to ask for anything it should have? List potential missing requests and whether they would have mattered.
   - See CID-15518-analysis.md "Run 5 Tool Call Breakdown" for the expected level of detail.
3. **Conclusion quality** —
   - present the exact conlusion the llm stated with its reasoning.
   - Did it have all the info it needed to draw a conclusion? Why/why not?
   - Did it reach the correct conclusion? Why/why not?
4. **Suggested improvements** — anything that could make the analysis better

## Output
- Save analysis in `CID-<cid>-analysis.md` as a new section for this round
- If that document doesn't exist, also analyze prior rounds (if any) and add them to that document
- Compare different runs in a summary table in that document
- **Share the full analysis in chat** — include the run comparison table, tool call breakdown, conclusion assessment, and suggested improvements. The user should not have to open the document to see results.