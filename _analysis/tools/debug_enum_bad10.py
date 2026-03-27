"""
Debug: run find_enum_end on the RAW (unfixed) CSV and show the first 10 entries
where it produces an end_line whose source line does NOT contain '}'.
Shows actual source around start_line and end_line so we can see exactly
what went wrong.
"""
import csv
import sys
import zipfile

db = sys.argv[1] if len(sys.argv) > 1 else r"C:\code\codeQL_CoD\codeql"
raw_csv = db + "\\EnumLookup_raw.csv"
src_zip = db + "\\src.zip"


def norm(raw):
    return raw.strip().strip('"').replace("\\", "/").replace(":", "_", 1)


def find_enum_end(lines, start_line):
    """Same logic as fix_enum_endlines.py."""
    idx = start_line - 1
    if idx < 0 or idx >= len(lines):
        return start_line
    # Guard: need '{' within 4 lines
    has_open = False
    for i in range(idx, min(idx + 4, len(lines))):
        if '{' in lines[i]:
            has_open = True
            break
    if not has_open:
        return start_line
    # Brace scan
    depth, opened = 0, False
    for i in range(idx, min(idx + 200, len(lines))):
        line = lines[i]
        cp = line.find('//')
        if cp >= 0:
            line = line[:cp]
        for ch in line:
            if ch == '{':
                depth += 1
                opened = True
            elif ch == '}':
                depth -= 1
                if opened and depth == 0:
                    return i + 1
    return start_line


# Read raw rows
rows = []
with open(raw_csv, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        if "start_line" in line and "end_line" in line:
            continue
        p = list(csv.reader([line]))[0]
        if len(p) >= 6:
            rows.append(p)

print(f"Total raw rows: {len(rows)}")

with zipfile.ZipFile(src_zip) as zf:
    znames = set(zf.namelist())
    fc = {}
    shown = 0
    total_bad = 0

    for r in rows:
        name = r[1].strip('"')
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

        new_end = find_enum_end(fl, start)
        if new_end == start:
            continue  # stayed single-line, not a failure

        ei = new_end - 1
        # Check if end_line has '}'
        if 0 <= ei < len(fl) and "}" in fl[ei]:
            continue  # PASS

        total_bad += 1
        if shown >= 10:
            continue
        shown += 1

        print(f"\n{'='*70}")
        print(f"BAD #{shown}: {name}")
        print(f"  File: ...{fcol[-70:]}")
        print(f"  start_line={start}, computed_end={new_end}, span={new_end-start+1}, file_len={len(fl)}")

        if ei >= len(fl):
            print(f"  PROBLEM: end_line {new_end} is PAST end of file ({len(fl)} lines)")
        else:
            print(f"  end_line text: [{fl[ei].rstrip()}]")

        print(f"\n  Source around start_line ({start}):")
        for i in range(max(0, start - 2), min(len(fl), start + 6)):
            m = ">>>" if i == start - 1 else "   "
            print(f"    {i+1:>6} {m} {fl[i].rstrip()[:120]}")

        if 0 <= ei < len(fl):
            print(f"\n  Source around computed end_line ({new_end}):")
            for i in range(max(0, new_end - 4), min(len(fl), new_end + 3)):
                m = ">>>" if i == new_end - 1 else "   "
                print(f"    {i+1:>6} {m} {fl[i].rstrip()[:120]}")

    print(f"\n{'='*70}")
    print(f"Total bad: {total_bad}")
    print(f"(Shown first 10)")
