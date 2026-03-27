"""Analyze single-line enums: which have good duplicates vs truly incomplete."""
import csv
import collections

db = r"C:\code\codeQL_CoD\codeql"
enum_csv = db + "\\EnumLookup.csv"

rows = []
with open(enum_csv, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        parsed = list(csv.reader([line]))[0]
        if len(parsed) >= 6:
            rows.append(parsed)

single = [r for r in rows if int(r[3]) == int(r[4])]
fixed = [r for r in rows if int(r[3]) != int(r[4])]

# Check: how many single-line enum names also have a fixed version?
fixed_names = set(r[5].strip('"') for r in fixed)
single_with_fixed = [r for r in single if r[5].strip('"') in fixed_names]
single_no_fixed = [r for r in single if r[5].strip('"') not in fixed_names]

print(f"Single-line enums: {len(single)}")
print(f"  Have a fixed row elsewhere: {len(single_with_fixed)} (get_class will find the good one)")
print(f"  No fixed row anywhere:      {len(single_no_fixed)} (truly incomplete)")
print()

# Show the truly incomplete ones
names = collections.Counter(r[5].strip('"') for r in single_no_fixed)
print(f"Unique enum names with no good row: {len(names)}")
print()
print("Top 20:")
for name, cnt in names.most_common(20):
    files = set(r[2].strip('"')[-50:] for r in single_no_fixed if r[5].strip('"') == name)
    print(f"  {cnt}x {name}")
    for ff in list(files)[:2]:
        print(f"       ...{ff}")

# How many are project vs vendor?
proj = [r for r in single_no_fixed if "mapped_drives" in r[2]]
vendor = [r for r in single_no_fixed if "mapped_drives" not in r[2]]
print(f"\nProject (mapped_drives): {len(proj)}")
print(f"Vendor/system:           {len(vendor)}")
