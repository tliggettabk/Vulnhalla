"""Show first 10 cases where smart parser skips but naive gets right code.
Read source directly from zip for display."""
import csv, re, sys, zipfile

db = sys.argv[1] if len(sys.argv) > 1 else r"C:\code\codeQL_CoD\codeql"
raw_csv = db + "\\EnumLookup_raw.csv"
src_zip = db + "\\src.zip"

def norm(raw):
    return raw.strip().strip('"').replace("\\", "/").replace(":", "_", 1)

def smart_find(lines, start_1b, simple_name):
    idx = start_1b - 1
    if idx < 0 or idx >= len(lines):
        return start_1b, "out_of_bounds"
    scan_limit = min(idx + 6, len(lines))
    scan_text = ""
    brace_line = None
    semi_before_brace = False
    has_enum = False
    enum_idx = None
    for i in range(idx, scan_limit):
        line = lines[i].strip()
        cp = line.find('//')
        code = line[:cp].strip() if cp >= 0 else line
        scan_text += " " + code
        if re.search(r'\benum\b', code):
            has_enum = True
            if enum_idx is None: enum_idx = i
        if '{' in code:
            if brace_line is None: brace_line = i
            break
        if ';' in code:
            semi_before_brace = True
    # Backward scan: check one line above for typedef enum (no ; = not a forward decl)
    if not has_enum and idx > 0:
        prev = lines[idx - 1].strip()
        cp2 = prev.find('//')
        pc = prev[:cp2].strip() if cp2 >= 0 else prev
        if re.search(r'\benum\b', pc) and ';' not in pc:
            has_enum = True
            enum_idx = idx - 1
    if not has_enum:
        start_line = lines[idx].strip()
        if simple_name not in start_line:
            return start_1b, "no_enum_keyword_no_name"
        if brace_line is None:
            return start_1b, "macro_no_brace"
        return start_1b, "no_enum_keyword"
    our_enum = False
    is_typedef_anon = False
    if enum_idx is not None:
        eline = lines[enum_idx].strip()
        cp = eline.find('//')
        ecode = eline[:cp].strip() if cp >= 0 else eline
        if re.search(r'\benum\b\s+(?:class\s+|struct\s+)?' + re.escape(simple_name) + r'\b', ecode):
            our_enum = True
        elif re.search(r'\btypedef\s+enum\b', ecode):
            is_typedef_anon = True; our_enum = True
        elif enum_idx > 0:
            prev = lines[enum_idx - 1].strip()
            if 'typedef' in prev:
                is_typedef_anon = True; our_enum = True
    if not our_enum:
        return start_1b, "enum_keyword_wrong_name"
    if semi_before_brace and brace_line is None:
        fwd_pat = re.compile(r'\benum\b\s+(?:class\s+|struct\s+)?' + re.escape(simple_name) + r'\s*(?::\s*[\w\s]+)?\s*;')
        if fwd_pat.search(scan_text):
            return start_1b, "forward_decl"
    if semi_before_brace and brace_line is not None:
        if enum_idx is not None:
            el = lines[enum_idx].strip()
            cp2 = el.find('//')
            ec2 = el[:cp2].strip() if cp2 >= 0 else el
            if re.search(re.escape(simple_name) + r'\s*(?::\s*[\w\s]+)?\s*;', ec2):
                return start_1b, "forward_decl_with_later_brace"
    if brace_line is None:
        return start_1b, "no_brace_in_window"
    depth = 0; opened = False
    for i in range(brace_line, min(brace_line + 500, len(lines))):
        line = lines[i]
        cp = line.find('//')
        code = line[:cp] if cp >= 0 else line
        for ch in code:
            if ch == '{': depth += 1; opened = True
            elif ch == '}':
                depth -= 1
                if opened and depth == 0:
                    end = i + 1
                    if end - start_1b > 500: return start_1b, "span_too_large"
                    span = "\n".join(lines[start_1b-1:end])
                    if is_typedef_anon:
                        el2 = lines[i].strip() if i < len(lines) else ""
                        if not re.search(r'}\s*' + re.escape(simple_name) + r'\b', el2):
                            return start_1b, "typedef_name_mismatch"
                    elif not re.search(r'\b' + re.escape(simple_name) + r'\b', span):
                        return start_1b, "name_not_in_span"
                    return end, "matched"
    return start_1b, "brace_mismatch"

