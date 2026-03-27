#!/usr/bin/env python3
"""Combine the partial CSVs from recent batch runs into single files."""
import csv
import glob
import os

OUT_DIR = r"output\results_orchestrated\c"


def combine_latest_two(prefix: str, out_name: str) -> int:
    """Merge the 2 most recent CSV files for the given prefix."""
    # Define the exact files to merge (newest last = wins dedup)
    files = [
        os.path.join(OUT_DIR, f"{prefix}_20260324_170529.csv"),
        os.path.join(OUT_DIR, f"{prefix}_20260325_074912.csv"),
        os.path.join(OUT_DIR, f"{prefix}_20260325_105424.csv"),
    ]
    
    # Filter to only existing files
    files = [f for f in files if os.path.exists(f)]
    
    if not files:
        print(f"  No files found for {prefix}")
        return 0

    all_rows = []
    header = None
    cid_rows = {}  # Track CIDs for dedup (last wins)
    
    for f in files:
        print(f"    Processing: {os.path.basename(f)}")
        with open(f, "r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            if header is None:
                header = reader.fieldnames
            for row in reader:
                # For CID files, use CID as deduplication key (last wins)
                if prefix == "run_cids":
                    cid = row.get("cid", "")
                    if cid:
                        cid_rows[cid] = row
                else:
                    # For leads and tool_calls, just append all rows
                    all_rows.append(row)

    if prefix == "run_cids":
        all_rows = list(cid_rows.values())

    if not all_rows:
        print(f"  No data found in {prefix} files")
        return 0

    out_path = os.path.join(OUT_DIR, out_name)
    with open(out_path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=header)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"  {len(files)} files -> {out_path} ({len(all_rows)} rows)")
    return len(all_rows)


def main():
    print("Combining the 2 most recent CSV files...\n")

    combine_latest_two("run_cids", "run_cids_merged.csv")
    combine_latest_two("run_leads", "run_leads_merged.csv") 
    combine_latest_two("run_tool_calls", "run_tool_calls_merged.csv")

    print("\nDone.")


if __name__ == "__main__":
    main()
