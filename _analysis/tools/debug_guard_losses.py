"""Show the cases where naive succeeds but guard rejects — what is the guard losing?"""
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


def find_guarded(lines, start):
    idx = start - 1
    if idx < 0 or idx >= len(lines):
        return start
    has_open = any('{' in lines[i] for i in range(idx, min(idx + 4, len(lines))))
    if not has_open:
        return start
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

with zipfile.ZipFile(src_zip) as zf:
    znames = set(zf.namelist())
    fc = {}
    lost = 0
    shown = 0

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

        ne = find_naive(fl, start)
        ge = find_guarded(fl, start)

        if ne > start and ge == start:
            # Guard killed a valid fix
            lost += 1
            if shown < 10:
                shown += 1
                nei = ne - 1
                # Find where the first '{' actually is
                idx = start - 1
                brace_line = None
                for i in range(idx, min(idx + 20, len(fl))):
                    if '{' in fl[i]:
                        brace_line = i + 1
                        break

                print(f"\n{'='*70}")
                print(f"LOST #{shown}: {name}")
                print(f"  File: ...{fcol[-70:]}")
                print(f"  start={start}, naive_end={ne} (span={ne-start+1})")
                print(f"  First '{{' at line {brace_line} (offset +{brace_line - start} from start)")
                print(f"\n  Source around start ({start}):")
                for i in range(max(0, start - 2), min(len(fl), start + 10)):
                    m = ">>>" if i == start - 1 else "   "
                    print(f"    {i+1:>6} {m} {fl[i].rstrip()[:120]}")
                print(f"\n  Source at naive end ({ne}):")
                for i in range(max(0, ne - 2), min(len(fl), ne + 2)):
                    m = ">>>" if i == ne - 1 else "   "
                    print(f"    {i+1:>6} {m} {fl[i].rstrip()[:120]}")

    print(f"\n{'='*70}")
    print(f"Total cases where naive succeeds but guard rejects: {lost}")
