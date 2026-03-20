# Vulnhalla Post-Run Analysis Guide

**Purpose:** Instructions for AI assistants and humans to quickly analyze Vulnhalla LLM run results without tedious file parsing.

## Quick Start — After a Run Completes

### 1. Read the Run Summary (Primary Source)
```powershell
Get-Content "output\results\c\run_summary.json" | ConvertFrom-Json | Format-List
```

The `run_summary.json` file is written at the end of every Vulnhalla run. It contains **everything** needed for analysis:

| Field | Description |
|-------|-------------|
| `run_timestamp` | UTC ISO timestamp of when the run completed |
| `model` | LLM model used (e.g., `gpt-5.1-codex`, `gpt-4o`) |
| `provider` | Provider name (`azure`, `openai`, `gemini`) |
| `language` | Language analyzed (`c`, `cpp`, etc.) |
| `findings_processed` | Total number of findings sent to the LLM |
| `totals` | Aggregate stats: TP/FP/More Data counts, token usage, cost, duration |
| `averages_per_finding` | Per-finding averages for tokens and cost |
| `findings[]` | Array of per-finding detail objects |

### 2. Per-Finding Detail (in `findings[]` array)

Each finding object contains:

| Field | Description |
|-------|-------------|
| `cid` | The CID / issue name from issues.csv |
| `issue_type` | Vulnerability category |
| `decision` | Human-readable: `True Positive`, `False Positive`, or `LLM needs More Data` |
| `decision_code` | Last 4 chars of LLM response (contains status code) |
| `rounds` | Number of LLM conversation rounds |
| `tool_calls` | Number of tool-call rounds (each can have multiple tools) |
| `prompt_tokens` | Input tokens consumed for this finding |
| `completion_tokens` | Output tokens for this finding |
| `total_tokens` | prompt + completion |
| `estimated_cost_usd` | Actual cost from `litellm.completion_cost()` (0 if not available) |
| `duration_seconds` | Wall-clock time for this finding |
| `model` | Model name used |

## Status Codes Reference

| Code | Meaning | Classification |
|------|---------|----------------|
| `1337` | True Positive — real vulnerability | Exploitable security issue |
| `1007` | False Positive — not a real issue | Safe, no action needed |
| `7337-LEAN-VULN` | True Positive (lean analysis) | Exploitable |
| `7337-LEAN-SECURE` | False Positive (lean analysis) | Safe |
| `7331` | Need More Data | Insufficient info |
| `7337` | Conflicting evidence | Re-analysis recommended |
| `3713` | Need More Data variant | Insufficient info |

## Output File Structure

```
output/results/{lang}/
├── run_summary.json              ← START HERE — structured run report
├── {issue_type}/
│   ├── {id}_raw.json             ← Input: prompt, function info, model/provider metadata
│   └── {id}_final.json           ← Full LLM conversation log (all messages)
```

### `_raw.json` Fields
- `function_tree_file`: Path to FunctionTree.csv used
- `current_function`: The function dict containing the finding
- `db_path`: CodeQL database path
- `code_path`: Source code root path
- `prompt`: Exact prompt sent to the LLM
- `model`: Model name (e.g., `azure/gpt-5.1-codex`)
- `provider`: Provider name
- `temperature`, `top_p`: Sampling parameters used

### `_final.json` Format
Contains the full message history as a formatted string array. To find the final verdict:
```powershell
# Quick: get last status code from final conversation
$c = Get-Content "output\results\c\{CID}\{id}_final.json" -Raw
$m = [regex]::Matches($c, '\*\*(\d{4})\*\*')
$m[$m.Count - 1].Groups[1].Value  # Last status code = final answer
```

## Cost Estimation

### When `estimated_cost_usd` is available (litellm supports the model)
Read it directly from `run_summary.json` — it uses `litellm.completion_cost()` per API call.

### When `estimated_cost_usd` is 0 (model not in litellm pricing DB)
Estimate manually using token counts from the summary:

| Model | Input $/1K tokens | Output $/1K tokens |
|-------|-------------------|-------------------|
| gpt-4o | $0.0025 | $0.010 |
| gpt-4.1-mini | $0.0004 | $0.0016 |
| gpt-5.1-codex | ~$0.015 (est.) | ~$0.030 (est.) |

```
cost = (prompt_tokens × input_rate + completion_tokens × output_rate)
```

## Common Analysis Commands

```powershell
# Full summary
Get-Content "output\results\c\run_summary.json" -Raw | python -m json.tool

# Just decisions
(Get-Content "output\results\c\run_summary.json" | ConvertFrom-Json).findings | Select-Object cid, decision, rounds, total_tokens, estimated_cost_usd

# Total cost
(Get-Content "output\results\c\run_summary.json" | ConvertFrom-Json).totals

# Check specific CID conversation ending
$c = Get-Content "output\results\c\{CID}\{id}_final.json" -Raw
$c.Substring([Math]::Max(0, $c.Length - 1000))
```

## For AI Assistants

When the user asks to analyze results after a Vulnhalla run:

1. **First**: Read `output/results/{lang}/run_summary.json` — this has all token counts, costs, decisions, and timing
2. **Only if needed**: Read specific `_final.json` files for conversation analysis
3. **Do NOT** grep through `_final.json` files to count tokens — use the summary
4. **Cost**: Use `estimated_cost_usd` from the summary; fall back to manual calculation with token counts only if it's 0

This eliminates the need for multiple regex searches, file size estimates, and character counting that was previously required.