def naive_find(lines, start):
    idx = start - 1
    if idx < 0 or idx >= len(lines): return start
    depth, opened = 0, False
    for i in range(idx, min(idx + 200, len(lines))):
        for ch in lines[i]:
            if ch == '{': depth += 1; opened = True
            elif ch == '}':
                depth -= 1
                if opened and depth == 0: return i + 1
    return start

def is_right(lines, s, e, name):
    stripped = []
    for l in lines[s-1:e]:
        cp = l.find('//')
        stripped.append(l[:cp] if cp >= 0 else l)
    span = "\n".join(stripped)
    # Per-line check: enum NAME must NOT be a forward decl (no ; before {)
    enum_pat = re.compile(r'\benum\b\s+(?:class\s+|struct\s+)?' + re.escape(name) + r'\b')
    has_def = False
    for sl in stripped:
        m = enum_pat.search(sl)
        if m:
            after = sl[m.end():]
            semi_pos = after.find(';')
            brace_pos = after.find('{')
            if semi_pos >= 0 and (brace_pos < 0 or semi_pos < brace_pos):
                continue
            has_def = True
            break
    has_td = bool(re.search(r'}\s*' + re.escape(name) + r'\s*[;,]', span))
    return has_def or has_td

# Load current EnumLookup.csv to show its start_line for each loss
current_csv = db + "\\EnumLookup.csv"
current_lookup = {}  # (simple_name, file_norm) -> list of (start, end)
try:
    with open(current_csv, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            p = list(csv.reader([line]))[0]
            if len(p) >= 6:
                sn = p[5].strip('"') if len(p) > 5 else p[1].strip('"')
                fn = norm(p[2].strip('"'))
                key = (sn, fn)
                if key not in current_lookup:
                    current_lookup[key] = []
                current_lookup[key].append((int(p[3]), int(p[4])))
except Exception as e:
    print(f"Warning: couldn't load {current_csv}: {e}")

rows = []
with open(raw_csv, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line or ("start_line" in line and "end_line" in line): continue
        p = list(csv.reader([line]))[0]
        if len(p) >= 6: rows.append(p)

shown = 0
seen = set()  # dedupe by (name, file, start, naive_end)

with zipfile.ZipFile(src_zip) as zf:
    znames = set(zf.namelist())
    fc = {}
    for r in rows:
        if shown >= 10: break
        simple = r[5].strip('"')
        fcol = r[2].strip('"')
        start = int(r[3])
        zp = norm(fcol)
        if zp not in fc:
            if zp in znames:
                try:
                    c = zf.read(zp).decode("utf-8", "replace")
                    fc[zp] = c.replace("\r\n", "\n").split("\n")
                except: fc[zp] = None
            else: fc[zp] = None
        fl = fc.get(zp)
        if fl is None: continue

        smart_end, reason = smart_find(fl, start, simple)
        naive_end = naive_find(fl, start)
        
        if smart_end != start: continue  # smart didn't skip
        if naive_end == start: continue  # naive also skipped
        nei = naive_end - 1
        if nei < 0 or nei >= len(fl) or "}" not in fl[nei]: continue
        if not is_right(fl, start, naive_end, simple): continue  # naive was wrong too
        if (simple, zp) in current_lookup: continue  # already covered in CSV
        
        key = (simple, zp, start, naive_end)
        if key in seen: continue
        seen.add(key)
        
        shown += 1
        # Look up in current EnumLookup.csv
        csv_key = (simple, zp)
        csv_entries = current_lookup.get(csv_key, [])
        if csv_entries:
            csv_info = ", ".join(f"L{s}-{e}" for s, e in csv_entries)
        else:
            csv_info = "NOT IN CSV"
        print(f"#{shown}: '{simple}' raw L{start}-{naive_end} reason={reason}  csv={csv_info}")
        print(f"  File: ...{fcol[-70:]}")
        print(f"  --- naive source (lines {start}-{naive_end}) ---")
        for li in range(start-1, min(naive_end, len(fl))):
            print(f"    {li+1:>6}: {fl[li].rstrip()[:140]}")
        print()
