import json, os

results_dir = r'output\results_orchestrated\c'

all_leads = []

for cid in sorted(os.listdir(results_dir)):
    cid_dir = os.path.join(results_dir, cid)
    if not os.path.isdir(cid_dir):
        continue
    runs = sorted([d for d in os.listdir(cid_dir) if d.startswith('run_')])
    run = runs[-1]
    run_dir = os.path.join(cid_dir, run)

    with open(os.path.join(run_dir, 'run_summary.json'), encoding='utf-8') as f:
        summary = json.load(f)

    total_cost = summary.get('estimated_cost_usd', 0)
    total_tokens = summary.get('total_tokens', 0)
    leads_count = summary.get('leads_count', 0)

    lead_data = []
    for finding in summary.get('findings', []):
        lid = finding.get('lead_id', finding.get('id', '?'))
        loc = finding.get('loc', {})
        ld = {
            'cid': cid,
            'id': lid,
            'cost': finding.get('estimated_cost_usd', 0),
            'tokens': finding.get('total_tokens', 0),
            'rounds': finding.get('follow_up_rounds', 0),
            'tools': finding.get('tool_calls', 0),
            'loc_total': loc.get('total', 0),
            'loc_tools': loc.get('tool_total', 0),
            'loc_initial': loc.get('initial', 0),
            'avg_loc': loc.get('avg_per_tool_call', 0),
        }
        lead_data.append(ld)
        all_leads.append(ld)

    agg_loc = sum(l['loc_total'] for l in lead_data)
    agg_loc_tools = sum(l['loc_tools'] for l in lead_data)

    print(f"=== CID {cid} ({run}) | {leads_count} leads | ${total_cost:.2f} | {total_tokens:,} tok | {agg_loc} LOC ({agg_loc_tools} from tools) ===")
    hdr = f"{'Lead':>5} {'Cost':>8} {'Tokens':>8} {'Rounds':>6} {'Tools':>5} {'LOCtot':>7} {'LOCtool':>7} {'Avg/cl':>6} {'$/LOC':>8}"
    print(hdr)
    print("-" * len(hdr))
    for l in lead_data:
        dpl = l['cost'] / l['loc_total'] if l['loc_total'] > 0 else 0
        print(f"{l['id']:>5} ${l['cost']:>7.3f} {l['tokens']:>8,} {l['rounds']:>6} {l['tools']:>5} {l['loc_total']:>7} {l['loc_tools']:>7} {l['avg_loc']:>6.0f} ${dpl:>7.4f}")
    if agg_loc > 0:
        print(f"  Aggregate: ${total_cost:.2f} / {agg_loc} LOC = ${total_cost/agg_loc:.4f}/LOC")
    print()

# Cross-CID summary
print("=" * 80)
print("CROSS-CID ANALYSIS")
print("=" * 80)

# Sort by $/LOC descending
for_sort = [l for l in all_leads if l['loc_total'] > 0]
for_sort.sort(key=lambda x: x['cost'] / x['loc_total'], reverse=True)

print(f"\n{'CID':>6} {'Lead':>5} {'Cost':>8} {'LOCtot':>7} {'$/LOC':>8} {'Rounds':>6} {'AvgLOC':>6}")
print("-" * 55)
for l in for_sort:
    dpl = l['cost'] / l['loc_total']
    print(f"{l['cid']:>6} {l['id']:>5} ${l['cost']:>7.3f} {l['loc_total']:>7} ${dpl:>7.4f} {l['rounds']:>6} {l['avg_loc']:>6.0f}")

# Correlation
costs = [l['cost'] for l in for_sort]
locs = [l['loc_total'] for l in for_sort]
tokens = [l['tokens'] for l in for_sort]
rounds = [l['rounds'] for l in for_sort]

def pearson(xs, ys):
    n = len(xs)
    if n < 2:
        return 0
    mx, my = sum(xs)/n, sum(ys)/n
    num = sum((x-mx)*(y-my) for x,y in zip(xs,ys))
    dx = sum((x-mx)**2 for x in xs)**0.5
    dy = sum((y-my)**2 for y in ys)**0.5
    return num/(dx*dy) if dx*dy > 0 else 0

print(f"\nCorrelations (Pearson r, n={len(for_sort)}):")
print(f"  cost vs LOC_total:  {pearson(costs, locs):.3f}")
print(f"  cost vs tokens:     {pearson(costs, tokens):.3f}")
print(f"  cost vs rounds:     {pearson(costs, rounds):.3f}")
print(f"  tokens vs LOC_total:{pearson(tokens, locs):.3f}")
print(f"  rounds vs LOC_total:{pearson(rounds, locs):.3f}")
