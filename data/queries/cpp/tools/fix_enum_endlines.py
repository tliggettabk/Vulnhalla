"""
fix_enum_endlines.py
====================
Post-process EnumLookup.csv to fix end_line values.

CodeQL reports end_line == start_line for many enum/enum-class types.
This script opens the source from src.zip and scans forward from start_line
to find the closing '};' brace, then rewrites the CSV with corrected end_lines.

Usage:
    python data/queries/cpp/tools/fix_enum_endlines.py <db_path>

Example:
    python data/queries/cpp/tools/fix_enum_endlines.py C:\\code\\codeQL_CoD\\codeql
"""
import csv
import re
import sys
import zipfile
from pathlib import Path


def normalize_zip_path(raw_file: str) -> str:
    """Convert a CodeQL file column value to the path used inside src.zip.
    
    Zip structure uses drive_letter + '_' instead of ':'.
    E.g. 'D:/mapped_drives/...' → 'D_/mapped_drives/...'
         'C:/vendor/...'        → 'C_/vendor/...'
    """
    path = raw_file.strip().strip('"').replace("\\", "/")
    path = path.replace(":", "_", 1)           # D:/foo → D_/foo, C:/bar → C_/bar
    return path


def find_enum_end(lines: list[str], start_line: int) -> int:
    """
    Given full file lines (0-indexed list) and a 1-indexed start_line,
    scan forward to find the closing '};' of an enum definition.

    Returns corrected 1-indexed end_line, or start_line if we can't find it.

    Guards:
    - Detects forward declarations (no '{' within 3 lines) and returns start_line.
    - Only scans up to 200 lines.
    - Strips // comments before counting braces.
    - Post-validates: if the computed end_line doesn't contain '}', reverts to start_line.
    """
    # start_line is 1-indexed; convert to 0-indexed
    idx = start_line - 1
    if idx < 0 or idx >= len(lines):
        return start_line

    # Guard: check if there's an opening '{' within the first 4 lines.
    # If not, this is a forward declaration like "enum X : int;" — keep single-line.
    has_open_brace = False
    for i in range(idx, min(idx + 4, len(lines))):
        if '{' in lines[i]:
            has_open_brace = True
            break
    if not has_open_brace:
        return start_line

    # Scan forward, counting braces (strip line comments first)
    brace_depth = 0
    found_open = False
    for i in range(idx, min(idx + 200, len(lines))):
        line = lines[i]
        # Strip // line comments to avoid counting braces in comments
        comment_pos = line.find('//')
        if comment_pos >= 0:
            line = line[:comment_pos]
        for ch in line:
            if ch == '{':
                brace_depth += 1
                found_open = True
            elif ch == '}':
                brace_depth -= 1
                if found_open and brace_depth == 0:
                    candidate = i + 1  # 1-indexed
                    # Post-validate: the end line MUST contain '}'
                    if '}' in lines[i]:
                        return candidate
                    else:
                        return start_line
    return start_line


