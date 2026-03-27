"""One-shot script to extract code from existing _final.json and create 2_initial_code.json."""
import json
import re

with open(r'output\results_orchestrated\c\15518\run_001\2_1_final.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

user_msg = data['messages'][1]['content']

# Find code between triple backtick fences after "## Flagged Code"
m = re.search(r'## Flagged Code\n```\n(.*?)\n```', user_msg, re.DOTALL)
if not m:
    # Try alternate: maybe the ``` has no trailing newline before assignment
    m = re.search(r'## Flagged Code\n```\n(.*?)```', user_msg, re.DOTALL)

if m:
    code = m.group(1).rstrip('\n')
    print(f'Extracted code ({len(code)} chars):')
    print(code[:200])
    with open(r'output\results_orchestrated\c\15518\run_001\2_initial_code.json', 'w', encoding='utf-8') as f:
        json.dump({'code': code}, f, indent=2, ensure_ascii=False)
    print('\nWrote 2_initial_code.json')
else:
    print('Could not find code block. Content starts with:')
    print(repr(user_msg[:200]))
    # Fallback: just grab from "file:" to end of function
    idx = user_msg.find('file:')
    if idx >= 0:
        end = user_msg.find('}\n', idx)
        code = user_msg[idx:end+1]
        print(f'\nFallback extracted ({len(code)} chars):')
        print(code[:200])
        with open(r'output\results_orchestrated\c\15518\run_001\2_initial_code.json', 'w', encoding='utf-8') as f:
            json.dump({'code': code}, f, indent=2, ensure_ascii=False)
        print('\nWrote 2_initial_code.json (fallback)')
