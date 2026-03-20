#!/usr/bin/env python3
"""
Fast Issue-to-Function Mapper

Efficient version with indexed function lookups.
"""

import csv
import os
import statistics
import re
from collections import Counter, defaultdict


def parse_locations(description):
    """Extract file:line from CodeQL descriptions."""
    pattern = r'([^=\s]+\.(?:cpp|c|h|hpp)):(\d+)'
    matches = re.findall(pattern, description)
    return [(path.strip(), int(line)) for path, line in matches]


def build_function_index(functions):
    """Build an index of functions by normalized file path for fast lookups."""
    index = defaultdict(list)
    
    for func in functions:
        # Normalize and extract just the filename and last few path components
        file_path = func['file'].replace('\\', '/').lower()
        
        # Extract meaningful parts of the path
        parts = file_path.split('/')
        if len(parts) >= 2:
            # Use last 2-3 path components for matching
            key = '/'.join(parts[-2:])  # e.g., "src/snd.cpp"
        else:
            key = parts[-1]  # Just filename
        
        index[key].append(func)
    
    return index


def find_function_for_location(file_path, line_number, function_index):
    """Find function containing the given file:line using the index."""
    # Normalize the file path
    file_path_norm = file_path.replace('\\', '/').lower()
    
    # Try different matching strategies
    parts = file_path_norm.split('/')
    
    # Strategy 1: Try last 2-3 path components
    for i in range(1, min(4, len(parts) + 1)):
        key = '/'.join(parts[-i:])
        if key in function_index:
            candidates = function_index[key]
            break
    else:
        return None  # No matching file found
    
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
    print("FAST ISSUE-TO-FUNCTION MAPPER")
    print("=" * 35)
    
    overrun_file = "C:\\temp\\test-overrun1.csv"
    functions_file = "C:\\code\\codeQL_CoD\\codeql\\FunctionTree.csv"
    
    if not os.path.exists(overrun_file):
        print(f"ERROR: {overrun_file} not found")
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
    
    print(f"Loaded {len(functions)} functions")
    
    # Build index for fast lookups
    print("Building function index...")
    function_index = build_function_index(functions)
    print(f"Indexed {len(function_index)} file groups")
    
    # Process issues
    print("Processing security issues...")
    mapped = []
    unmapped = []
    total_issues = 0
    
    with open(overrun_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            total_issues += 1
            description = list(row.values())[-1]
            locations = parse_locations(description)
            
            found_match = False
            for file_path, line_number in locations:
                func = find_function_for_location(file_path, line_number, function_index)
                if func:
                    mapped.append(func)
                    found_match = True
                    break  # Use first successful match
            
            # Track unmapped issues for analysis
            if not found_match and locations:
                unmapped.append({
                    'description': description.split('.')[0],
                    'locations': locations
                })
    
    print(f"Total issues: {total_issues}")
    print(f"Mapped to functions: {len(mapped)}")
    print(f"Unmapped: {len(unmapped)}")
    print(f"Success rate: {len(mapped)/total_issues*100:.3f}%")
    print()
    
    # Show unmapped issues for analysis
    if unmapped:
        print("UNMAPPED ISSUES (first 10):")
        print("-" * 30)
        for i, issue in enumerate(unmapped[:10]):
            print(f"{i+1}. {issue['description'][:60]}...")
            for file_path, line_num in issue['locations']:
                print(f"   Location: {file_path}:{line_num}")
        print()
    
    if not mapped:
        print("No successful mappings!")
        return 1
    
    # Analyze function lengths
    lengths = [f['length'] for f in mapped]
    
    print("VULNERABLE FUNCTION STATISTICS:")
    print("=" * 35)
    print(f"Functions analyzed: {len(lengths)}")
    print(f"Smallest function: {min(lengths)} lines")
    print(f"Largest function: {max(lengths)} lines")
    print(f"Average function: {statistics.mean(lengths):.1f} lines")
    print(f"Median function: {statistics.median(lengths):.1f} lines")
    print()
    
    # Size distribution
    ranges = [(1, 5), (6, 10), (11, 25), (26, 50), (51, 100), (101, 500), (501, 9999)]
    labels = ['Very Small (1-5)', 'Small (6-10)', 'Medium (11-25)', 
              'Large (26-50)', 'Very Large (51-100)', 'Huge (101-500)', 'Massive (500+)']
    
    print("SIZE DISTRIBUTION OF VULNERABLE FUNCTIONS:")
    total = len(lengths)
    for (min_sz, max_sz), label in zip(ranges, labels):
        count = len([l for l in lengths if min_sz <= l <= max_sz])
        percent = count / total * 100
        print(f"{label:20} {count:>6} ({percent:>5.1f}%)")
    
    # Show examples
    print("\\nSAMPLE VULNERABLE FUNCTIONS:")
    print("-" * 30)
    for i, func in enumerate(mapped[:10]):
        name = func['name'][:30]
        filename = func['file'].split('/')[-1]
        print(f"{name:30} {func['length']:>3} lines in {filename}")
    
    return 0


if __name__ == "__main__":
    exit(main())