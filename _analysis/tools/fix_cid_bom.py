#!/usr/bin/env python3
"""
Fix CID Tracking - Handle BOM Character

Re-processes external issues with proper CID field handling.
"""

import csv
import os
from datetime import datetime
from collections import defaultdict


def parse_date(date_str):
    """Parse date from MM/DD/YY format to datetime object."""
    try:
        if '/' in date_str:
            month, day, year = date_str.split('/')
            if len(year) == 2:
                year = '20' + year
            return datetime(int(year), int(month), int(day))
    except (ValueError, IndexError):
        return None
    return None


def should_include_issue(first_detected):
    """Check if issue should be included based on first detected date."""
    cutoff_date = datetime(2025, 10, 1)  # 10/1/2025
    issue_date = parse_date(first_detected)
    
    if issue_date is None:
        return True  # Include if we can't parse the date
    
    return issue_date < cutoff_date


def fix_cid_tracking_proper():
    """Re-create external issues files with proper CID tracking - handling BOM."""
    
    reportable_file = r"C:\Users\tliggett\Downloads\Reportable.csv"
    
    # Output files
    external_issues_file = "zCoD/external_issues_with_cids.csv"
    matched_issues_file = "zCoD/matched_issues_with_cids.csv"
    no_line_issues_file = "zCoD/no_line_number_issues_with_cids.csv"
    unmatched_issues_file = "zCoD/unmatched_issues_with_cids.csv"
    mapping_file = "zCoD/cid_mapping_with_cids.csv"
    
    print("FIXING CID TRACKING - HANDLING BOM CHARACTER")
    print("=" * 50)
    
    if not os.path.exists(reportable_file):
        print(f"ERROR: {reportable_file} not found")
        return 1
    
    # Read original Reportable.csv with proper BOM handling
    print("Reading original Reportable.csv...")
    reportable_issues = []
    actual_cid_field = None
    
    with open(reportable_file, 'r', encoding='utf-8-sig') as f:  # utf-8-sig handles BOM
        reader = csv.DictReader(f)
        
        # Find the actual CID field name (might have BOM)
        for field in reader.fieldnames:
            if 'CID' in field:
                actual_cid_field = field
                print(f"Found CID field: '{actual_cid_field}'")
                break
        
        for row in reader:
            reportable_issues.append(row)
    
    print(f"Found {len(reportable_issues)} total issues")
    
    # Convert with proper CID handling
    print("Converting with proper CID tracking...")
    converted_issues = []
    mapping_records = []
    filtered_count = 0
    issue_id = 1
    issues_with_cids = 0
    
    for row in reportable_issues:
        first_detected = row.get('First Detected', '')
        
        if not should_include_issue(first_detected):
            filtered_count += 1
            continue
        
        # Extract data using correct field name
        cid = row.get(actual_cid_field, '').strip() if actual_cid_field else ''
        abk_classification = row.get('2. ABK_Classification', '')
        issue_type = row.get('Type', '')
        checker = row.get('Checker', '')
        file_path = row.get('File', '')
        line_number = row.get('Line Number', '0')
        
        if cid:
            issues_with_cids += 1
        
        # Build name with CID: "CID12345-Issue-Type"
        if cid:
            name_with_cid = f"CID{cid}-{issue_type}"
        else:
            # Use sequential ID for issues without CIDs (if any)
            name_with_cid = f"SEQ{issue_id:04d}-{issue_type}"
        
        # Build help field: CID + " " + ABK_Classification
        help_text = f"{cid} {abk_classification}".strip()
        
        # Create issues.csv row with CID in name
        issues_row = {
            'name': name_with_cid,  # Now includes CID for tracking
            'help': help_text,
            'type': checker,
            'message': issue_type,
            'file': file_path,
            'start_line': line_number,
            'start_offset': '0',
            'end_line': line_number,
            'end_offset': '0'
        }
        
        converted_issues.append(issues_row)
        
        # Create proper mapping record
        mapping_record = {
            'issue_id': issue_id,
            'original_cid': cid,
            'first_detected': first_detected,
            'severity': row.get('Severity', ''),
            'component': row.get('Component', ''),
            'function': row.get('Function', ''),
            'impact': row.get('Impact', ''),
            'abk_classification': abk_classification,
            'name_with_cid': name_with_cid
        }
        
        mapping_records.append(mapping_record)
        issue_id += 1
    
    # Write fixed external issues file
    print(f"Writing {external_issues_file}...")
    fieldnames = ['name', 'help', 'type', 'message', 'file', 'start_line', 'start_offset', 'end_line', 'end_offset']
    
    with open(external_issues_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(converted_issues)
    
    # Write fixed mapping file
    print(f"Writing {mapping_file}...")
    mapping_fieldnames = ['issue_id', 'original_cid', 'first_detected', 'severity', 'component', 'function', 'impact', 'abk_classification', 'name_with_cid']
    
    with open(mapping_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=mapping_fieldnames)
        writer.writeheader()
        writer.writerows(mapping_records)
    
    print(f"\\nResults:")
    print(f"  Total issues processed: {len(converted_issues)}")
    print(f"  Issues filtered by date: {filtered_count}")
    print(f"  Issues with CID tracking: {issues_with_cids}")
    
    # Load function data for mapping
    functions_file = "C:\\code\\codeQL_CoD\\codeql\\FunctionTree.csv"
    if not os.path.exists(functions_file):
        print(f"Warning: {functions_file} not found - skipping subset creation")
        return 0
    
    # Load functions
    print("\\nLoading functions for subset creation...")
    functions = []
    with open(functions_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                start = int(row['start_line'])
                end = int(row['end_line'])
                if end >= start and end - start <= 5000:
                    functions.append({
                        'name': row['function_name'],
                        'file': row['file'],
                        'start_line': start,
                        'end_line': end,
                        'length': end - start + 1
                    })
            except:
                continue
    
    # Build function index  
    function_index = defaultdict(list)
    
    for func in functions:
        file_path = func['file'].replace('\\\\', '/').lower()
        parts = file_path.split('/')
        if len(parts) >= 3:
            normalized = '/'.join(parts[-3:])
        else:
            normalized = file_path
        filename = parts[-1]
        
        function_index[normalized].append(func)
        function_index[filename].append(func)
    
    # Function matching
    def find_matching_function(file_path, line_number, function_index):
        if line_number == "Various" or line_number == 0:
            return None
            
        normalized_path = file_path.replace('\\\\', '/').lower()
        
        potential_keys = []
        filename = normalized_path.split('/')[-1]
        potential_keys.append(filename)
        
        parts = normalized_path.split('/')
        for i in range(min(3, len(parts))):
            key = '/'.join(parts[-(i+1):])
            potential_keys.append(key)
        
        candidates = []
        for key in potential_keys:
            if key in function_index:
                candidates.extend(function_index[key])
        
        if not candidates:
            return None
        
        containing = []
        for func in candidates:
            try:
                if func['start_line'] <= line_number <= func['end_line']:
                    containing.append(func)
            except:
                continue
        
        if containing:
            return min(containing, key=lambda f: f['length'])
        
        return None
    
    # Categorize issues
    print("Creating subset files with proper CID tracking...")
    matched_issues = []
    no_line_issues = []
    unmatched_issues = []
    
    for row in converted_issues:
        file_path = row['file']
        line_str = row['start_line']
        
        if line_str == "Various":
            no_line_issues.append(row)
            continue
        
        try:
            line_number = int(line_str)
            func = find_matching_function(file_path, line_number, function_index)
            
            if func:
                enhanced_row = row.copy()
                enhanced_row['matched_function'] = func['name']
                enhanced_row['function_length'] = str(func['length'])
                matched_issues.append(enhanced_row)
            else:
                unmatched_issues.append(row)
                
        except:
            unmatched_issues.append(row)
    
    # Write subset files
    if matched_issues:
        enhanced_fieldnames = fieldnames + ['matched_function', 'function_length']
        with open(matched_issues_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=enhanced_fieldnames)
            writer.writeheader()
            writer.writerows(matched_issues)
        print(f"Created {matched_issues_file} with {len(matched_issues)} issues")
    
    if no_line_issues:
        with open(no_line_issues_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(no_line_issues)
        print(f"Created {no_line_issues_file} with {len(no_line_issues)} issues")
    
    if unmatched_issues:
        with open(unmatched_issues_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(unmatched_issues)
        print(f"Created {unmatched_issues_file} with {len(unmatched_issues)} issues")
    
    print("\\n" + "=" * 60)
    print("CID TRACKING FIXED - BOM ISSUE RESOLVED")
    print("=" * 60)
    print(f"All files now include proper CID tracking in name field")
    print(f"Use '*_with_cids.csv' files for proper CID traceability")
    
    return 0


if __name__ == "__main__":
    exit(fix_cid_tracking_proper())