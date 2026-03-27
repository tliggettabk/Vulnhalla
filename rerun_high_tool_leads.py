#!/usr/bin/env python3
"""Replay all leads from run_leads CSV that used more than 9 tool calls."""
import csv
import sys
import time
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent))

from src.vulnhalla import IssueAnalyzer

CSV_PATH = r"output\results_orchestrated\c\run_leads_20260322_114133.csv"
DB_PATH = r"C:\code\codeQL_CoD\codeql"
TOOL_CALL_THRESHOLD = 9

def main():
    # Parse CSV and filter
    leads_to_replay = []
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tc = int(row["tool_calls"])
            if tc > TOOL_CALL_THRESHOLD:
                leads_to_replay.append({
                    "cid": row["cid"],
                    "lead_id": row["lead_id"],
                    "tool_calls": tc,
                })

    print(f"Found {len(leads_to_replay)} leads with >{TOOL_CALL_THRESHOLD} tool calls:\n")
    for l in leads_to_replay:
        print(f"  CID {l['cid']} Lead {l['lead_id']} ({l['tool_calls']} tool calls)")

    print(f"\n{'='*60}")
    print(f"Starting replay...")
    print(f"{'='*60}\n")

    results = []
    for i, lead in enumerate(leads_to_replay, 1):
        cid = lead["cid"]
        lid = lead["lead_id"]
        plan_file = f"output\\results_orchestrated\\c\\{cid}\\run_001\\1_plan_final.json"

        if not Path(plan_file).exists():
            print(f"[{i}/{len(leads_to_replay)}] SKIP CID {cid} Lead {lid} — plan file not found")
            results.append({"cid": cid, "lead_id": lid, "status": "skipped", "duration": 0})
            continue

        print(f"[{i}/{len(leads_to_replay)}] Replaying CID {cid} Lead {lid} (was {lead['tool_calls']} tool calls)...")
        t0 = time.time()
        try:
            analyzer = IssueAnalyzer(
                lang="c",
                orchestrated=True,
                exact_only=True,
                plan_file=plan_file,
                replay_lead=str(lid),
            )
            analyzer.run(DB_PATH)
            elapsed = time.time() - t0
            print(f"    Done in {elapsed:.1f}s")
            results.append({"cid": cid, "lead_id": lid, "status": "ok", "duration": elapsed})
        except Exception as e:
            elapsed = time.time() - t0
            print(f"    FAILED after {elapsed:.1f}s: {e}")
            results.append({"cid": cid, "lead_id": lid, "status": f"error: {e}", "duration": elapsed})

    # Summary
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    ok = sum(1 for r in results if r["status"] == "ok")
    total_time = sum(r["duration"] for r in results)
    print(f"  {ok}/{len(results)} succeeded in {total_time:.1f}s total\n")
    for r in results:
        print(f"  CID {r['cid']} Lead {r['lead_id']}: {r['status']} ({r['duration']:.1f}s)")


if __name__ == "__main__":
    main()
