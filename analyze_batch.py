"""Quick analysis of the 20260323 batch replay results."""
import csv, collections

# Read combined tool_calls
tc = list(csv.DictReader(open('output/results_orchestrated/c/run_tool_calls_batch_20260323.csv')))
print(f"Total tool calls: {len(tc)}")

# Tool call counts by tool
by_tool = collections.Counter(r['tool'] for r in tc)
print("\nTool call breakdown:")
for tool, cnt in by_tool.most_common():
    found_ct = sum(1 for r in tc if r['tool'] == tool and r.get('found', '') == 'True')
    pct = 100 * found_ct / cnt if cnt else 0
    print(f"  {tool}: {cnt} calls, {found_ct} found ({pct:.0f}%)")

# Read leads
leads = list(csv.DictReader(open('output/results_orchestrated/c/run_leads_batch_20260323.csv')))
print(f"\nLeads: {len(leads)}")

# Old tool call counts (from the batch script selection)
old_tc = {
    (25232, 3): 12, (27241, 3): 12,
    (27724, 1): 13, (27724, 2): 13, (27724, 3): 13,
    (22768, 1): 13, (21656, 1): 12, (27054, 1): 12,
    (25987, 1): 12, (25987, 2): 12, (25987, 3): 10,
    (20212, 1): 10, (20212, 2): 13, (20212, 3): 13,
    (29415, 2): 14,
}

print(f"\n{'CID':>6} {'L':>2} {'Old TC':>6} {'New TC':>6} {'Saved':>6} {'Cost':>8} {'Conf':>6}")
print("-" * 50)
total_old = 0
total_new = 0
total_cost = 0.0
for l in leads:
    cid = int(l['cid'])
    lid = int(l['lead_id'])
    new_tc = int(l['tool_calls'])
    cost = float(l['estimated_cost_usd'])
    conf = l.get('confidence', '?')
    o = old_tc.get((cid, lid), '?')
    saved = o - new_tc if isinstance(o, int) else '?'
    total_old += o if isinstance(o, int) else 0
    total_new += new_tc
    total_cost += cost
    print(f"{cid:>6} {lid:>2} {str(o):>6} {new_tc:>6} {str(saved):>6} ${cost:>7.4f} {conf:>6}")

print("-" * 50)
print(f"{'TOTAL':>9} {total_old:>6} {total_new:>6} {total_old - total_new:>6} ${total_cost:>7.4f}")
pct_reduction = 100 * (total_old - total_new) / total_old if total_old else 0
print(f"\nTool call reduction: {total_old} -> {total_new} ({pct_reduction:.0f}% fewer)")
print(f"Total batch cost: ${total_cost:.4f}")
