#!/usr/bin/env python3
"""
External Issues Function Mapper

Maps converted external issues from tools/issues.csv to functions using FunctionTree.csv
"""

import csv
import os
import statistics
from collections import Counter, defaultdict


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
    print("EXTERNAL ISSUES FUNCTION MAPPER")
    print("=" * 35)
    
    issues_file = "tools/issues.csv"
    functions_file = "C:\\code\\codeQL_CoD\\codeql\\FunctionTree.csv"
    
    if not os.path.exists(issues_file):
        print(f"ERROR: {issues_file} not found")
        return 1
        
    if not os.path.exists(functions_file):
        print(f"ERROR: {functions_file} not found")
        return 1
    
    # Read functions efficiently
    print("Reading functions...")
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
    
    # Build index for fast lookups
    print("Building function index...")
    function_index = build_function_index(functions)
    print(f"Indexed {len(function_index):,} file groups")
    
    # Process external issues
    print("Processing external issues...")
    mapped = []
    unmapped = []
    issue_types = Counter()
    file_counts = Counter() 
    
    with open(issues_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            try:
                file_path = row['file']
                line_str = row['start_line']
                issue_type = row['message']
                
                # Track issue types
                issue_types[issue_type] += 1
                
                # Track files
                filename = os.path.basename(file_path)
                file_counts[filename] += 1
                
                # Skip "Various" line numbers
                if line_str == "Various":
                    unmapped.append({
                        'file': file_path,
                        'line': line_str,
                        'type': issue_type,
                        'reason': 'Various line number'
                    })
                    continue
                
                line_number = int(line_str)
                
                # Find containing function
                func = find_matching_function(file_path, line_number, function_index)
                
                if func:
                    mapped.append({
                        'function': func['name'],
                        'file': file_path,
                        'line': line_number,
                        'type': issue_type,
                        'func_length': func['length']
                    })
                else:
                    unmapped.append({
                        'file': file_path,
                        'line': line_number,
                        'type': issue_type,
                        'reason': 'No matching function'
                    })
                    
            except Exception as e:
                unmapped.append({
                    'file': row.get('file', ''),
                    'line': row.get('start_line', ''),
                    'type': row.get('message', ''),
                    'reason': f'Parse error: {e}'
                })
    
    total_issues = len(mapped) + len(unmapped)
    
    # Analysis Results
    print("\\n" + "=" * 50)
    print("EXTERNAL ISSUES ANALYSIS")
    print("=" * 50)
    
    print(f"\\nTotal external issues: {total_issues:,}")
    print(f"Successfully mapped: {len(mapped):,} ({len(mapped)/total_issues*100:.1f}%)")
    print(f"Could not map: {len(unmapped):,} ({len(unmapped)/total_issues*100:.1f}%)")
    
    # Function analysis
    if mapped:
        unique_functions = set(issue['function'] for issue in mapped)
        func_lengths = [issue['func_length'] for issue in mapped]
        
        print(f"\\nFunction Impact:")
        print(f"Vulnerable functions: {len(unique_functions):,}")
        print(f"Total functions scanned: {len(functions):,}")
        print(f"Vulnerability rate: {len(unique_functions)/len(functions)*100:.3f}%")
        
        print(f"\\nVulnerable Function Characteristics:")
        print(f"Average length: {statistics.mean(func_lengths):.1f} lines")
        print(f"Median length: {statistics.median(func_lengths):.1f} lines")
        print(f"Min length: {min(func_lengths)} lines")
        print(f"Max length: {max(func_lengths)} lines")
    
    print(f"\\nTop Issue Types:")
    for issue_type, count in issue_types.most_common(10):
        print(f"  {issue_type}: {count:,} issues ({count/total_issues*100:.1f}%)")
    
    print(f"\\nTop Vulnerable Files:")
    for filename, count in file_counts.most_common(10):
        print(f"  {filename}: {count:,} issues")
    
    # Function issue distribution 
    if mapped:
        func_issue_counts = Counter(issue['function'] for issue in mapped)
        multi_issue_funcs = {name: count for name, count in func_issue_counts.items() if count > 1}
        
        print(f"\\nFunctions with Multiple Issues:")
        print(f"Functions with 2+ issues: {len(multi_issue_funcs):,}")
        
        if multi_issue_funcs:
            print(f"\\nTop 10 Most Vulnerable Functions:")
            for func_name, count in sorted(multi_issue_funcs.items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"  {func_name}: {count} issues")
    
    # Unmapped analysis
    print(f"\\nUnmapped Issues Analysis:")
    unmapped_reasons = Counter(issue['reason'] for issue in unmapped)
    for reason, count in unmapped_reasons.most_common():
        print(f"  {reason}: {count:,} issues")
    
    print("\\n" + "=" * 50)
    print("ANALYSIS COMPLETE")
    print("=" * 50)
    
    return 0


if __name__ == "__main__":
    exit(main())