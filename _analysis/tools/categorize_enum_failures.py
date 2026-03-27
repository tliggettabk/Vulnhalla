"""
Categorize the 1,824 enum end_line failures to understand the error patterns.
"""
import csv
import sys
import zipfile

db = sys.argv[1] if len(sys.argv) > 1 else r"C:\code\codeQL_CoD\codeql"
enum_csv = db + "\\EnumLookup.csv"
src_zip = db + "\\src.zip"


def norm(raw):
    p = raw.strip().strip('"').replace("\\", "/")
    p = p.replace(":", "_", 1)
    return p


rows = []
with open(enum_csv, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        parsed = list(csv.reader([line]))[0]
        if len(parsed) >= 6:
            start = int(parsed[3])
            end = int(parsed[4])
            if end > start:
                rows.append(parsed)

with zipfile.ZipFile(src_zip) as zf:
    zip_names = set(zf.namelist())
    file_cache = {}

    categories = {
        "forward_decl_at_end": 0,      # end_line is a forward decl like "enum X : int;"
        "wrong_scope_landed": 0,        # brace matched a different scope (class, namespace, etc.)
        "macro_body": 0,                # end_line is inside #define / #include expansion
        "end_out_of_range": 0,          # end_line beyond file length
        "empty_or_comment": 0,          # end_line is blank or comment
        "other": 0,
    }
    # Also track: how many are project vs vendor
    proj_fail = 0
    vendor_fail = 0
    # Track span sizes of failures
    fail_spans = []

    for r in rows:
        name = r[1].strip('"')
        file_col = r[2]
        start = int(r[3])
        end = int(r[4])
        zp = norm(file_col)

        if zp not in file_cache:
            if zp in zip_names:
                try:
                    content = zf.read(zp).decode("utf-8", errors="replace")
                    content = content.replace("\r\n", "\n").replace("\r", "\n")
                    file_cache[zp] = content.split("\n")
                except Exception:
                    file_cache[zp] = None
            else:
                file_cache[zp] = None

        lines = file_cache.get(zp)
        if lines is None:
            continue

        end_idx = end - 1
        if end_idx < 0 or end_idx >= len(lines):
            categories["end_out_of_range"] += 1
            if "mapped_drives" in file_col:
                proj_fail += 1
            else:
                vendor_fail += 1
            fail_spans.append(end - start)
            continue

        end_text = lines[end_idx]
        if "}" in end_text:
            continue  # PASS

        # Categorize the failure
        is_proj = "mapped_drives" in file_col
        if is_proj:
            proj_fail += 1
        else:
            vendor_fail += 1
        fail_spans.append(end - start)

        stripped = end_text.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
            categories["empty_or_comment"] += 1
        elif "enum" in stripped and ";" in stripped:
            categories["forward_decl_at_end"] += 1
        elif stripped.startswith("#"):
            categories["macro_body"] += 1
        elif any(kw in stripped for kw in ["struct ", "class ", "namespace ", "extern "]):
            categories["wrong_scope_landed"] += 1
        else:
            categories["other"] += 1

total_fail = sum(categories.values())
print(f"Total failures: {total_fail}")
print(f"  Project files: {proj_fail}")
print(f"  Vendor files:  {vendor_fail}")
print()
print("Failure categories:")
for cat, cnt in sorted(categories.items(), key=lambda x: -x[1]):
    pct = 100 * cnt / total_fail if total_fail else 0
    print(f"  {cat:<25} {cnt:>5}  ({pct:.1f}%)")

print()
if fail_spans:
    fail_spans.sort()
    print(f"Span sizes of failed enums:")
    print(f"  Min: {min(fail_spans)}, Max: {max(fail_spans)}, Median: {fail_spans[len(fail_spans)//2]}")
    short = sum(1 for s in fail_spans if s <= 5)
    long_ = sum(1 for s in fail_spans if s > 100)
    print(f"  Short (<=5 lines): {short}")
    print(f"  Long (>100 lines): {long_}")

# Impact assessment: for failures, is the span wildly wrong? 
# Check if the REAL enum body is within the span
print()
print("--- Impact: do the bad spans at least CONTAIN the real enum? ---")
contains_enum = 0
doesnt_contain = 0
for r in rows:
    name = r[1].strip('"')
    file_col = r[2]
    start = int(r[3])
    end = int(r[4])
    zp = norm(file_col)
    lines = file_cache.get(zp)
    if lines is None:
        continue
    end_idx = end - 1
    if end_idx < 0 or end_idx >= len(lines):
        doesnt_contain += 1
        continue
    if "}" in lines[end_idx]:
        continue  # pass, skip
    
    # Check: does ANY line in [start, end] have "};"?
    found_close = False
    for i in range(start - 1, min(end, len(lines))):
        if "};" in lines[i] or ("}" in lines[i] and i > start - 1):
            found_close = True
            break
    if found_close:
        contains_enum += 1
    else:
        doesnt_contain += 1

print(f"  Span CONTAINS the real enum body:     {contains_enum}")
print(f"  Span does NOT contain enum body:       {doesnt_contain}")
print(f"  (i.e. overshot = {contains_enum}, missed entirely = {doesnt_contain})")
