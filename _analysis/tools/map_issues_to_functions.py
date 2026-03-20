#!/usr/bin/env python3
"""
Map security issues to their containing functions and analyze function lengths.

This script:
1. Reads issues from issues.csv 
2. Maps them to functions in FunctionTree.csv
3. Finds the smallest function containing each issue
4. Provides statistical analysis of function lengths
"""

import csv
import os
import sys
import statistics
from collections import defaultdict, Counter
from pathlib import Path


def read_issues_csv(file_path):
    """Read issues from CSV file."""
    issues = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Assuming first column is variable/offset name and second is description
                variable_name = list(row.values())[0] if row else ""
                description = list(row.values())[1] if len(row.values()) > 1 else ""
                if variable_name and variable_name != "offset":  # Skip header
                    issues.append({
                        'variable': variable_name,
                        'description': description
                    })
    except Exception as e:
        print(f"Error reading issues file: {e}")
        return []
    
    return issues


def read_functions_csv(file_path):
    """Read function information from CSV file."""
    functions = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    start_line = int(row['start_line'])
                    end_line = int(row['end_line'])
                    
                    # Fix negative length calculation - some data might be malformed
                    if end_line >= start_line:
                        length = end_line - start_line + 1
                    else:
                        # If end_line < start_line, skip this function as it's malformed
                        continue
                    
                    # Skip functions with unreasonable lengths
                    if length <= 0 or length > 10000:  # Filter out obviously wrong data
                        continue
                    
                    functions.append({
                        'name': row['function_name'],
                        'file': row['file'],
                        'start_line': start_line,
                        'end_line': end_line,
                        'length': length,
                        'function_id': row['function_id'],
                        'caller_id': row.get('caller_id', '')
                    })
                except (ValueError, KeyError) as e:
                    # Skip malformed rows quietly
                    continue
    except Exception as e:
        print(f"Error reading functions file: {e}")
        return []
    
    return functions


def find_functions_containing_issue(issue_variable, functions):
    """
    Find all functions that might contain the given issue variable.
    
    Uses more specific matching heuristics to avoid too many false positives.
    """
    containing_functions = []
    
    # More targeted matching strategies
    for func in functions:
        func_name_lower = func['name'].lower()
        variable_lower = issue_variable.lower()
        
        # Skip very generic single-letter matches unless they're exact
        if len(variable_lower) == 1 and variable_lower != func_name_lower:
            # Only match single letters to very short function names or exact matches
            if len(func_name_lower) > 5:
                continue
        
        # Strategy 1: Exact substring matches (more specific)
        if (variable_lower in func_name_lower and len(variable_lower) > 2) or \
           (func_name_lower in variable_lower and len(func_name_lower) > 2):
            containing_functions.append(func)
            continue
            
        # Strategy 2: For single character variables, be very selective
        if len(variable_lower) == 1:
            # Only match if function name is also single character or contains the letter
            # in a specific pattern
            if func_name_lower == variable_lower or \
               func_name_lower.endswith(variable_lower) or \
               func_name_lower.startswith(variable_lower):
                containing_functions.append(func)
                continue
        
        # Strategy 3: Known common variable patterns
        common_patterns = {
            'index': ['index', 'idx', 'ind'],
            'count': ['count', 'cnt', 'num'],
            'size': ['size', 'length', 'len'],
            'idx': ['index', 'idx', 'ind'], 
            'len': ['length', 'len', 'size'],
            'i': ['i'],  # Be very specific about 'i' 
            'j': ['j'],  # Be very specific about 'j'
            'k': ['k']   # Be very specific about 'k'
        }
        
        if variable_lower in common_patterns:
            if any(pattern in func_name_lower for pattern in common_patterns[variable_lower]):
                containing_functions.append(func)
    
    # Limit results to prevent overwhelming output
    if len(containing_functions) > 100:
        # Sort by function length and take the smallest ones
        containing_functions = sorted(containing_functions, key=lambda f: f['length'])[:100]
    
    return containing_functions


def find_smallest_function(functions_list):
    """Find the smallest function from a list (innermost/most specific)."""
    if not functions_list:
        return None
    
    return min(functions_list, key=lambda f: f['length'])


def analyze_function_lengths(function_lengths):
    """Provide statistical analysis of function lengths."""
    if not function_lengths:
        return {}
    
    return {
        'count': len(function_lengths),
        'min': min(function_lengths),
        'max': max(function_lengths),
        'mean': statistics.mean(function_lengths),
        'median': statistics.median(function_lengths),
        'mode': statistics.mode(function_lengths) if function_lengths else 0,
        'std_dev': statistics.stdev(function_lengths) if len(function_lengths) > 1 else 0
    }


