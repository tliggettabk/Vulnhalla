"""
For every row where naive finds end > start AND end_line has '}':
Check if the source between start_line and end_line actually contains
'enum <name>' — i.e., is it the RIGHT enum or some random other code?

Show the first 10 where it's the WRONG code.
"""
import csv
import sys
import zipfile

db = sys.argv[1] if len(sys.argv) > 1 else r"C:\code\codeQL_CoD\codeql"
raw_csv = db + "\\EnumLookup_raw.csv"
src_zip = db + "\\src.zip"


def norm(raw):
    return raw.strip().strip('"').replace("\\", "/").replace(":", "_", 1)


def find_naive(lines, start):
    idx = start - 1
    if idx < 0 or idx >= len(lines):
        return start
    depth, opened = 0, False
    for i in range(idx, min(idx + 200, len(lines))):
        for ch in lines[i]:
            if ch == '{':
                depth += 1
                opened = True
            elif ch == '}':
                depth -= 1
                if opened and depth == 0:
                    return i + 1
    return start


rows = []
with open(raw_csv, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line or ("start_line" in line and "end_line" in line):
            continue
        p = list(csv.reader([line]))[0]
        if len(p) >= 6:
            rows.append(p)

print(f"Total raw rows: {len(rows)}")

with zipfile.ZipFile(src_zip) as zf:
    znames = set(zf.namelist())
    fc = {}
    wrong_code = 0
    right_code = 0
    shown = 0

    for r in rows:
        name = r[1].strip('"')
        simple = r[5].strip('"')
        fcol = r[2].strip('"')
        start = int(r[3])
        zp = norm(fcol)

        if zp not in fc:
            if zp in znames:
                try:
                    c = zf.read(zp).decode("utf-8", "replace")
                    fc[zp] = c.replace("\r\n", "\n").split("\n")
                except Exception:
                    fc[zp] = None
            else:
                fc[zp] = None
        fl = fc.get(zp)
        if fl is None:
            continue

        ne = find_naive(fl, start)
        if ne == start:
            continue
        nei = ne - 1
        if nei < 0 or nei >= len(fl) or "}" not in fl[nei]:
            continue  # already known bad

        # This is a naive "pass" — end_line has '}'.
        # But does the span actually contain our enum DEFINITION (not just fwd decl)?
        span_text = "\n".join(fl[start-1:ne])
        # Pattern 1: enum NAME { or enum class NAME { — the definition itself
        # Pattern 2: typedef enum { ... } NAME; — name at the end
        import re
        has_def = bool(re.search(r'enum\s+(class\s+|struct\s+)?' + re.escape(simple) + r'\s*[:{]', span_text))
        # typedef enum {...} NAME; or } NAME, *PNAME;
        has_typedef = bool(re.search(r'}\s*' + re.escape(simple) + r'\s*[;,]', span_text))
        is_right = has_def or has_typedef

        if is_right:
            right_code += 1
        else:
            wrong_code += 1
            if shown < 10:
                shown += 1
                print(f"\n{'='*70}")
                print(f"WRONG CODE #{shown}: naive says this is '{simple}' but it isn't")
                print(f"  Enum name: {name}")
                print(f"  File: ...{fcol[-70:]}")
                print(f"  start={start}, naive_end={ne}, span={ne-start+1} lines")
                print(f"\n  FULL SOURCE returned to LLM (lines {start}-{ne}):")
                for i in range(start-1, min(ne, len(fl))):
                    print(f"    {i+1:>6}: {fl[i].rstrip()[:120]}")

    print(f"\n{'='*70}")
    print(f"Naive 'good' results that are actually RIGHT code: {right_code}")
    print(f"Naive 'good' results that are WRONG code:          {wrong_code}")
    pct = 100 * wrong_code / (right_code + wrong_code) if (right_code + wrong_code) else 0
    print(f"Wrong code rate: {pct:.1f}%")
