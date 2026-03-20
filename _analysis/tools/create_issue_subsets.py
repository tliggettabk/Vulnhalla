#!/usr/bin/env python3
"""
External Issues Subset Creator

Creates subset CSV files based on mapping results:
- matched: Issues successfully mapped to functions
- no_line_number: Issues with "Various" line numbers
- unmatched: Issues that couldn't be mapped to functions
"""

import csv
import os
from collections import defaultdict


def build_function_index(functions):
    """Build an index of functions by normalized file path for fast lookups."""
    index = defaultdict(list)
    
    for func in functions:
        # Normalize path
        file_path = func['file'].replace('\\', '/').lower()
        
        # Extract meaningful parts
        parts = file_path.split('/')
        if len(parts) >= 3:
            # Use last 3 parts (like folder/subfolder/filename.cpp)
            normalized = '/'.join(parts[-3:])
        else:
            normalized = file_path
        
        # Also index by just filename
        filename = parts[-1]
        
        index[normalized].append(func)
        index[filename].append(func)
    
    return index


def find_matching_function(file_path, line_number, function_index):
    """Find the function containing the given location."""
    if line_number == "Various" or line_number == 0:
        return None
        
    # Normalize the file path
    normalized_path = file_path.replace('\\', '/').lower()
    
    # Try different ways to match the path
    potential_keys = []
    
    # Extract filename
    filename = normalized_path.split('/')[-1]
    potential_keys.append(filename)
    
    # Extract path components
    parts = normalized_path.split('/')
    for i in range(min(3, len(parts))):
        key = '/'.join(parts[-(i+1):])
        potential_keys.append(key)
    
    # Find candidate functions
    candidates = []
    for key in potential_keys:
        if key in function_index:
            candidates.extend(function_index[key])
    
    if not candidates:
        return None
    
    # Find functions that contain this line  
    containing = []
    for func in candidates:
        try:
            if func['start_line'] <= line_number <= func['end_line']:
                containing.append(func)
        except:
            continue
    
    # Return smallest (innermost) function
    if containing:
        return min(containing, key=lambda f: f['length'])
    
    return None


def main():
    print("EXTERNAL ISSUES SUBSET CREATOR")
    print("=" * 35)
    
    issues_file = "zCoD/external_issues.csv"
    functions_file = "C:\\code\\codeQL_CoD\\codeql\\FunctionTree.csv"
    
    if not os.path.exists(issues_file):
        print(f"ERROR: {issues_file} not found")
        return 1
        
    if not os.path.exists(functions_file):
        print(f"ERROR: {functions_file} not found")
        return 1
    
    # Read functions
    print("Loading functions...")
    functions = []
    with open(functions_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                start = int(row['start_line'])
                end = int(row['end_line'])
                if end >= start and end - start <= 5000:  # Skip huge functions
                    functions.append({
                        'name': row['function_name'],
                        'file': row['file'],
                        'start_line': start,
                        'end_line': end,
                        'length': end - start + 1
                    })
            except:
                continue
    
    print(f"Loaded {len(functions):,} functions")
    
    # Build index
    print("Building function index...")
    function_index = build_function_index(functions)
    
    # Process issues and categorize
    print("Processing and categorizing issues...")
    matched_issues = []
    no_line_issues = []
    unmatched_issues = []
    
    with open(issues_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        
        for row in reader:
            file_path = row['file']
            line_str = row['start_line']
            
            # Check for "Various" line numbers
            if line_str == "Various":
                no_line_issues.append(row)
                continue
            
            try:
                line_number = int(line_str)
                
                # Try to find matching function
                func = find_matching_function(file_path, line_number, function_index)
                
                if func:
                    # Add function info to the row
                    enhanced_row = row.copy()
                    enhanced_row['matched_function'] = func['name']
                    enhanced_row['function_length'] = str(func['length'])
                    matched_issues.append(enhanced_row)
                else:
                    unmatched_issues.append(row)
                    
            except:
                unmatched_issues.append(row)
    
    # Write subset files
    print("\\nWriting subset files...")
    
    # Matched issues (with additional function info)
    matched_file = "zCoD/matched_issues.csv"
    if matched_issues:
        enhanced_fieldnames = fieldnames + ['matched_function', 'function_length']
        with open(matched_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=enhanced_fieldnames)
            writer.writeheader()
            writer.writerows(matched_issues)
        print(f"Created {matched_file} with {len(matched_issues)} issues")
    
    # No line number issues  
    no_line_file = "zCoD/no_line_number_issues.csv"
    if no_line_issues:
        with open(no_line_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(no_line_issues)
        print(f"Created {no_line_file} with {len(no_line_issues)} issues")
    
    # Unmatched issues
    unmatched_file = "zCoD/unmatched_issues.csv"
    if unmatched_issues:
        with open(unmatched_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(unmatched_issues)
        print(f"Created {unmatched_file} with {len(unmatched_issues)} issues")
    
    # Summary
    total = len(matched_issues) + len(no_line_issues) + len(unmatched_issues)
    print("\\n" + "=" * 50)
    print("SUBSET CREATION COMPLETE")
    print("=" * 50)
    print(f"Total issues processed: {total}")
    print(f"Matched (with function): {len(matched_issues)} ({len(matched_issues)/total*100:.1f}%)")
    print(f"No line number: {len(no_line_issues)} ({len(no_line_issues)/total*100:.1f}%)")
    print(f"Unmatched: {len(unmatched_issues)} ({len(unmatched_issues)/total*100:.1f}%)")
    
    return 0


if __name__ == "__main__":
    exit(main())