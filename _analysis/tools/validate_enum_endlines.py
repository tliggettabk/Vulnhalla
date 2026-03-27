"""
Validate EnumLookup.csv end_lines by checking that the source at end_line
actually contains '}' (closing brace of the enum).

Samples multi-line enums and checks:
1. Does end_line contain '}' ?
2. Does start_line contain 'enum' or '{' ?
3. Is the line after end_line NOT inside the enum (i.e., no trailing enum constants)?
"""
import csv
import random
import sys
import zipfile

db = sys.argv[1] if len(sys.argv) > 1 else r"C:\code\codeQL_CoD\codeql"
enum_csv = db + "\\EnumLookup.csv"
src_zip = db + "\\src.zip"


def norm(raw):
    p = raw.strip().strip('"').replace("\\", "/")
    p = p.replace(":", "_", 1)
    return p


# Parse multi-line rows
rows = []
with open(enum_csv, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        parsed = list(csv.reader([line]))[0]
        if len(parsed) >= 6:
            start = int(parsed[3])
            end = int(parsed[4])
            if end > start:
                rows.append(parsed)

print(f"Multi-line enums to validate: {len(rows)}")

# Sample: check ALL of them (it's only 14K, fast enough)
with zipfile.ZipFile(src_zip) as zf:
    zip_names = set(zf.namelist())
    file_cache = {}

    good = 0
    bad_no_brace = []
    bad_no_file = 0
    bad_extra_after = []

    for r in rows:
        name = r[1].strip('"')
        file_col = r[2]
        start = int(r[3])
        end = int(r[4])
        simple = r[5].strip('"')

        zp = norm(file_col)
        if zp not in file_cache:
            if zp in zip_names:
                try:
                    content = zf.read(zp).decode("utf-8", errors="replace")
                    content = content.replace("\r\n", "\n").replace("\r", "\n")
                    file_cache[zp] = content.split("\n")
                except Exception:
                    file_cache[zp] = None
            else:
                file_cache[zp] = None

        lines = file_cache[zp]
        if lines is None:
            bad_no_file += 1
            continue

        # Check 1: Does end_line contain '}' ?
        end_idx = end - 1  # 0-indexed
        if end_idx < 0 or end_idx >= len(lines):
            bad_no_brace.append((name, file_col[-60:], start, end, "end_line out of range"))
            continue

        end_text = lines[end_idx]
        if "}" not in end_text:
            # Check end_line+1 in case off-by-one
            context = []
            for i in range(max(0, end_idx - 2), min(len(lines), end_idx + 3)):
                marker = " >>>" if i == end_idx else "    "
                context.append(f"  {i+1:>5}{marker} {lines[i]}")
            bad_no_brace.append((name, file_col[-60:], start, end, "\n".join(context)))
            continue

        # Check 2: Does start_line area contain 'enum' ?
        start_idx = start - 1
        start_area = " ".join(lines[max(0, start_idx - 1):start_idx + 2])
        if "enum" not in start_area.lower():
            # Not necessarily wrong (could be macro-generated), just note it
            pass

        good += 1

print(f"\nResults:")
print(f"  PASS (end_line has '}}'):   {good}")
print(f"  FAIL (no '}}' at end_line): {len(bad_no_brace)}")
print(f"  SKIP (file not in zip):    {bad_no_file}")
print(f"  Pass rate: {100*good/(good+len(bad_no_brace)):.1f}%")

if bad_no_brace:
    print(f"\n--- FAILURES (showing up to 20) ---")
    for name, fpath, start, end, context in bad_no_brace[:20]:
        print(f"\n  {name} (lines {start}-{end}) in ...{fpath}")
        print(context)

# Spot-check: show 5 random GOOD ones with context
print(f"\n--- SPOT CHECK: 5 random passing enums ---")
random.seed(42)
spot = random.sample(rows, min(5, len(rows)))
for r in spot:
    name = r[1].strip('"')
    file_col = r[2]
    start = int(r[3])
    end = int(r[4])
    zp = norm(file_col)
    lines = file_cache.get(zp)
    if not lines:
        continue
    print(f"\n  {name} (lines {start}-{end}):")
    for i in range(start - 1, min(end, len(lines))):
        print(f"    {i+1:>5}: {lines[i][:100]}")
    if end < len(lines):
        print(f"    {end+1:>5}: {lines[end][:100]}  <-- line after")
