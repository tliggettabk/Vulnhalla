"""
Debug: run the ORIGINAL naive find_enum_end (NO guards, NO comment stripping)
on the raw CSV to see exactly what goes wrong without protections.
Shows the first 10 entries where naive brace counting produces a wrong end_line.
"""
import csv
import sys
import zipfile

db = sys.argv[1] if len(sys.argv) > 1 else r"C:\code\codeQL_CoD\codeql"
raw_csv = db + "\\EnumLookup_raw.csv"
src_zip = db + "\\src.zip"


def norm(raw):
    return raw.strip().strip('"').replace("\\", "/").replace(":", "_", 1)


def find_enum_end_NAIVE(lines, start_line):
    """Original naive version: just count braces, no guards."""
    idx = start_line - 1
    if idx < 0 or idx >= len(lines):
        return start_line, "out of range"
    depth, opened = 0, False
    for i in range(idx, min(idx + 200, len(lines))):
        for ch in lines[i]:
            if ch == '{':
                depth += 1
                opened = True
            elif ch == '}':
                depth -= 1
                if opened and depth == 0:
                    return i + 1, "brace_match"
    return start_line, "no_match"


def find_enum_end_GUARDED(lines, start_line):
    """Current guarded version."""
    idx = start_line - 1
    if idx < 0 or idx >= len(lines):
        return start_line, "out of range"
    # Guard: need '{' within 4 lines
    has_open = False
    for i in range(idx, min(idx + 4, len(lines))):
        if '{' in lines[i]:
            has_open = True
            break
    if not has_open:
        return start_line, "forward_decl_guard"
    # Brace scan with comment stripping
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
                    return i + 1, "brace_match"
    return start_line, "no_match"


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
    total_naive_bad = 0
    total_guard_saved = 0
    total_both_good = 0

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

        naive_end, naive_reason = find_enum_end_NAIVE(fl, start)
        guard_end, guard_reason = find_enum_end_GUARDED(fl, start)

        if naive_end == start:
            continue  # both can't fix it

        # Check naive result
        nei = naive_end - 1
        naive_ok = (0 <= nei < len(fl) and "}" in fl[nei])

        if naive_ok:
            total_both_good += 1
            continue

        # Naive produced a BAD result
        total_naive_bad += 1
        if guard_end == start:
            total_guard_saved += 1

        if shown >= 10:
            continue
        shown += 1

        print(f"\n{'='*70}")
        print(f"BAD #{shown}: {name}")
        print(f"  File: ...{fcol[-70:]}")
        print(f"  start_line={start}")
        print(f"  NAIVE:   end={naive_end} (span={naive_end-start+1}) reason={naive_reason}")
        print(f"  GUARDED: end={guard_end} reason={guard_reason}")

        if nei >= len(fl):
            print(f"  PROBLEM: naive end_line {naive_end} past EOF ({len(fl)} lines)")
        else:
            print(f"  naive end_line text: [{fl[nei].rstrip()[:120]}]")

        print(f"\n  Source around start_line ({start}):")
        for i in range(max(0, start - 2), min(len(fl), start + 6)):
            m = ">>>" if i == start - 1 else "   "
            print(f"    {i+1:>6} {m} {fl[i].rstrip()[:120]}")

        if 0 <= nei < len(fl):
            print(f"\n  Source around naive end_line ({naive_end}):")
            for i in range(max(0, naive_end - 3), min(len(fl), naive_end + 3)):
                m = ">>>" if i == naive_end - 1 else "   "
                print(f"    {i+1:>6} {m} {fl[i].rstrip()[:120]}")

    print(f"\n{'='*70}")
    print(f"SUMMARY:")
    print(f"  Naive produced good result:   {total_both_good}")
    print(f"  Naive produced BAD result:    {total_naive_bad}")
    print(f"  Guard saved (reverted to SL): {total_guard_saved}")
    print(f"  Guard did NOT save:           {total_naive_bad - total_guard_saved}")