def main():
    # File paths - adjust these as needed
    script_dir = Path(__file__).parent.parent
    database_path = r"C:\code\codeQL_CoD\codeql"
    
    issues_file = os.path.join(database_path, "issues.csv")
    functions_file = os.path.join(database_path, "FunctionTree.csv")
    
    print("Issue to Function Mapper")
    print("=" * 50)
    
    # Check if files exist
    if not os.path.exists(issues_file):
        print(f"ERROR: Issues file not found: {issues_file}")
        return 1
    
    if not os.path.exists(functions_file):
        print(f"ERROR: Functions file not found: {functions_file}")
        return 1
    
    # Read data
    print("Reading issues...")
    issues = read_issues_csv(issues_file)
    print(f"   Found {len(issues)} issues")
    
    print("Reading functions...")
    functions = read_functions_csv(functions_file)
    print(f"   Found {len(functions)} functions")
    
    # Map issues to functions
    print("\nMapping issues to functions...")
    issue_function_map = {}
    function_lengths = []
    issue_counter = Counter()
    mapped_count = 0
    unmapped_count = 0
    
    # Sample output for first 20 to avoid overwhelming console
    show_detailed = True
    detail_count = 0
    
    for issue in issues:
        variable = issue['variable']
        description = issue['description']
        
        # Find all functions that could contain this issue
        containing_functions = find_functions_containing_issue(variable, functions)
        
        if containing_functions:
            # Find the smallest (most specific) function
            smallest_func = find_smallest_function(containing_functions)
            
            issue_function_map[f"{variable}_{mapped_count}"] = {
                'variable': variable,
                'description': description,
                'function': smallest_func,
                'num_candidates': len(containing_functions)
            }
            
            function_lengths.append(smallest_func['length'])
            issue_counter[variable] += 1
            mapped_count += 1
            
            # Show details for first 20 items
            if show_detailed and detail_count < 20:
                print(f"   {variable} -> {smallest_func['name']} "
                      f"({smallest_func['length']} lines) "
                      f"[{len(containing_functions)} candidates]")
                detail_count += 1
            elif detail_count == 20:
                print("   ... (showing first 20 mappings, use -v for full output) ...")
                show_detailed = False
            
        else:
            unmapped_count += 1
            if detail_count < 20:
                print(f"   {variable} -> No matching functions found")
    
    print(f"\nMapping Summary: {mapped_count} mapped, {unmapped_count} unmapped")
    
    # Statistical Analysis
    print("\nStatistical Analysis")
    print("=" * 30)
    
    if function_lengths:
        stats = analyze_function_lengths(function_lengths)
        
        print(f"Function Length Statistics:")
        print(f"   • Issues mapped to functions: {stats['count']}")
        print(f"   • Shortest function: {stats['min']} lines")
        print(f"   • Longest function: {stats['max']} lines")
        print(f"   • Mean function length: {stats['mean']:.1f} lines")
        print(f"   • Median function length: {stats['median']:.1f} lines")
        print(f"   • Most common length: {stats['mode']} lines")
        print(f"   • Standard deviation: {stats['std_dev']:.1f} lines")
        
        # Length distribution
        print(f"\nFunction Length Distribution:")
        length_bins = {
            "Very Small (1-10 lines)": len([l for l in function_lengths if l <= 10]),
            "Small (11-25 lines)": len([l for l in function_lengths if 11 <= l <= 25]),
            "Medium (26-50 lines)": len([l for l in function_lengths if 26 <= l <= 50]),
            "Large (51-100 lines)": len([l for l in function_lengths if 51 <= l <= 100]),
            "Very Large (>100 lines)": len([l for l in function_lengths if l > 100])
        }
        
        for bin_name, count in length_bins.items():
            percentage = (count / len(function_lengths)) * 100
            print(f"   • {bin_name}: {count} ({percentage:.1f}%)")
        
        # Most problematic variables
        print(f"\nMost Problematic Variables:")
        for variable, count in issue_counter.most_common(10):
            print(f"   • {variable}: {count} issues")
    
    else:
        print("No issues could be mapped to functions")
    
    print(f"\nAnalysis complete! Processed {len(issues)} issues across {len(functions)} functions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())