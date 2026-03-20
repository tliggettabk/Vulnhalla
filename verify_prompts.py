"""
Compare YAML-loaded prompts against hardcoded fallback values character-by-character.
Reports any differences so YAML files can be corrected to produce identical output.
"""
import sys, tempfile, difflib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.prompt_loader import PromptLoader

# Load from YAML
yaml_loader = PromptLoader()

# Load fallbacks (empty dir → all methods return hardcoded defaults)
with tempfile.TemporaryDirectory() as td:
    fallback_loader = PromptLoader(prompts_dir=td)

    diffs_found = False

    # --- 1. System Messages ---
    yaml_msgs = yaml_loader.load_system_messages()
    # Build hardcoded messages by importing the fallback inline from LLMAnalyzer
    # We need the ACTUAL hardcoded list. Create an analyzer with empty loader to get fallbacks.
    from src.llm.llm_analyzer import LLMAnalyzer
    fallback_analyzer = LLMAnalyzer(prompt_loader=fallback_loader)
    hardcoded_msgs = fallback_analyzer.MESSAGES

    print("=" * 80)
    print("SYSTEM MESSAGES COMPARISON")
    print("=" * 80)
    if yaml_msgs is None:
        print("ERROR: YAML returned None for system messages!")
        diffs_found = True
    elif len(yaml_msgs) != len(hardcoded_msgs):
        print(f"ERROR: Count mismatch — YAML has {len(yaml_msgs)}, hardcoded has {len(hardcoded_msgs)}")
        diffs_found = True
    else:
        for i, (ym, hm) in enumerate(zip(yaml_msgs, hardcoded_msgs)):
            yc = ym["content"]
            hc = hm["content"]
            if yc == hc:
                print(f"  Message {i+1}: IDENTICAL ✓")
            else:
                diffs_found = True
                print(f"  Message {i+1}: DIFFERENT ✗")
                for line in difflib.unified_diff(
                    hc.splitlines(keepends=True),
                    yc.splitlines(keepends=True),
                    fromfile=f"hardcoded[{i}]",
                    tofile=f"yaml[{i}]",
                    lineterm=""
                ):
                    print(f"    {line}")

    # --- 2. Tools ---
    yaml_tools = yaml_loader.load_tools()
    hardcoded_tools = fallback_analyzer.tools

    print()
    print("=" * 80)
    print("TOOLS COMPARISON")
    print("=" * 80)
    if yaml_tools is None:
        print("ERROR: YAML returned None for tools!")
        diffs_found = True
    elif len(yaml_tools) != len(hardcoded_tools):
        print(f"ERROR: Count mismatch — YAML has {len(yaml_tools)}, hardcoded has {len(hardcoded_tools)}")
        diffs_found = True
    else:
        import json
        for i, (yt, ht) in enumerate(zip(yaml_tools, hardcoded_tools)):
            yj = json.dumps(yt, sort_keys=True)
            hj = json.dumps(ht, sort_keys=True)
            name = yt["function"]["name"]
            if yj == hj:
                print(f"  Tool '{name}': IDENTICAL ✓")
            else:
                diffs_found = True
                print(f"  Tool '{name}': DIFFERENT ✗")
                for line in difflib.unified_diff(
                    json.dumps(ht, indent=2, sort_keys=True).splitlines(keepends=True),
                    json.dumps(yt, indent=2, sort_keys=True).splitlines(keepends=True),
                    fromfile=f"hardcoded[{name}]",
                    tofile=f"yaml[{name}]",
                    lineterm=""
                ):
                    print(f"    {line}")

    # --- 3. Conversation Control strings ---
    print()
    print("=" * 80)
    print("CONVERSATION CONTROL COMPARISON")
    print("=" * 80)

    checks = [
        ("retry_nudge", yaml_loader.get_retry_nudge(), fallback_loader.get_retry_nudge()),
        ("tool_limit_warning", yaml_loader.get_tool_limit_warning(), fallback_loader.get_tool_limit_warning()),
        ("caller_preamble(testFunc)", yaml_loader.get_caller_function_preamble("testFunc"), fallback_loader.get_caller_function_preamble("testFunc")),
        ("fuzzy_class_note(A,B)", yaml_loader.get_fuzzy_class_note("A", "B"), fallback_loader.get_fuzzy_class_note("A", "B")),
        ("map_func_args_prompt(c1,c2)", yaml_loader.get_map_func_args_prompt("CALLER_CODE", "CALLEE_CODE"), fallback_loader.get_map_func_args_prompt("CALLER_CODE", "CALLEE_CODE")),
        ("invalid_tool_message(t,a)", yaml_loader.get_invalid_tool_message("bad_tool", {"x": 1}), fallback_loader.get_invalid_tool_message("bad_tool", {"x": 1})),
        ("status_codes", str(yaml_loader.get_status_codes()), str(fallback_loader.get_status_codes())),
        ("max_tool_calls", str(yaml_loader.get_max_tool_calls()), str(fallback_loader.get_max_tool_calls())),
    ]

    for label, yaml_val, hardcoded_val in checks:
        if yaml_val == hardcoded_val:
            print(f"  {label}: IDENTICAL ✓")
        else:
            diffs_found = True
            print(f"  {label}: DIFFERENT ✗")
            for line in difflib.unified_diff(
                hardcoded_val.splitlines(keepends=True),
                yaml_val.splitlines(keepends=True),
                fromfile="hardcoded",
                tofile="yaml",
                lineterm=""
            ):
                print(f"    {line}")

    print()
    if diffs_found:
        print("❌ DIFFERENCES FOUND — YAML files need corrections above.")
        sys.exit(1)
    else:
        print("✅ ALL IDENTICAL — YAML files produce the exact same text as hardcoded values.")
        sys.exit(0)
