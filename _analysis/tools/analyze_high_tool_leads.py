"""Analyze leads with 9+ tool calls to understand tool usage patterns."""
import json
import os
import csv

LEADS_CSV = "output/results_orchestrated/c/run_leads_20260325_112539.csv"
BASE = "output/results_orchestrated/c"

# Identify leads with 9+ tool calls
rows = list(csv.DictReader(open(LEADS_CSV)))
high = [r for r in rows if int(float(r['tool_calls'])) >= 9]

for lead_row in high:
    cid = lead_row['cid']
    lid = lead_row['lead_id']
    tc = int(float(lead_row['tool_calls']))
    cached = int(float(lead_row.get('tool_calls_cached', '0')))
    found = int(float(lead_row.get('tool_calls_found', '0')))
    rounds = int(float(lead_row['follow_up_rounds']))
    conf = lead_row.get('confidence', '?')

    # Find latest run folder
    cid_dir = os.path.join(BASE, cid)
    run_dirs = sorted([d for d in os.listdir(cid_dir) if d.startswith('run_')])
    latest_run = run_dirs[-1]
    run_path = os.path.join(cid_dir, latest_run)

    print(f"{'='*80}")
    print(f"CID {cid}, Lead {lid} — {tc} tools ({cached} cached, {found} found), "
          f"{rounds} rounds, confidence={conf}")
    print(f"Run folder: {latest_run}")
    print(f"{'='*80}")

    # Try to read the raw investigation file
    raw_file = os.path.join(run_path, f"2_{lid}_raw.json")
    final_file = os.path.join(run_path, f"2_{lid}_final.json")
    summary_file = os.path.join(run_path, f"2_{lid}_summary.json")

    # Read final to get the lead description and conclusion
    if os.path.exists(final_file):
        with open(final_file) as f:
            final = json.load(f)
        print(f"\nLead description: {str(final.get('lead', {}).get('description', '?'))[:200]}")
        print(f"Conclusion confidence: {final.get('confidence', '?')}")
        print(f"Conclusion verdict: {final.get('verdict', '?')}")
        finding = final.get('finding', '')
        if finding:
            print(f"Finding (first 300 chars): {str(finding)[:300]}")

    # Read raw to get tool call sequence
    if os.path.exists(raw_file):
        with open(raw_file) as f:
            raw = json.load(f)

        print(f"\nRaw JSON top keys: {list(raw.keys())}")

        # Try different structures
        tools = raw.get('tools_executed', [])
        if tools:
            print(f"\nTool calls executed ({len(tools)}):")
            for i, t in enumerate(tools):
                if isinstance(t, dict):
                    tool_name = t.get('tool_name', t.get('name', t.get('tool', '?')))
                    round_num = t.get('round', '?')
                    args = t.get('arguments', t.get('args', t.get('input', {})))
                    cached_flag = t.get('cached', False)
                    found_flag = t.get('found', None)
                    result_preview = str(t.get('result', t.get('output', '')))[:150]
                    
                    args_summary = ''
                    if isinstance(args, dict):
                        args_summary = ', '.join(f'{k}={str(v)[:60]}' for k, v in args.items())
                    else:
                        args_summary = str(args)[:150]
                    
                    status = ''
                    if cached_flag:
                        status += ' [CACHED]'
                    if found_flag is not None:
                        status += f' [found={found_flag}]'
                    
                    print(f"  [{i+1}] Round {round_num}: {tool_name}{status}")
                    print(f"       Args: {args_summary}")
                    if result_preview and result_preview != 'None':
                        print(f"       Result: {result_preview}")
                    print()

        # Also check if there are messages with tool_calls
        messages = raw.get('messages', [])
        if messages and not tools:
            print(f"\nMessages ({len(messages)}):")
            tc_count = 0
            for i, msg in enumerate(messages):
                if not isinstance(msg, dict):
                    continue
                role = msg.get('role', '')
                if role == 'assistant' and msg.get('tool_calls'):
                    for tc_item in msg['tool_calls']:
                        fn = tc_item.get('function', {})
                        name = fn.get('name', '?')
                        tc_count += 1
                        args_str = str(fn.get('arguments', ''))[:200]
                        print(f"  [{tc_count}] msg[{i}] {name}")
                        print(f"       Args: {args_str}")
                elif role == 'tool':
                    content = str(msg.get('content', ''))[:100]
                    print(f"       Result[{i}]: {content}")

        # Check the conversation rounds
        rounds_data = raw.get('rounds', [])
        if rounds_data:
            print(f"\nRounds data ({len(rounds_data)}):")
            for r in rounds_data:
                rnum = r.get('round', '?')
                tool_calls_in_round = r.get('tool_calls', [])
                reasoning = str(r.get('reasoning', ''))[:200]
                print(f"  Round {rnum}: {len(tool_calls_in_round)} tool calls")
                if reasoning:
                    print(f"    Reasoning: {reasoning}")
                for tc_item in tool_calls_in_round:
                    tname = tc_item.get('tool_name', tc_item.get('name', '?'))
                    targs = tc_item.get('arguments', tc_item.get('args', {}))
                    if isinstance(targs, dict):
                        targs_s = ', '.join(f'{k}={str(v)[:50]}' for k, v in targs.items())
                    else:
                        targs_s = str(targs)[:150]
                    cached_f = tc_item.get('cached', False)
                    found_f = tc_item.get('found', None)
                    status = ''
                    if cached_f:
                        status += ' [CACHED]'
                    if found_f is not None:
                        status += f' [found={found_f}]'
                    print(f"    - {tname}{status}: {targs_s}")

    # Check tool_calls.csv if available
    tc_csv = os.path.join(run_path, "tool_calls.csv")
    if os.path.exists(tc_csv):
        print(f"\n--- tool_calls.csv for lead {lid} ---")
        tc_rows = list(csv.DictReader(open(tc_csv)))
        lead_tc = [r for r in tc_rows if r.get('lead_id', '') == lid or r.get('lead', '') == lid]
        if not lead_tc:
            # Maybe not filtered by lead
            lead_tc = tc_rows
        print(f"Total tool call rows: {len(lead_tc)} (filtered for lead {lid})")
        for r in lead_tc[:20]:
            print(f"  {r}")

    # Read summary for high-level view
    if os.path.exists(summary_file):
        with open(summary_file) as f:
            summary = json.load(f)
        print(f"\nSummary keys: {list(summary.keys())}")
        print(f"Summary (first 500 chars): {json.dumps(summary, indent=2)[:500]}")

    print("\n")

# Also check the audit files
for lead_row in high:
    cid = lead_row['cid']
    lid = lead_row['lead_id']
    cid_dir = os.path.join(BASE, cid)
    run_dirs = sorted([d for d in os.listdir(cid_dir) if d.startswith('run_')])
    latest_run = run_dirs[-1]
    run_path = os.path.join(cid_dir, latest_run)
    
    audit_file = os.path.join(run_path, f"2_{lid}_audit.json")
    if os.path.exists(audit_file):
        print(f"=== AUDIT: CID {cid} Lead {lid} ===")
        with open(audit_file) as f:
            audit = json.load(f)
        print(f"Audit keys: {list(audit.keys())}")
        print(json.dumps(audit, indent=2)[:2000])
        print()
