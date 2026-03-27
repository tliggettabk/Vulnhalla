import json

d = json.load(open(r'output\results_orchestrated\c\27528\run_002\2_3_final_v2.json'))
msgs = d.get('messages', [])

# Match tool calls to their results
tool_names = []
for m in msgs:
    if m.get('role') == 'assistant' and m.get('tool_calls'):
        for tc in m['tool_calls']:
            fn = tc['function']['name']
            args = json.loads(tc['function']['arguments'])
            name_arg = args.get('function_name') or args.get('macro_name') or args.get('global_var_name') or args.get('object_name') or '?'
            tool_names.append((fn, name_arg))

i = 0
for m in msgs:
    if m.get('role') == 'tool':
        content = str(m.get('content', ''))
        found = 'not found' not in content.lower()
        status = 'FOUND' if found else 'NOT FOUND'
        if i < len(tool_names):
            tool, name = tool_names[i]
        else:
            tool, name = '?', '?'
        loc = len(content)
        print(f'[{status:9s}] {tool}({name}) -> {loc} chars')
        i += 1
