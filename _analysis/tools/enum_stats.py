"""Quick stats report for EnumLookup.csv after end-line fixing."""
import csv
import os
import sys

db_path = sys.argv[1] if len(sys.argv) > 1 else r"C:\code\codeQL_CoD\codeql"

enum_csv = os.path.join(db_path, "EnumLookup.csv")
classes_csv = os.path.join(db_path, "Classes.csv")

# --- Parse EnumLookup.csv ---
enum_rows = []
with open(enum_csv, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        parsed = list(csv.reader([line]))[0]
        if len(parsed) >= 6:
            enum_rows.append(parsed)

total = len(enum_rows)
fixed = sum(1 for r in enum_rows if int(r[3]) != int(r[4]))
unfixed = total - fixed

# Length stats for fixed rows
lengths = [int(r[4]) - int(r[3]) + 1 for r in enum_rows if int(r[3]) != int(r[4])]
if lengths:
    avg_len = sum(lengths) / len(lengths)
    min_len = min(lengths)
    max_len = max(lengths)
    sorted_lengths = sorted(lengths)
    median_len = sorted_lengths[len(sorted_lengths) // 2]
else:
    avg_len = min_len = max_len = median_len = 0

# File sizes
enum_size = os.path.getsize(enum_csv)
classes_size = os.path.getsize(classes_csv)

# Unique source files
files = set(r[2].strip('"') for r in enum_rows)
project_files = set(r[2].strip('"') for r in enum_rows if "mapped_drives" in r[2])

print("=" * 60)
print("ENUMLOOKUP.CSV STATS")
print("=" * 60)
print(f"  Total enum entries:        {total:,}")
print(f"  End-lines fixed:           {fixed:,} ({100*fixed/total:.1f}%)")
print(f"  Still single-line:         {unfixed:,} ({100*unfixed/total:.1f}%)")
print(f"  File size:                 {enum_size:,} bytes ({enum_size/1024/1024:.1f} MB)")
print()
print(f"  Unique source files:       {len(files):,}")
print(f"  Project source files:      {len(project_files):,} (mapped_drives)")
print()
print("  Line-length distribution (fixed enums):")
print(f"    Min:    {min_len} lines")
print(f"    Max:    {max_len} lines")
print(f"    Median: {median_len} lines")
print(f"    Mean:   {avg_len:.1f} lines")
print()

buckets = [(1, 5), (6, 15), (16, 30), (31, 60), (61, 100), (101, 500), (501, 9999)]
for lo, hi in buckets:
    cnt = sum(1 for l in lengths if lo <= l <= hi)
    if cnt:
        print(f"    {lo:>4}-{hi:>4} lines: {cnt:>5} enums")

print()
print("COMPARISON WITH CLASSES.CSV:")
print(f"  Classes.csv:    {classes_size:,} bytes ({classes_size/1024/1024:.1f} MB)")
print(f"  EnumLookup.csv: {enum_size:,} bytes ({enum_size/1024/1024:.1f} MB)")

# Count classes rows
cls_count = 0
with open(classes_csv, "r", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            cls_count += 1
print(f"  Classes.csv rows:     {cls_count:,}")
print(f"  EnumLookup.csv rows:  {total:,}")

# Overlap check
enum_names = set(r[5].strip('"') for r in enum_rows)
cls_names = set()
with open(classes_csv, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        parsed = list(csv.reader([line]))[0]
        if len(parsed) >= 6:
            cls_names.add(parsed[5].strip('"'))

overlap = enum_names & cls_names
print(f"  Name overlap:         {len(overlap)} (enums also in Classes.csv as class/struct)")

# Show the key test cases
print()
print("KEY VALIDATION:")
for name in ["hknpLevelOfDetail", "hknpPenetrationRecoveryControl", "hknpBroadPhaseType"]:
    matches = [r for r in enum_rows if r[5].strip('"') == name]
    if matches:
        r = matches[0]
        span = int(r[4]) - int(r[3]) + 1
        print(f"  {name}: lines {r[3]}-{r[4]} ({span} lines)")
    else:
        print(f"  {name}: NOT FOUND")
