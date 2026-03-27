"""
Analyze "not found" fallback patterns across all orchestrated runs.

Finds cases where:
1. A tool call returned "not found" or similar failure
2. The SAME entity name was retried with a DIFFERENT tool (cross-tool fallback)
3. The SAME tool was retried with name variants (cosmetic retry anti-pattern)
"""

import json
import os
import re
from pathlib import Path
from collections import defaultdict

BASE = Path(r"C:\Users\tliggett\source\repos\Vulnhalla\output\results_orchestrated\c")
CIDS = ["15518", "19309", "27190", "27528", "27746", "29391"]

# Patterns that indicate "not found" in tool results
NOT_FOUND_PATTERNS = [
    r"not found",
    r"no function found",
    r"no (?:class|struct|type|macro|global|enum|variable|definition) found",
    r"no results",
    r"could not find",
    r"no match",
    r"function .+ not found",
    r"not found in (?:the )?(?:codebase|database|index)",
]

NOT_FOUND_RE = re.compile("|".join(NOT_FOUND_PATTERNS), re.IGNORECASE)

# Patterns that indicate the tool SUCCEEDED (returned actual code)
SUCCESS_PATTERNS = [
    r"^file:\s",           # Tool returned source code with file path header
    r"^Source code for",   # Another success header
    r"^Macro\s+\S+\s+expands to",  # Macro expansion success
    r"^Global var\s+\S+\s+defined",  # Global var found
]
SUCCESS_RE = re.compile("|".join(SUCCESS_PATTERNS), re.IGNORECASE)


def is_not_found(content: str) -> bool:
    """Check if tool result indicates entity was not found."""
    if not content:
        return False
    # If the result starts with a success indicator, it's NOT a "not found"
    # even if the returned source code contains "not found" as a comment
    if SUCCESS_RE.search(content.strip()):
        return False
    # Check for explicit not-found error messages
    # Only check the FIRST few lines (the tool error message, not embedded code)
    first_lines = "\n".join(content.strip().split("\n")[:3])
    if NOT_FOUND_RE.search(first_lines):
        return True
    return False


def extract_entity_name(args_str: str) -> str | None:
    """Extract the primary entity name from tool call arguments."""
    try:
        args = json.loads(args_str)
    except (json.JSONDecodeError, TypeError):
        return None
    # Try common argument names
    for key in ["function_name", "class_name", "object_name", "macro_name", "name",
                "type_name", "global_name", "global_var_name", "variable_name",
                "enum_name", "struct_name", "symbol_name", "identifier"]:
        if key in args:
            return args[key]
    return None


def extract_tool_name(args_str: str) -> str | None:
    """Extract tool name from arguments (for nested calls)."""
    try:
        args = json.loads(args_str)
    except (json.JSONDecodeError, TypeError):
        return None
    return args.get("tool")


def normalize_name(name: str) -> str:
    """Normalize entity name for comparison (strip namespace prefixes, etc.)."""
    # Remove trailing template params
    name = re.sub(r"<[^>]*>$", "", name)
    # Get the base name (last component after ::)
    parts = name.split("::")
    return parts[-1].lower().strip()


def get_latest_run(cid: str) -> Path | None:
    """Get the latest run directory for a CID."""
    cid_dir = BASE / cid
    if not cid_dir.exists():
        return None
    runs = sorted([d for d in cid_dir.iterdir() if d.is_dir() and d.name.startswith("run_")])
    return runs[-1] if runs else None


