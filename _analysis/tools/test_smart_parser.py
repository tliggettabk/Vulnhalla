"""Smart enum parser: actually understands the code structure instead of
using dumb distance thresholds.

Logic:
1. Read start_line and a few lines forward
2. Detect what we're looking at:
   a. Forward decl: `enum [class] NAME ...;` (semicolon before any {) -> SKIP
   b. Definition: `enum [class] NAME ... {` -> brace-match from that {
   c. Typedef: `typedef enum ... {` ... `} NAME;` -> brace-match, verify name after }
   d. Macro-based: `MAKE_ENUM(NAME)` or similar -> no real braces, SKIP
   e. No enum keyword at all near start_line -> SKIP (forward decl site, cast, etc.)
3. After brace-match, verify the closing `};` or `} NAME;` is correct

Test against all 15,829 raw rows and compare to naive.
"""
import csv, re, sys, zipfile
from collections import Counter

db = sys.argv[1] if len(sys.argv) > 1 else r"C:\code\codeQL_CoD\codeql"
raw_csv = db + "\\EnumLookup_raw.csv"
src_zip = db + "\\src.zip"

def norm(raw):
    return raw.strip().strip('"').replace("\\", "/").replace(":", "_", 1)


def smart_find_enum_end(lines, start_1based, simple_name):
    """Smart parser: find the end of an enum definition starting near start_1based.
    Returns (end_1based, reason) or (start_1based, reason) if can't find it."""
    idx = start_1based - 1
    if idx < 0 or idx >= len(lines):
        return start_1based, "out_of_bounds"
    
    # Phase 1: Scan up to 6 lines looking for enum-related content
    # Build a picture of what's here
    scan_limit = min(idx + 6, len(lines))
    scan_text = ""
    brace_line = None  # line index of first {
    semi_before_brace = False  # is there a ; before any { ?
    has_enum_keyword = False
    enum_line_idx = None  # which line has the 'enum' keyword
    
    for i in range(idx, scan_limit):
        line = lines[i].strip()
        # strip // comments for analysis
        comment_pos = line.find('//')
        code = line[:comment_pos].strip() if comment_pos >= 0 else line
        
        scan_text += " " + code
        
        if re.search(r'\benum\b', code):
            has_enum_keyword = True
            if enum_line_idx is None:
                enum_line_idx = i
        
        if '{' in code:
            if brace_line is None:
                brace_line = i
            break  # stop scanning once we hit {
        
        if ';' in code:
            semi_before_brace = True
    
    # Phase 1b: If no enum keyword found in forward scan, check one line backward.
    # Handles cases where CodeQL reports start at '{' but 'typedef enum' is on the line above.
    # Only accept if the backward line is a definition start (no ; which would mean forward decl).
    if not has_enum_keyword and idx > 0:
        prev_line = lines[idx - 1].strip()
        cp = prev_line.find('//')
        prev_code = prev_line[:cp].strip() if cp >= 0 else prev_line
        if re.search(r'\benum\b', prev_code) and ';' not in prev_code:
            has_enum_keyword = True
            enum_line_idx = idx - 1
    
    # Phase 2: Classify what we found
    
    # No enum keyword anywhere in the scan window?
    if not has_enum_keyword:
        # Check if start_line mentions the name at all (maybe it's a macro)
        start_line = lines[idx].strip()
        if simple_name not in start_line:
            return start_1based, "no_enum_keyword_no_name"
        # Could be MAKE_ENUM(NAME) or similar macro — no { means we can't parse it
        if brace_line is None:
            return start_1based, "macro_no_brace"
        # There's a { but no 'enum' keyword — the { belongs to something else
        return start_1based, "no_enum_keyword"
    
    # Enum keyword found. But is it OUR enum?
    # Check if the enum line contains our simple_name (word boundary)
    # or it's a typedef enum (anonymous — name comes after })
    our_enum = False
    is_typedef_anon = False
    if enum_line_idx is not None:
        eline = lines[enum_line_idx].strip()
        comment_pos = eline.find('//')
        ecode = eline[:comment_pos].strip() if comment_pos >= 0 else eline
        
        # Check: does this line have `enum [class|struct] OUR_NAME`?
        if re.search(r'\benum\b\s+(?:class\s+|struct\s+)?' + re.escape(simple_name) + r'\b', ecode):
            our_enum = True
        # Check: `typedef enum {` or `typedef enum` (anonymous, name comes after })
        elif re.search(r'\btypedef\s+enum\b', ecode):
            is_typedef_anon = True
            our_enum = True  # we'll verify name after } later
        # Check: maybe the name used differs (e.g. qualified). 
        # Also check one line before the enum keyword for typedef
        elif enum_line_idx > 0:
            prev = lines[enum_line_idx - 1].strip()
            if 'typedef' in prev:
                is_typedef_anon = True
                our_enum = True
    
    if not our_enum:
        return start_1based, "enum_keyword_wrong_name"
    
    # It's our enum keyword. Is it a forward declaration?
    # Forward decl: enum [class|struct] NAME [: type] ;
    # Key: semicolon appears AFTER enum keyword but BEFORE any {
    if semi_before_brace and brace_line is None:
        fwd_pat = re.compile(
            r'\benum\b\s+(?:class\s+|struct\s+)?' + re.escape(simple_name) + r'\s*(?::\s*[\w\s]+)?\s*;')
        if fwd_pat.search(scan_text):
            return start_1based, "forward_decl"
    
    if semi_before_brace and brace_line is not None:
        # There's a ; before the {. Check if OUR enum's line has a ; (making it a fwd decl)
        if enum_line_idx is not None:
            eline = lines[enum_line_idx].strip()
            comment_pos = eline.find('//')
            ecode = eline[:comment_pos].strip() if comment_pos >= 0 else eline
            if re.search(re.escape(simple_name) + r'\s*(?::\s*[\w\s]+)?\s*;', ecode):
                return start_1based, "forward_decl_with_later_brace"
    
    # No { found at all in scan window
    if brace_line is None:
        return start_1based, "no_brace_in_window"
    
    # We have an enum keyword AND a {. This looks like a real definition.
    # Now brace-match from brace_line.
    depth = 0
    opened = False
    for i in range(brace_line, min(brace_line + 500, len(lines))):
        # Strip // comments
        line = lines[i]
        comment_pos = line.find('//')
        code = line[:comment_pos] if comment_pos >= 0 else line
        
        for ch in code:
            if ch == '{':
                depth += 1
                opened = True
            elif ch == '}':
                depth -= 1
                if opened and depth == 0:
                    end_1based = i + 1
                    # Safety: clamp to reasonable size
                    if end_1based - start_1based > 500:
                        return start_1based, "span_too_large"
                    
                    # Post-match verification: does the span contain our name?
                    span = "\n".join(lines[start_1based-1:end_1based])
                    # For typedef enum: name should appear after } on end line
                    if is_typedef_anon:
                        end_line = lines[i].strip() if i < len(lines) else ""
                        if not re.search(r'}\s*' + re.escape(simple_name) + r'\b', end_line):
                            return start_1based, "typedef_name_mismatch"
                    # For named enum: name should be in the span
                    elif not re.search(r'\b' + re.escape(simple_name) + r'\b', span):
                        return start_1based, "name_not_in_span"
                    
                    return end_1based, "matched"
    
    return start_1based, "brace_mismatch"


