#!/usr/bin/env python3
"""
Proper Issue-to-Function Mapper with Location Data

Uses actual file:line information from CodeQL results to map 
security issues to their containing functions.
"""

import csv
import os
import statistics
import re
from collections import Counter, defaultdict


def parse_location_from_description(description):
    """
    Extract file:line information from CodeQL descriptions.
    
    Example: "Index may be outside the range [0..63]. Sink= code/src/snd/snd.cpp:16233"
    Returns: [("code/src/snd/snd.cpp", 16233), ...]
    """
    locations = []
    
    # Pattern to match file:line format
    pattern = r'([^=\s]+\.(?:cpp|c|h|hpp)):(\d+)'
    matches = re.findall(pattern, description)
    
    for file_path, line_num in matches:
        try:
            locations.append((file_path.strip(), int(line_num)))
        except ValueError:
            continue
    
    return locations


def normalize_path(path):
    """Normalize file paths for comparison."""
    return path.replace('\\', '/').lower()


def find_containing_function(file_path, line_number, functions):
    """
    Find the innermost function that contains the given file:line.
    
    Returns the function dict if found, None otherwise.
    """
    file_path_norm = normalize_path(file_path)
    
    # Find all functions in the same file that could contain this line
    candidates = []
    
    for func in functions:
        func_file_norm = normalize_path(func['file'])
        
        # Check if files match (handle different path formats)
        if file_path_norm in func_file_norm or func_file_norm in file_path_norm:
            # Check if line is within function bounds
            if func['start_line'] <= line_number <= func['end_line']:
                candidates.append(func)
    
    # Return the smallest (innermost) function
    if candidates:
        return min(candidates, key=lambda f: f['length'])
    
    return None


def main():
    print("ISSUE TO FUNCTION MAPPER WITH LOCATIONS")
    print("=" * 45)
    
    # Use the better data source
    overrun_file = "C:\\temp\\test-overrun1.csv"
    functions_file = "C:\\code\\codeQL_CoD\\codeql\\FunctionTree.csv"
    
    # Check files exist
    if not os.path.exists(overrun_file):
        print(f"ERROR: {overrun_file} not found")
        print("Run: codeql bqrs decode overrun1.bqrs --format=csv --output=C:\\temp\\test-overrun1.csv")
        return 1
        
    if not os.path.exists(functions_file):
        print(f"ERROR: {functions_file} not found")
        return 1
    
    # Read function data
    print("Reading function data...")
    functions = []
    with open(functions_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                start_line = int(row['start_line'])
                end_line = int(row['end_line'])
                if end_line >= start_line:
                    length = end_line - start_line + 1
                    functions.append({
                        'name': row['function_name'],
                        'file': row['file'],
                        'start_line': start_line,
                        'end_line': end_line,
                        'length': length,
                        'function_id': row['function_id']
                    })
            except (ValueError, KeyError):
                continue
    
    print(f"Loaded {len(functions)} functions")
    
    # Read issue data with locations
    print("Reading security issues...")
    issues_mapped = []
    issues_unmapped = []
    
    with open(overrun_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for i, row in enumerate(reader):
            description = list(row.values())[-1]  # Last column has the description
            locations = parse_location_from_description(description)
            
            mapped_to_function = False
            
            for file_path, line_number in locations:
                func = find_containing_function(file_path, line_number, functions)
                
                if func:
                    issues_mapped.append({
                        'issue_id': i,
                        'file': file_path,
                        'line': line_number,
                        'function': func,
                        'description': description.split('.')[0]  # Short description
                    })
                    mapped_to_function = True
                    break  # Use first successful mapping
            
            if not mapped_to_function and locations:
                issues_unmapped.append({
                    'issue_id': i,
                    'locations': locations,
                    'description': description.split('.')[0]
                })
    
    print(f"Issues processed: {len(issues_mapped) + len(issues_unmapped)}")
    print(f"Mapped to functions: {len(issues_mapped)}")
    print(f"Unmapped: {len(issues_unmapped)}")
    print()
    
    if not issues_mapped:
        print("No issues could be mapped to functions!")
        return 1
    
    # Analyze function lengths containing security issues
    function_lengths = [issue['function']['length'] for issue in issues_mapped]
    
    print("SECURITY ISSUE FUNCTION LENGTH STATISTICS")
    print("=" * 45)
    print(f"Functions with security issues: {len(function_lengths)}")
    print(f"Smallest vulnerable function: {min(function_lengths)} lines")
    print(f"Largest vulnerable function: {max(function_lengths)} lines")
    print(f"Average vulnerable function: {statistics.mean(function_lengths):.1f} lines")
    print(f"Median vulnerable function: {statistics.median(function_lengths):.1f} lines")
    print()
    
    # Size distribution of vulnerable functions
    ranges = [(1, 5), (6, 10), (11, 25), (26, 50), (51, 100), (101, 500), (501, float('inf'))]
    labels = ['Very Small (1-5)', 'Small (6-10)', 'Medium (11-25)', 'Large (26-50)', 
              'Very Large (51-100)', 'Huge (101-500)', 'Massive (500+)']
    
    print("VULNERABLE FUNCTION SIZE DISTRIBUTION:")
    print("-" * 40)
    total = len(function_lengths)
    for (min_size, max_size), label in zip(ranges, labels):
        count = len([l for l in function_lengths if min_size <= l < max_size])
        percent = count / total * 100 if total > 0 else 0
        print(f"{label:20} {count:>6} ({percent:>5.1f}%)")
    
    print()
    
    # Most vulnerable files
    file_counter = Counter([issue['file'] for issue in issues_mapped])
    print("MOST VULNERABLE FILES:")
    print("-" * 25)
    for file_name, count in file_counter.most_common(10):
        short_name = file_name.split('/')[-1]  # Just filename
        print(f"{short_name:30} {count:>3} issues")
    
    print()
    
    # Show some examples
    print("SAMPLE VULNERABLE FUNCTIONS:")
    print("-" * 30)
    for i, issue in enumerate(issues_mapped[:10]):
        func_name = issue['function']['name'][:25]
        file_name = issue['file'].split('/')[-1]
        print(f"{func_name:25} {issue['function']['length']:>3} lines in {file_name}")
    
    print(f"\\nAnalysis complete! Found {len(function_lengths)} vulnerable functions.")
    return 0


if __name__ == "__main__":
    exit(main())