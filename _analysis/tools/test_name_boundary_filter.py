"""Test: after naive brace-match, check if enum simple_name appears on
start_line or end_line.  Categorize into 4 buckets."""
import csv, re, sys, zipfile

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
                    return i + 1  # 1-based
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

    keep = 0
    false_reject = []
    true_reject = 0
    false_accept = []

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
            continue

        # Is the code RIGHT?
        span_text = "\n".join(fl[start-1:ne])
        has_def = bool(re.search(r'enum\s+(class\s+|struct\s+)?' + re.escape(simple) + r'\s*[:{]', span_text))
        has_typedef = bool(re.search(r'}\s*' + re.escape(simple) + r'\s*[;,]', span_text))
        is_right = has_def or has_typedef

        # Does name appear on start_line or end_line?
        start_text = fl[start - 1] if start - 1 < len(fl) else ""
        end_text = fl[nei] if nei < len(fl) else ""
        on_boundary = (simple in start_text) or (simple in end_text)

        if is_right and on_boundary:
            keep += 1
        elif is_right and not on_boundary:
            false_reject.append((simple, fcol[-60:], start, ne,
                start_text.rstrip(), end_text.rstrip(), fl, start-1, nei))
        elif not is_right and not on_boundary:
            true_reject += 1
        else:
            false_accept.append((simple, fcol[-60:], start, ne,
                start_text.rstrip(), end_text.rstrip(), fl, start-1, nei))

    total = keep + len(false_reject) + true_reject + len(false_accept)
    print(f"\nResults ({total} naive 'good' results tested):")
    print(f"  KEEP          (right + name on boundary):     {keep}")
    print(f"  FALSE REJECT  (right + name NOT on boundary): {len(false_reject)}  <-- lose good data")
    print(f"  TRUE REJECT   (wrong + name NOT on boundary): {true_reject}  <-- filter catches bad")
    print(f"  FALSE ACCEPT  (wrong + name ON boundary):     {len(false_accept)}  <-- bad leaks through")

    right_total = keep + len(false_reject)
    wrong_total = true_reject + len(false_accept)
    if right_total:
        print(f"\n  Of {right_total} RIGHT: {keep} kept ({100*keep/right_total:.1f}%), "
              f"{len(false_reject)} falsely rejected ({100*len(false_reject)/right_total:.1f}%)")
    if wrong_total:
        print(f"  Of {wrong_total} WRONG: {true_reject} caught ({100*true_reject/wrong_total:.1f}%), "
              f"{len(false_accept)} leaked ({100*len(false_accept)/wrong_total:.1f}%)")

    if false_reject:
        print(f"\n{'='*70}")
        print(f"FALSE REJECTS (good code the filter would WRONGLY toss):")
        for i, (s, f, st, ne, sl, el, fl, si, ei) in enumerate(false_reject[:10]):
            print(f"\n  #{i+1}: '{s}' L{st}-{ne}  ...{f}")
            print(f"    start: {sl[:120]}")
            print(f"    end:   {el[:120]}")
            print(f"    --- full span ---")
            for li in range(si, min(ei+1, len(fl))):
                print(f"      {li+1:>6}: {fl[li].rstrip()[:120]}")

    if false_accept:
        print(f"\n{'='*70}")
        print(f"FALSE ACCEPTS (wrong code the filter would MISS):")
        for i, (s, f, st, ne, sl, el, fl, si, ei) in enumerate(false_accept[:15]):
            print(f"\n  #{i+1}: '{s}' L{st}-{ne}  ...{f}")
            print(f"    start: {sl[:120]}")
            print(f"    end:   {el[:120]}")
            print(f"    --- full span ---")
            for li in range(si, min(ei+1, len(fl))):
                print(f"      {li+1:>6}: {fl[li].rstrip()[:120]}")
