"""Analyze which EnumLookup.csv entries could not be fixed and why."""
import csv
import collections
import zipfile
import sys

db = sys.argv[1] if len(sys.argv) > 1 else r"C:\code\codeQL_CoD\codeql"
enum_csv = db + "\\EnumLookup.csv"
src_zip = db + "\\src.zip"

# Parse all rows
rows = []
with open(enum_csv, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        parsed = list(csv.reader([line]))[0]
        if len(parsed) >= 6:
            rows.append(parsed)

# Identify single-line rows
single = [r for r in rows if int(r[3]) == int(r[4])]


def norm(raw):
    p = raw.strip().strip('"').replace("\\", "/")
    p = p.replace(":", "_", 1)
    return p


# Get zip contents
with zipfile.ZipFile(src_zip) as zf:
    zip_names = set(zf.namelist())

# Categorize
missing_in_zip = []
present_but_unfixed = []
for r in single:
    zp = norm(r[2])
    if zp in zip_names:
        present_but_unfixed.append(r)
    else:
        missing_in_zip.append(r)

print(f"Total enums: {len(rows)}")
print(f"Fixed (multi-line): {len(rows) - len(single)}")
print(f"Single-line enums: {len(single)}")
print(f"  File NOT in src.zip: {len(missing_in_zip)}")
print(f"  File IS in src.zip:  {len(present_but_unfixed)}")
print()

# Break down missing by path prefix
prefixes = collections.Counter()
for r in missing_in_zip:
    path = r[2].strip('"')
    parts = path.replace("\\", "/").split("/")
    if len(parts) >= 3:
        prefix = "/".join(parts[:3])
    else:
        prefix = path
    prefixes[prefix] += 1

print("Missing files by path prefix:")
for p, cnt in prefixes.most_common(20):
    print(f"  {cnt:>5}  {p}")

# Check if any project (mapped_drives) files are missing
project_missing = [r for r in missing_in_zip if "mapped_drives" in r[2]]
print(f"\nProject files (mapped_drives) missing from zip: {len(project_missing)}")
if project_missing:
    for r in project_missing[:10]:
        print(f"  {r[1]}: {r[2].strip(chr(34))[:80]}  line {r[3]}")

# Break down present-but-unfixed
if present_but_unfixed:
    print(f"\nPresent in zip but still single-line ({len(present_but_unfixed)}):")
    print("(These are forward-declared enums or enums with no body in that TU)")
    for r in present_but_unfixed[:20]:
        print(f"  {r[1]}: line {r[3]} in ...{r[2].strip(chr(34))[-60:]}")
    if len(present_but_unfixed) > 20:
        print(f"  ... and {len(present_but_unfixed) - 20} more")
