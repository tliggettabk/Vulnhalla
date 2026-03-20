"""Check whether LLM includes reasoning content alongside tool call requests."""
import ast, sys

path = sys.argv[1] if len(sys.argv) > 1 else "output/results/c/15518/21_final.json"
with open(path, "r", encoding="utf-8") as f:
    data = ast.literal_eval(f.read())

msgs = data if isinstance(data, list) else data.get("messages", data.get("conversation", []))

for i, m in enumerate(msgs):
    role = m.get("role", "?")
    tc = m.get("tool_calls") or []
    content = m.get("content", "") or ""
    if tc:
        print(f"=== msg[{i}] role={role}  tool_calls={len(tc)}  has_content={bool(content.strip())}")
        if content.strip():
            preview = content[:500]
            print(f"  REASONING:\n    {preview}")
        else:
            print("  REASONING: (none)")
        for t in tc:
            fn = t.get("function", {}).get("name", "?")
            args = t.get("function", {}).get("arguments", "?")
            print(f"  TOOL: {fn}({args})")
        print()
