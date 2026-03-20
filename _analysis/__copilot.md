# _analysis — Copilot Context

This folder benchmarks Vulnhalla (parent dir) against Coverity findings. Each subfolder has its own docs — read those for details.

## How to Run Vulnhalla

### 1. Config — `.env` file in repo root (copy from `.env.example`)
Required vars: `PROVIDER`, `MODEL`, `<PROVIDER>_API_KEY` (e.g. `OPENAI_API_KEY`, `AZURE_OPENAI_API_KEY`).
Providers: openai, azure, gemini, bedrock, anthropic, mistral, groq, ollama.

### 2. Database layout — Vulnhalla expects a CodeQL database directory containing:
- `issues.csv` — findings to analyze (cols: name, help, type, message, file, start_line, start_offset, end_line, end_offset). See `zForLLM/issues-csv-format.md` for full spec.
- `FunctionTree.csv` — function boundaries from CodeQL (function_name, file, start_line, function_id, end_line, caller_id).
- `src.zip` — source code archive for code extraction.

### 3. Run (Step 5.2)
See `x03_run_vulnhalla/step5_llm_analysis.md` for full details.
```powershell
# Default prompts (system_messages.yaml)
python -c "from src.vulnhalla import IssueAnalyzer; analyzer = IssueAnalyzer(lang='c'); analyzer.run('C:\\code\\codeQL_CoD\\codeql')"

# Specify a prompt file
python -c "from src.vulnhalla import IssueAnalyzer; analyzer = IssueAnalyzer(lang='c', prompt_file='system_messages.v12-verify-claims.yaml'); analyzer.run('C:\\code\\codeQL_CoD\\codeql')"
```
Prompt files live in `data/prompts/`. The `prompt_file` param selects which system messages YAML to use.

### 4. Results → `output/results/c/{CID}/`
- `{id}_raw.json` — prompt + metadata sent to LLM
- `{id}_final.json` — full LLM conversation + classification
- `{id}_summary.json` — per-CID copy of run summary (includes `prompt_file`, cost, tokens, decision)
- `run_summary.json` — global run summary at `output/results/c/run_summary.json` (overwritten each run)
- Classification codes: **1337** = true positive, **1007** = false positive, **7331** = need more data

### 5. Analyze results
After a run completes, follow `_analysis/CID-analysis-guide.md` to review and interpret LLM classifications.

### 6. View results UI
```powershell
python examples\ui_example.py
```

## Folder Quick Ref
- **x01/** — Filter Coverity export into working set. **x02/** — Correct line numbers, generate issues.csv. **x03/** — Run & review docs.
- **tools/** — Utility scripts. **z-prefixed/** — Reference/archive.
- Post-run analysis guide: `CID-analysis-guide.md`