"""Check: for rows where naive also skips (no { in 200 lines),
is the actual enum definition within 200 lines of the start?"""
import csv, re, sys, zipfile

db = sys.argv[1] if len(sys.argv) > 1 else r"C:\code\codeQL_CoD\codeql"
raw_csv = db + "\\EnumLookup_raw.csv"
src_zip = db + "\\src.zip"
current_csv = db + "\\EnumLookup.csv"

def norm(raw):
    return raw.strip().strip('"').replace("\\", "/").replace(":", "_", 1)

# Load current CSV coverage
covered = set()
try:
    with open(current_csv, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            p = list(csv.reader([line]))[0]
            if len(p) >= 6:
                sn = p[5].strip('"')
                fn = norm(p[2].strip('"'))
                covered.add((sn, fn))
except Exception as e:
    print(f"Warning: couldn't load {current_csv}: {e}")

rows = []
with open(raw_csv, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line or ("start_line" in line and "end_line" in line): continue
        p = list(csv.reader([line]))[0]
        if len(p) >= 6: rows.append(p)

found_nearby = 0
found_covered = 0
not_found = 0
file_missing = 0
examples = []

with zipfile.ZipFile(src_zip) as zf:
    znames = set(zf.namelist())
    fc = {}
    for r in rows:
        simple = r[5].strip('"')
        fcol = r[2].strip('"')
        start = int(r[3])
        zp = norm(fcol)
        if zp not in fc:
            if zp in znames:
                try:
                    c = zf.read(zp).decode("utf-8", "replace")
                    fc[zp] = c.replace("\r\n", "\n").split("\n")
                except:
                    fc[zp] = None
            else:
                fc[zp] = None
        fl = fc.get(zp)
        if fl is None:
            file_missing += 1
            continue

        idx = start - 1
        if idx < 0 or idx >= len(fl):
            continue

        # Check if naive finds any brace pair
        depth, opened = 0, False
        naive_end = start
        for i in range(idx, min(idx + 200, len(fl))):
            for ch in fl[i]:
                if ch == '{':
                    depth += 1
                    opened = True
                elif ch == '}':
                    depth -= 1
                    if opened and depth == 0:
                        naive_end = i + 1
                        break
            if naive_end != start:
                break

        if naive_end != start:
            continue  # naive found something — not a 'both skip'

        # Naive skipped. Is our enum name + definition within 200 lines?
        search_end = min(idx + 200, len(fl))
        enum_def_pat = re.compile(
            r'\benum\b\s+(?:class\s+|struct\s+)?' + re.escape(simple) + r'\b')
        found = False
        found_line = -1
        for i in range(idx, search_end):
            line = fl[i]
            cp = line.find('//')
            code = line[:cp] if cp >= 0 else line
            m = enum_def_pat.search(code)
            if m:
                after = code[m.end():]
                sp = after.find(';')
                bp = after.find('{')
                if sp >= 0 and (bp < 0 or sp < bp):
                    continue  # forward decl
                found = True
                found_line = i
                break

        if found:
            is_covered = (simple, zp) in covered
            if is_covered:
                found_covered += 1
            else:
                found_nearby += 1
                if len(examples) < 10:
                    examples.append((simple, fcol[-70:], start, found_line + 1,
                                     fl[found_line].strip()[:120]))
        else:
            not_found += 1

print(f"Both-skip rows: {found_nearby + found_covered + not_found}")
print(f"  Enum def within 200 lines, already in CSV: {found_covered}")
print(f"  Enum def within 200 lines, NOT in CSV:     {found_nearby}")
print(f"  No enum def within 200 lines:              {not_found}")
print(f"  (File missing from zip:                    {file_missing})")
print()
if examples:
    print(f"REAL MISSES — first {len(examples)} where enum IS nearby but NOT in CSV:")
    for j, (s, f, st, defline, code) in enumerate(examples):
        print(f"  #{j+1}: '{s}' raw_start=L{st} def_at=L{defline} (offset +{defline - st})")
        print(f"    File: ...{f}")
        print(f"    Line: {code}")
        print()
else:
    print("No real misses — every nearby enum def is already in the CSV.")
