#!/usr/bin/env python3
"""
External Issues Analyzer

Analyzes converted external issues from tools/issues.csv using the function mapping approach.
"""

import csv
import os
import statistics
import re
from collections import Counter, defaultdict


def build_function_index(functions):
    """Build an index of functions by normalized file path for fast lookups."""
    index = defaultdict(list)
    
    for func in functions:
        # Normalize and extract just the filename and last few path components
        file_path = func['file'].replace('\\', '/').lower()
        
        # Extract meaningful parts of the path
        parts = file_path.split('/')
        if len(parts) >= 3:
            # Use last 3 parts (like folder/subfolder/filename.cpp)
            normalized = '/'.join(parts[-3:])
        else:
            # Use full path if short
            normalized = file_path
        
        index[normalized].append(func)
    
    return index


def find_matching_function(file_path, line_number, function_index):
    """Find the function containing the given location using the index."""
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
        if func['start_line'] <= line_number <= func['end_line']:
            containing.append(func)
    
    # Return smallest (innermost) function
    if containing:
        return min(containing, key=lambda f: f['length'])
    
    return None


def main():
    print("EXTERNAL ISSUES ANALYZER")
    print("=" * 25)
    
    issues_file = "tools/issues.csv"
    functions_file = "C:\\code\\codeQL_CoD\\codeql\\FunctionTree.csv"
    
    if not os.path.exists(issues_file):
        print(f"Error: {issues_file} not found!")
        return
        
    if not os.path.exists(functions_file):
        print(f"Error: {functions_file} not found!")
        return
    
    print(f"Loading functions from: {functions_file}")
    functions = []
    with open(functions_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            functions.append({
                'function_name': row['function_name'],
                'file': row['file_path'],
                'start_line': int(row['start_line']),
                'end_line': int(row['end_line']),
                'length': int(row['end_line']) - int(row['start_line']) + 1
            })
    
    print(f"Loaded {len(functions):,} functions")
    
    # Build function index
    print("Building function index...")
    function_index = build_function_index(functions)
    print(f"Indexed functions across {len(function_index):,} normalized paths")
    
    print(f"\\nLoading issues from: {issues_file}")
    issues = []
    with open(issues_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            issues.append({
                'file': row['file'],
                'line': int(row['line']),
                'message': row['message'],
                'description': row['description'],
                'help': row['help']
            })
    
    print(f"Loaded {len(issues):,} external issues")
    
    # Map issues to functions
    print("\\nMapping issues to functions...")
    mapped_count = 0
    unmapped_count = 0
    function_issues = defaultdict(list)
    issue_types = Counter()
    vulnerable_functions = set()
    function_lines = []
    file_counts = Counter()
    
    for issue in issues:
        file_path = issue['file']
        line_number = issue['line']
        
        # Track issue types
        issue_types[issue['message']] += 1
        
        # Track files with issues
        filename = os.path.basename(file_path)
        file_counts[filename] += 1
        
        # Find containing function
        func = find_matching_function(file_path, line_number, function_index)
        
        if func:
            mapped_count += 1
            function_issues[func['function_name']].append(issue)
            vulnerable_functions.add(func['function_name'])
            function_lines.append(func['length'])
        else:
            unmapped_count += 1
    
    # Results
    print("\\n" + "=" * 50)
    print("EXTERNAL ISSUES ANALYSIS RESULTS")
    print("=" * 50)
    
    print(f"\\nIssue Mapping:")
    print(f"  Successfully mapped: {mapped_count:,} issues ({mapped_count/len(issues)*100:.1f}%)")
    print(f"  Could not map: {unmapped_count:,} issues ({unmapped_count/len(issues)*100:.1f}%)")
    
    print(f"\\nFunction Analysis:")
    print(f"  Total vulnerable functions: {len(vulnerable_functions):,}")
    print(f"  Total functions scanned: {len(functions):,}")
    print(f"  Vulnerability rate: {len(vulnerable_functions)/len(functions)*100:.3f}%")
    
    if function_lines:
        print(f"\\nVulnerable Function Characteristics:")
        print(f"  Average function length: {statistics.mean(function_lines):.1f} lines")
        print(f"  Median function length: {statistics.median(function_lines):.1f} lines")
        print(f"  Min function length: {min(function_lines)} lines")
        print(f"  Max function length: {max(function_lines)} lines")
    
    print(f"\\nIssue Type Distribution:")
    for issue_type, count in issue_types.most_common(10):
        print(f"  {issue_type}: {count:,} issues ({count/len(issues)*100:.1f}%)")
    
    print(f"\\nTop Vulnerable Files:")
    for filename, count in file_counts.most_common(10):
        print(f"  {filename}: {count:,} issues")
    
    print(f"\\nFunctions with Multiple Issues:")
    multi_issue_functions = [(name, len(issues)) for name, issues in function_issues.items() if len(issues) > 1]
    multi_issue_functions.sort(key=lambda x: x[1], reverse=True)
    
    print(f"  Functions with 2+ issues: {len(multi_issue_functions):,}")
    
    if multi_issue_functions:
        print(f"\\nTop 10 Most Vulnerable Functions:")
        for func_name, issue_count in multi_issue_functions[:10]:
            print(f"    {func_name}: {issue_count} issues")
    
    print("\\n" + "=" * 50)
    print("ANALYSIS COMPLETE")
    print("=" * 50)


if __name__ == "__main__":
    main()