def main():
    if len(sys.argv) < 2:
        print("Usage: python fix_enum_endlines.py <db_path>")
        sys.exit(1)

    db_path = Path(sys.argv[1])
    csv_path = db_path / "EnumLookup.csv"
    src_zip_path = db_path / "src.zip"

    if not csv_path.exists():
        print(f"ERROR: {csv_path} not found")
        sys.exit(1)
    if not src_zip_path.exists():
        print(f"ERROR: {src_zip_path} not found")
        sys.exit(1)

    # Read all rows
    rows = []
    header = None
    with open(csv_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            # Skip header row (from bqrs decode)
            if header is None and "start_line" in line and "end_line" in line:
                header = line
                continue
            rows.append(line)

    print(f"Read {len(rows)} rows from EnumLookup.csv")

    # Cache of file contents from src.zip (file_path -> lines list)
    file_cache: dict[str, list[str] | None] = {}
    fixed = 0
    failed_files = set()

    # Open the zip once for efficiency
    with zipfile.ZipFile(str(src_zip_path), "r") as zf:
        zip_namelist = set(zf.namelist())

        new_rows = []
        for row_str in rows:
            # Parse the CSV row: "Enum","name","file",start,end,"simple_name"
            # Use csv reader for proper quote handling
            parsed = list(csv.reader([row_str]))[0]
            if len(parsed) < 6:
                new_rows.append(row_str)
                continue

            etype, name, file_col, start_str, end_str, simple_name = parsed[:6]
            start_line = int(start_str)
            end_line = int(end_str)

            if end_line > start_line:
                # Already has a proper end_line (and it's sane), keep it
                new_rows.append(row_str)
                continue

            # Need to fix end_line
            zip_path = normalize_zip_path(file_col)

            if zip_path not in file_cache:
                if zip_path in zip_namelist:
                    try:
                        content = zf.read(zip_path).decode("utf-8", errors="replace")
                        content = content.replace("\r\n", "\n").replace("\r", "\n")
                        file_cache[zip_path] = content.split("\n")
                    except Exception:
                        file_cache[zip_path] = None
                        failed_files.add(zip_path)
                else:
                    file_cache[zip_path] = None
                    failed_files.add(zip_path)

            lines = file_cache[zip_path]
            if lines is not None:
                new_end = find_enum_end(lines, start_line)
                if new_end != start_line:
                    end_line = new_end
                    fixed += 1

            # Safety clamp: end_line must be >= start_line
            if end_line < start_line:
                end_line = start_line

            # Rebuild the row with corrected end_line
            new_row = f'"{etype}","{name}","{file_col}",{start_line},{end_line},"{simple_name}"'
            new_rows.append(new_row)

    # Verify: for every multi-line row, check that end_line actually has '}'
    # in the source. If not, revert to single-line (start==end).
    # This catches cases where the brace scanner matched braces from surrounding
    # code (class, namespace, etc.) rather than the enum itself.
    verified_rows = []
    reverted = 0
    for row_str in new_rows:
        parsed = list(csv.reader([row_str]))[0]
        if len(parsed) >= 6:
            start = int(parsed[3])
            end = int(parsed[4])
            if end > start:
                file_col = parsed[2]
                zip_path = normalize_zip_path(file_col)
                file_lines = file_cache.get(zip_path)
                end_idx = end - 1  # 0-indexed
                if file_lines is not None and 0 <= end_idx < len(file_lines):
                    if "}" not in file_lines[end_idx]:
                        # Bad end_line — revert to single-line
                        row_str = f'"{parsed[0]}","{parsed[1]}","{file_col}",{start},{start},"{parsed[5]}"'
                        reverted += 1
                else:
                    # Can't verify (file missing or out of range) — revert to single-line
                    row_str = f'"{parsed[0]}","{parsed[1]}","{parsed[2]}",{start},{start},"{parsed[5]}"'
                    reverted += 1
        verified_rows.append(row_str)

    new_rows = verified_rows

    # Dedup: remove single-line rows when a multi-line row exists for the same simple_name.
    # get_class() returns the first match, so keeping dead single-line duplicates
    # is both a performance and correctness problem.
    multi_line_names = set()
    for row_str in new_rows:
        parsed = list(csv.reader([row_str]))[0]
        if len(parsed) >= 6:
            start = int(parsed[3])
            end = int(parsed[4])
            if end > start:
                multi_line_names.add(parsed[5].strip('"'))

    deduped_rows = []
    removed = 0
    for row_str in new_rows:
        parsed = list(csv.reader([row_str]))[0]
        if len(parsed) >= 6:
            start = int(parsed[3])
            end = int(parsed[4])
            simple = parsed[5].strip('"')
            if start == end and simple in multi_line_names:
                removed += 1
                continue
        deduped_rows.append(row_str)

    # Write back
    with open(csv_path, "w", encoding="utf-8", newline="\n") as f:
        for row in deduped_rows:
            f.write(row + "\n")

    print(f"Fixed {fixed} end_lines out of {len(rows)} rows")
    print(f"Reverted {reverted} bad end_lines (no '}}' at end_line in source)")
    print(f"Removed {removed} single-line duplicates (multi-line version exists)")
    print(f"Final row count: {len(deduped_rows)}")
    if failed_files:
        print(f"Could not read {len(failed_files)} files from src.zip (external/vendor headers)")


if __name__ == "__main__":
    main()
