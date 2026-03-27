"""Show full source for false accepts AND test semicolon filter:
if enum name is on start_line and start_line has ';' after name → skip."""
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

    # Counters for the combined filter: name on boundary + no ; after name on start
    keep = 0
    wrong_kept = []     # wrong code that leaks through everything
    wrong_caught = 0    # wrong code caught
    right_lost = []     # right code wrongly tossed
    
    # Also track: how many does the ; filter alone catch?
    semi_catches_wrong = 0
    semi_catches_right = 0

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

        start_text = fl[start - 1] if start - 1 < len(fl) else ""
        end_text = fl[nei] if nei < len(fl) else ""
        
        # Check: does start_line have name followed by ; (forward decl)?
        # Look for: name appears, and ; appears after name position
        name_on_start = simple in start_text
        name_on_end = simple in end_text
        on_boundary = name_on_start or name_on_end
        
        # Semicolon check: if name is on start line, check if ; comes after name
        has_semi_after_name = False
        if name_on_start:
            pos = start_text.find(simple)
            after = start_text[pos + len(simple):]
            if ';' in after:
                has_semi_after_name = True
        
        if has_semi_after_name:
            if is_right:
                semi_catches_right += 1
            else:
                semi_catches_wrong += 1
        
        # Combined filter: reject if (not on boundary) OR (semi after name on start)
        reject = (not on_boundary) or has_semi_after_name
        
        if is_right and not reject:
            keep += 1
        elif is_right and reject:
            right_lost.append((simple, fcol[-60:], start, ne, start_text.rstrip(), end_text.rstrip(), fl, start-1, nei))
        elif not is_right and reject:
            wrong_caught += 1
        else:  # wrong and not rejected
            wrong_kept.append((simple, fcol[-60:], start, ne, start_text.rstrip(), end_text.rstrip(), fl, start-1, nei))

    total = keep + len(right_lost) + wrong_caught + len(wrong_kept)
    print(f"\nCOMBINED FILTER: name on boundary + reject if ; after name")
    print(f"{'='*70}")
    print(f"  KEEP (right, passes filter):    {keep}")
    print(f"  RIGHT LOST (falsely rejected):  {len(right_lost)}")
    print(f"  WRONG CAUGHT (correctly caught): {wrong_caught}")
    print(f"  WRONG KEPT (leaks through):     {len(wrong_kept)}")
    print(f"{'='*70}")
    
    right_total = keep + len(right_lost)
    wrong_total = wrong_caught + len(wrong_kept)
    if right_total:
        print(f"\n  Of {right_total} RIGHT: keep {keep} ({100*keep/right_total:.1f}%), lose {len(right_lost)} ({100*len(right_lost)/right_total:.1f}%)")
    if wrong_total:
        print(f"  Of {wrong_total} WRONG: catch {wrong_caught} ({100*wrong_caught/wrong_total:.1f}%), leak {len(wrong_kept)} ({100*len(wrong_kept)/wrong_total:.1f}%)")

    print(f"\n  Semicolon filter alone: catches {semi_catches_wrong} wrong, {semi_catches_right} right")

    # Show ALL wrong_kept with full source
    if wrong_kept:
        print(f"\n{'='*70}")
        print(f"WRONG CODE THAT STILL LEAKS THROUGH ({len(wrong_kept)} total):")
        print(f"Showing first 15 with full source:")
        for i, (s, f, st, ne, sl, el, fl, si, ei) in enumerate(wrong_kept[:15]):
            print(f"\n  #{i+1}: '{s}' L{st}-{ne}  ...{f}")
            print(f"    start: {sl[:140]}")
            print(f"    end:   {el[:140]}")
            print(f"    --- full source (lines {st}-{ne}) ---")
            for li in range(si, min(ei+1, len(fl))):
                print(f"      {li+1:>6}: {fl[li].rstrip()[:140]}")