def analyze_lead_file(filepath: Path) -> dict:
    """Analyze a single lead final.json file for fallback patterns."""
    results = {
        "filepath": str(filepath),
        "total_tool_calls": 0,
        "not_found_results": [],
        "cross_tool_fallbacks": [],
        "cosmetic_retries": [],
    }

    try:
        data = json.load(open(filepath, encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        results["error"] = str(e)
        return results

    messages = data.get("messages", [])

    # Build ordered list of (tool_name, entity_name, result_content, result_is_not_found)
    tool_sequence = []

    i = 0
    while i < len(messages):
        msg = messages[i]
        if msg.get("role") == "assistant" and "tool_calls" in msg:
            for tc in msg["tool_calls"]:
                fn_name = tc["function"]["name"]
                fn_args = tc["function"]["arguments"]
                entity = extract_entity_name(fn_args)
                tc_id = tc.get("id", "")

                # Find matching tool result
                result_content = None
                result_not_found = False
                for j in range(i + 1, min(i + 10, len(messages))):
                    if messages[j].get("role") == "tool" and messages[j].get("tool_call_id") == tc_id:
                        result_content = messages[j].get("content", "")
                        result_not_found = is_not_found(result_content)
                        break

                tool_sequence.append({
                    "tool": fn_name,
                    "entity": entity,
                    "args_raw": fn_args,
                    "result": result_content,
                    "not_found": result_not_found,
                    "msg_index": i,
                })
                results["total_tool_calls"] += 1
        i += 1

    # Now analyze the sequence for fallback patterns
    for idx, entry in enumerate(tool_sequence):
        if not entry["not_found"]:
            continue

        results["not_found_results"].append({
            "tool": entry["tool"],
            "entity": entry["entity"],
            "result_snippet": (entry["result"] or "")[:200],
        })

        if not entry["entity"]:
            continue

        base_name = normalize_name(entry["entity"])

        # Look at subsequent tool calls for the same or similar entity
        for future_idx in range(idx + 1, min(idx + 6, len(tool_sequence))):
            future = tool_sequence[future_idx]
            if not future["entity"]:
                continue

            future_base = normalize_name(future["entity"])

            # Check if same entity or very similar (e.g. with/without namespace)
            same_entity = (
                base_name == future_base
                or entry["entity"] == future["entity"]
                or base_name in future_base
                or future_base in base_name
            )

            if not same_entity:
                continue

            if future["tool"] != entry["tool"]:
                # CROSS-TOOL FALLBACK
                results["cross_tool_fallbacks"].append({
                    "original_tool": entry["tool"],
                    "fallback_tool": future["tool"],
                    "entity": entry["entity"],
                    "fallback_entity": future["entity"],
                    "fallback_succeeded": not future["not_found"],
                    "original_result_snippet": (entry["result"] or "")[:150],
                    "fallback_result_snippet": (future["result"] or "")[:150],
                })
                break  # Only count first fallback per not-found
            else:
                # SAME-TOOL COSMETIC RETRY (name variant)
                if future["entity"] != entry["entity"]:
                    results["cosmetic_retries"].append({
                        "tool": entry["tool"],
                        "original_name": entry["entity"],
                        "retry_name": future["entity"],
                        "retry_succeeded": not future["not_found"],
                        "original_result_snippet": (entry["result"] or "")[:150],
                        "retry_result_snippet": (future["result"] or "")[:150],
                    })
                    break

    return results


def main():
    all_results = []
    total_tool_calls = 0
    total_not_found = 0
    total_cross_fallback = 0
    total_cross_fallback_success = 0
    total_cross_fallback_fail = 0
    total_cosmetic_retry = 0
    total_cosmetic_retry_success = 0
    total_cosmetic_retry_fail = 0
    tool_pair_counts = defaultdict(lambda: {"success": 0, "fail": 0})

    print("=" * 80)
    print("FALLBACK PATTERN ANALYSIS - Orchestrated Runs")
    print("=" * 80)

    for cid in CIDS:
        latest_run = get_latest_run(cid)
        if not latest_run:
            print(f"\nCID {cid}: No run directory found")
            continue

        print(f"\n{'='*80}")
        print(f"CID {cid} / {latest_run.name}")
        print(f"{'='*80}")

        # Find all lead final files (2_*_final.json)
        lead_files = sorted(latest_run.glob("2_*_final.json"))
        lead_files = [f for f in lead_files if f.name != "2_initial_code.json"]

        for lead_file in lead_files:
            lead_name = lead_file.stem.replace("_final", "")
            result = analyze_lead_file(lead_file)
            all_results.append({"cid": cid, "run": latest_run.name, "lead": lead_name, **result})

            total_tool_calls += result["total_tool_calls"]
            total_not_found += len(result["not_found_results"])
            total_cross_fallback += len(result["cross_tool_fallbacks"])
            total_cosmetic_retry += len(result["cosmetic_retries"])

            if result["not_found_results"] or result["cross_tool_fallbacks"] or result["cosmetic_retries"]:
                print(f"\n  Lead {lead_name} ({result['total_tool_calls']} tool calls):")

            if result["not_found_results"]:
                print(f"    Not-found results: {len(result['not_found_results'])}")
                for nf in result["not_found_results"]:
                    print(f"      - {nf['tool']}({nf['entity']})")
                    print(f"        Result: {nf['result_snippet'][:120]}")

            for fb in result["cross_tool_fallbacks"]:
                status = "SUCCESS" if fb["fallback_succeeded"] else "FAILED"
                pair = f"{fb['original_tool']} -> {fb['fallback_tool']}"
                print(f"    CROSS-TOOL FALLBACK [{status}]: {pair}")
                print(f"      Entity: {fb['entity']}")
                if fb["entity"] != fb["fallback_entity"]:
                    print(f"      Fallback entity: {fb['fallback_entity']}")
                print(f"      Original result: {fb['original_result_snippet'][:100]}")
                print(f"      Fallback result: {fb['fallback_result_snippet'][:100]}")

                if fb["fallback_succeeded"]:
                    total_cross_fallback_success += 1
                    tool_pair_counts[pair]["success"] += 1
                else:
                    total_cross_fallback_fail += 1
                    tool_pair_counts[pair]["fail"] += 1

            for cr in result["cosmetic_retries"]:
                status = "SUCCESS" if cr["retry_succeeded"] else "FAILED"
                print(f"    COSMETIC RETRY [{status}]: {cr['tool']}")
                print(f"      Original: {cr['original_name']}")
                print(f"      Retry:    {cr['retry_name']}")
                print(f"      Original result: {cr['original_result_snippet'][:100]}")
                print(f"      Retry result: {cr['retry_result_snippet'][:100]}")

                if cr["retry_succeeded"]:
                    total_cosmetic_retry_success += 1
                else:
                    total_cosmetic_retry_fail += 1

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total tool calls analyzed:           {total_tool_calls}")
    print(f"Total 'not found' results:           {total_not_found}")
    print(f"  Led to cross-tool fallback:        {total_cross_fallback}")
    print(f"    - Fallback SUCCEEDED:            {total_cross_fallback_success}")
    print(f"    - Fallback FAILED:               {total_cross_fallback_fail}")
    print(f"  Led to cosmetic retry (same tool): {total_cosmetic_retry}")
    print(f"    - Retry SUCCEEDED:               {total_cosmetic_retry_success}")
    print(f"    - Retry FAILED:                  {total_cosmetic_retry_fail}")
    print(f"  No follow-up attempt:              {total_not_found - total_cross_fallback - total_cosmetic_retry}")

    if tool_pair_counts:
        print(f"\nCross-tool fallback pairs:")
        for pair, counts in sorted(tool_pair_counts.items(), key=lambda x: sum(x[1].values()), reverse=True):
            total = counts["success"] + counts["fail"]
            print(f"  {pair}: {total} total ({counts['success']} succeeded, {counts['fail']} failed)")

    print()


if __name__ == "__main__":
    main()