def naive_find(lines, start):
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


def is_code_right(lines, start_1based, end_1based, simple_name):
    """Check if the span actually contains this enum's definition (not just a forward decl)."""
    # Strip // comments from each line before joining
    stripped = []
    for l in lines[start_1based-1:end_1based]:
        cp = l.find('//')
        stripped.append(l[:cp] if cp >= 0 else l)
    span_text = "\n".join(stripped)
    
    # Check for enum definition per-line: enum [class] NAME must NOT be a forward decl
    # Forward decl has ; after name before any { on that line
    enum_pat = re.compile(r'\benum\b\s+(?:class\s+|struct\s+)?' + re.escape(simple_name) + r'\b')
    has_def = False
    for sl in stripped:
        m = enum_pat.search(sl)
        if m:
            after = sl[m.end():]
            semi_pos = after.find(';')
            brace_pos = after.find('{')
            # If ; comes before { (or no { at all), it's a forward decl — skip
            if semi_pos >= 0 and (brace_pos < 0 or semi_pos < brace_pos):
                continue
            has_def = True
            break
    
    has_typedef = bool(re.search(
        r'}\s*' + re.escape(simple_name) + r'\s*[;,]', 
        span_text))
    return has_def or has_typedef


# Load current EnumLookup.csv to check coverage
current_csv = db + "\\EnumLookup.csv"
covered = set()  # (simple_name, file_norm) pairs that already have correct entries
try:
    with open(current_csv, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            p = list(csv.reader([line]))[0]
            if len(p) >= 6:
                sn = p[5].strip('"') if len(p) > 5 else p[1].strip('"')
                fn = norm(p[2].strip('"'))
                covered.add((sn, fn))
except Exception as e:
    print(f"Warning: couldn't load {current_csv}: {e}")

# Load rows
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
print(f"Covered (name,file) pairs in current CSV: {len(covered)}")

with zipfile.ZipFile(src_zip) as zf:
    znames = set(zf.namelist())
    fc = {}

    # Counters
    smart_right = 0
    smart_wrong = 0
    smart_skip_was_right = 0  # smart skipped, but naive would have been right
    smart_skip_was_wrong = 0  # smart skipped, and naive would have been wrong
    smart_skip_covered = 0   # smart skipped, naive right, but already in CSV
    naive_right = 0
    naive_wrong = 0
    naive_skip = 0
    
    skip_reasons = Counter()
    wrong_examples = []
    skip_right_examples = []

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

        # Smart parser
        smart_end, reason = smart_find_enum_end(fl, start, simple)
        
        # Naive parser (for comparison)
        naive_end = naive_find(fl, start)
        naive_has_result = naive_end != start
        
        if smart_end == start:
            # Smart decided to skip this one
            skip_reasons[reason] += 1
            if naive_has_result:
                right = is_code_right(fl, start, naive_end, simple)
                if right:
                    if (simple, zp) in covered:
                        smart_skip_covered += 1
                    else:
                        smart_skip_was_right += 1
                        if len(skip_right_examples) < 5:
                            skip_right_examples.append((simple, fcol[-60:], start, naive_end, reason,
                                fl[start-1].rstrip()[:120] if start-1 < len(fl) else ""))
                else:
                    smart_skip_was_wrong += 1
        else:
            # Smart found an end
            sei = smart_end - 1
            if sei >= 0 and sei < len(fl) and "}" in fl[sei]:
                right = is_code_right(fl, start, smart_end, simple)
                if right:
                    smart_right += 1
                else:
                    smart_wrong += 1
                    if len(wrong_examples) < 10:
                        wrong_examples.append((simple, fcol[-60:], start, smart_end, reason,
                            fl, start-1, sei))
            else:
                skip_reasons["no_brace_on_end"] += 1
        
        # Naive stats
        if naive_has_result:
            nei = naive_end - 1
            if nei >= 0 and nei < len(fl) and "}" in fl[nei]:
                if is_code_right(fl, start, naive_end, simple):
                    naive_right += 1
                else:
                    naive_wrong += 1
            else:
                naive_skip += 1
        else:
            naive_skip += 1

    print(f"\n{'='*60}")
    print(f"SMART PARSER RESULTS:")
    print(f"  Right code returned:  {smart_right}")
    print(f"  Wrong code returned:  {smart_wrong}")
    print(f"  Skipped (was wrong):  {smart_skip_was_wrong}  (correctly avoided)")
    print(f"  Skipped (covered):    {smart_skip_covered}  (already in CSV from other rows)")
    print(f"  Skipped (real loss):  {smart_skip_was_right}  (not in CSV)")
    
    smart_total_decided = smart_right + smart_wrong
    if smart_total_decided:
        print(f"  Accuracy when it acts: {100*smart_right/smart_total_decided:.1f}%")
    
    print(f"\n{'='*60}")
    print(f"NAIVE PARSER RESULTS (for comparison):")
    print(f"  Right code returned:  {naive_right}")
    print(f"  Wrong code returned:  {naive_wrong}")
    print(f"  Skipped:              {naive_skip}")
    if naive_right + naive_wrong:
        print(f"  Accuracy when it acts: {100*naive_right/(naive_right+naive_wrong):.1f}%")

    print(f"\n{'='*60}")
    print(f"SKIP REASONS:")
    for reason, count in skip_reasons.most_common():
        print(f"  {reason:30s}  {count:>6}")
    
    if wrong_examples:
        print(f"\n{'='*60}")
        print(f"SMART PARSER WRONG RESULTS ({smart_wrong} total, showing first 10):")
        for i, (s, f, st, ne, reason, fl, si, ei) in enumerate(wrong_examples):
            print(f"\n  #{i+1}: '{s}' L{st}-{ne} reason={reason}  ...{f}")
            print(f"    --- source ---")
            for li in range(si, min(ei+1, len(fl))):
                print(f"      {li+1:>6}: {fl[li].rstrip()[:130]}")
    
    if skip_right_examples:
        print(f"\n{'='*60}")
        print(f"SMART SKIPPED BUT NAIVE WAS RIGHT ({smart_skip_was_right} total, showing 10):")
        for i, (s, f, st, ne, reason, fl) in enumerate(skip_right_examples):
            print(f"\n  #{i+1}: '{s}' L{st}-{ne} reason={reason}  ...{f[-60:]}")
            print(f"    --- naive source (what the LLM would get) ---")
            for li in range(st-1, min(ne, len(fl))):
                print(f"      {li+1:>6}: {fl[li].rstrip()[:130]}")
