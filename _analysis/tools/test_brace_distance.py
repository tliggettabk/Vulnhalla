"""For every naive 'good' result, measure: how many non-comment, non-blank
lines between start_line and the first '{'. Show distribution for RIGHT vs WRONG."""
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

def lines_to_brace(lines, start_idx):
    """Count non-blank non-comment lines from start_idx until first '{'.
    Returns (distance, absolute_line_offset)."""
    count = 0
    for i in range(start_idx, min(start_idx + 200, len(lines))):
        text = lines[i].strip()
        if '{' in text:
            return count, i - start_idx
        if text and not text.startswith('//'):
            count += 1
    return 999, 999

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
    
    # distance → [right_count, wrong_count]
    dist_right = {}
    dist_wrong = {}

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

        span_text = "\n".join(fl[start-1:ne])
        has_def = bool(re.search(r'enum\s+(class\s+|struct\s+)?' + re.escape(simple) + r'\s*[:{]', span_text))
        has_typedef = bool(re.search(r'}\s*' + re.escape(simple) + r'\s*[;,]', span_text))
        is_right = has_def or has_typedef

        non_comment_dist, line_offset = lines_to_brace(fl, start - 1)
        
        if is_right:
            dist_right[line_offset] = dist_right.get(line_offset, 0) + 1
        else:
            dist_wrong[line_offset] = dist_wrong.get(line_offset, 0) + 1

    # Show cumulative: if we allow N lines, how many right/wrong do we keep?
    all_dists = sorted(set(list(dist_right.keys()) + list(dist_wrong.keys())))
    
    total_right = sum(dist_right.values())
    total_wrong = sum(dist_wrong.values())
    
    print(f"\nTotal RIGHT: {total_right}, Total WRONG: {total_wrong}")
    print(f"\nLine offset = lines from start_line to first '{{' (0 = same line)")
    print(f"{'offset':>8} {'right':>8} {'wrong':>8} {'cum_right':>10} {'cum_wrong':>10} {'%right':>8} {'%wrong':>8}")
    print(f"{'-'*8} {'-'*8} {'-'*8} {'-'*10} {'-'*10} {'-'*8} {'-'*8}")
    
    cum_r = 0
    cum_w = 0
    for d in range(max(all_dists) + 1):
        r_count = dist_right.get(d, 0)
        w_count = dist_wrong.get(d, 0)
        cum_r += r_count
        cum_w += w_count
        if r_count > 0 or w_count > 0:
            print(f"{d:>8} {r_count:>8} {w_count:>8} {cum_r:>10} {cum_w:>10} "
                  f"{100*cum_r/total_right:>7.1f}% {100*cum_w/total_wrong:>7.1f}%")
        if d > 20 and r_count == 0 and w_count == 0:
            break

    # Summary table for key thresholds
    print(f"\n{'='*60}")
    print(f"If we allow at most N lines to first '{{':") 
    print(f"{'max_lines':>10} {'right_kept':>11} {'right%':>8} {'wrong_kept':>11} {'wrong%':>8}")
    for threshold in [0, 1, 2, 3, 4, 5, 10]:
        rk = sum(v for k,v in dist_right.items() if k <= threshold)
        wk = sum(v for k,v in dist_wrong.items() if k <= threshold)
        print(f"{threshold:>10} {rk:>11} {100*rk/total_right:>7.1f}% {wk:>11} {100*wk/total_wrong:>7.1f}%")
