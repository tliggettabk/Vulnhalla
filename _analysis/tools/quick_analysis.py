#!/usr/bin/env python3
"""
Quick Issue to Function Analysis

Simplified version that focuses on key statistics.
"""

import csv
import os
import statistics
from collections import Counter
from pathlib import Path


def main():
    # File paths
    database_path = r"C:\code\codeQL_CoD\codeql"
    issues_file = os.path.join(database_path, "issues.csv")
    functions_file = os.path.join(database_path, "FunctionTree.csv")
    
    print("ISSUE TO FUNCTION ANALYSIS")
    print("=" * 40)
    
    # Read issues
    issues = []
    with open(issues_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            variable_name = list(row.values())[0] if row else ""
            if variable_name and variable_name != "offset":
                issues.append(variable_name)
    
    # Read functions 
    functions = []
    with open(functions_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                start_line = int(row['start_line'])
                end_line = int(row['end_line'])
                if end_line >= start_line and end_line - start_line <= 1000:
                    length = end_line - start_line + 1
                    functions.append({
                        'name': row['function_name'],
                        'length': length,
                        'file': row['file']
                    })
            except:
                continue
    
    print(f"Issues found: {len(issues)}")
    print(f"Valid functions: {len(functions)}")
    
    # Simple mapping - for common variable names, find smallest functions
    mapped_functions = []
    common_vars = ['i', 'j', 'k', 'index', 'idx', 'count', 'size', 'len']
    
    for issue_var in issues:
        if issue_var.lower() in common_vars:
            # Find smallest functions for common variables  
            smallest_funcs = sorted(functions, key=lambda f: f['length'])[:10]
            mapped_functions.extend([f['length'] for f in smallest_funcs])
        else:
            # Find functions that might contain this specific variable
            matching = [f for f in functions if issue_var.lower() in f['name'].lower()]
            if matching:
                smallest = min(matching, key=lambda f: f['length'])
                mapped_functions.append(smallest['length'])
    
    # Statistics
    if mapped_functions:
        print(f"\nFUNCTION LENGTH STATISTICS:")
        print(f"Functions analyzed: {len(mapped_functions)}")
        print(f"Smallest function: {min(mapped_functions)} lines")
        print(f"Largest function: {max(mapped_functions)} lines") 
        print(f"Average function: {statistics.mean(mapped_functions):.1f} lines")
        print(f"Median function: {statistics.median(mapped_functions):.1f} lines")
        
        # Distribution
        very_small = len([f for f in mapped_functions if f <= 10])
        small = len([f for f in mapped_functions if 11 <= f <= 25])
        medium = len([f for f in mapped_functions if 26 <= f <= 50])
        large = len([f for f in mapped_functions if 51 <= f <= 100])
        very_large = len([f for f in mapped_functions if f > 100])
        
        total = len(mapped_functions)
        print(f"\nFUNCTION SIZE DISTRIBUTION:")
        print(f"Very Small (1-10 lines): {very_small} ({very_small/total*100:.1f}%)")
        print(f"Small (11-25 lines): {small} ({small/total*100:.1f}%)")
        print(f"Medium (26-50 lines): {medium} ({medium/total*100:.1f}%)")
        print(f"Large (51-100 lines): {large} ({large/total*100:.1f}%)")
        print(f"Very Large (>100 lines): {very_large} ({very_large/total*100:.1f}%)")
        
        # Most frequent issue variables
        issue_counts = Counter(issues)
        print(f"\nMOST PROBLEMATIC VARIABLES:")
        for var, count in issue_counts.most_common(10):
            print(f"  {var}: {count} issues")
    
    print(f"\nAnalysis complete!")


if __name__ == "__main__":
    main()