#!/usr/bin/env python3
"""
Analyze function lengths from matched issues and create stats report
"""

import csv
import statistics
from collections import Counter


def analyze_matched_function_stats():
    """Analyze function length statistics from matched issues."""
    
    matched_file = "zCoD/matched_issues_with_cids.csv"
    output_file = "zCoD/matched.md"
    
    print("ANALYZING MATCHED ISSUES FUNCTION STATISTICS")
    print("=" * 50)
    
    # Read matched issues
    function_lengths = []
    issues_by_function = Counter()
    issues_by_type = Counter()
    function_details = {}
    
    with open(matched_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            try:
                func_length = int(row['function_length'])
                function_lengths.append(func_length)
                
                func_name = row['matched_function']
                issue_type = row['message']
                file_path = row['file']
                line_number = row['start_line']
                cid = row['name']
                
                issues_by_function[func_name] += 1
                issues_by_type[issue_type] += 1
                
                # Store function details
                if func_name not in function_details:
                    function_details[func_name] = {
                        'length': func_length,
                        'file': file_path,
                        'issues': []
                    }
                
                function_details[func_name]['issues'].append({
                    'cid': cid,
                    'type': issue_type,
                    'line': line_number
                })
                
            except (ValueError, KeyError):
                continue
    
    # Calculate statistics
    if function_lengths:
        total_issues = len(function_lengths)
        unique_functions = len(function_details)
        avg_length = statistics.mean(function_lengths)
        median_length = statistics.median(function_lengths)
        min_length = min(function_lengths)
        max_length = max(function_lengths)
        std_dev = statistics.stdev(function_lengths) if len(function_lengths) > 1 else 0
        
        # Calculate percentiles
        sorted_lengths = sorted(function_lengths)
        p25 = sorted_lengths[int(0.25 * len(sorted_lengths))]
        p75 = sorted_lengths[int(0.75 * len(sorted_lengths))]
        p90 = sorted_lengths[int(0.90 * len(sorted_lengths))]
        
        # Length distribution
        length_ranges = {
            "1-10 lines": len([l for l in function_lengths if 1 <= l <= 10]),
            "11-25 lines": len([l for l in function_lengths if 11 <= l <= 25]),
            "26-50 lines": len([l for l in function_lengths if 26 <= l <= 50]),
            "51-100 lines": len([l for l in function_lengths if 51 <= l <= 100]),
            "101-200 lines": len([l for l in function_lengths if 101 <= l <= 200]),
            "201-500 lines": len([l for l in function_lengths if 201 <= l <= 500]),
            "500+ lines": len([l for l in function_lengths if l > 500]),
        }
        
        # Create markdown report
        md_content = f"""# Matched Issues Function Length Analysis

## Overview
Analysis of function lengths for security issues that were successfully mapped to functions.

## Basic Statistics

| Metric | Value |
|--------|--------|
| **Total Matched Issues** | {total_issues:,} |
| **Unique Vulnerable Functions** | {unique_functions:,} |
| **Average Function Length** | {avg_length:.1f} lines |
| **Median Function Length** | {median_length:.1f} lines |
| **Standard Deviation** | {std_dev:.1f} lines |
| **Minimum Function Length** | {min_length} lines |
| **Maximum Function Length** | {max_length} lines |

## Percentile Distribution

| Percentile | Length (lines) |
|------------|----------------|
| 25th percentile | {p25} |
| 50th percentile (median) | {median_length:.0f} |
| 75th percentile | {p75} |
| 90th percentile | {p90} |

## Function Length Distribution

| Length Range | Issues Count | Percentage |
|--------------|--------------|------------|
"""

        for range_name, count in length_ranges.items():
            percentage = (count / total_issues) * 100
            md_content += f"| {range_name} | {count:,} | {percentage:.1f}% |\n"

        md_content += f"""
## Issue Type Distribution

| Issue Type | Count | Percentage |
|------------|--------|------------|
"""

        for issue_type, count in issues_by_type.most_common():
            percentage = (count / total_issues) * 100
            md_content += f"| {issue_type} | {count:,} | {percentage:.1f}% |\n"

        md_content += f"""
## Functions with Multiple Issues

Functions that contain more than one security issue:

| Function Name | Issues | Length | File |
|---------------|--------|--------|------|
"""

        # Show functions with multiple issues
        multi_issue_functions = [(name, details) for name, details in function_details.items() if len(details['issues']) > 1]
        multi_issue_functions.sort(key=lambda x: len(x[1]['issues']), reverse=True)

        for func_name, details in multi_issue_functions[:15]:  # Top 15
            issue_count = len(details['issues'])
            length = details['length']
            filename = details['file'].split('/')[-1] if '/' in details['file'] else details['file']
            
            # Truncate long function names
            display_name = func_name if len(func_name) <= 40 else func_name[:37] + "..."
            
            md_content += f"| {display_name} | {issue_count} | {length} | {filename} |\n"

        md_content += f"""
## Top 10 Longest Vulnerable Functions

| Function Name | Length | Issues | File |
|---------------|--------|--------|------|
"""

        # Show longest functions
        longest_functions = sorted(function_details.items(), key=lambda x: x[1]['length'], reverse=True)[:10]

        for func_name, details in longest_functions:
            issue_count = len(details['issues'])
            length = details['length']
            filename = details['file'].split('/')[-1] if '/' in details['file'] else details['file']
            
            # Truncate long function names
            display_name = func_name if len(func_name) <= 40 else func_name[:37] + "..."
            
            md_content += f"| {display_name} | {length} | {issue_count} | {filename} |\n"

        md_content += f"""
## Key Insights

### Function Size Distribution
- **{length_ranges['51-100 lines']}/{total_issues} ({(length_ranges['51-100 lines']/total_issues)*100:.1f}%)** of issues are in medium-sized functions (51-100 lines)
- **{length_ranges['26-50 lines']}/{total_issues} ({(length_ranges['26-50 lines']/total_issues)*100:.1f}%)** of issues are in smaller functions (26-50 lines)
- **{length_ranges['101-200 lines']}/{total_issues} ({(length_ranges['101-200 lines']/total_issues)*100:.1f}%)** of issues are in larger functions (101-200 lines)

### Security Hotspots
- **{len(multi_issue_functions)} functions** contain multiple security issues
- Functions with multiple issues may indicate areas requiring focused security review
- Longest vulnerable function: **{max_length} lines**

### Development Recommendations
- Functions over {p90} lines (90th percentile) may benefit from refactoring
- Focus security reviews on the {len([f for f in function_details.values() if len(f['issues']) > 1])} functions with multiple issues
- Consider breaking down functions exceeding 200 lines where practical

---
*Generated from matched issues analysis of Call of Duty external security data*
"""

        # Write the markdown file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        print(f"Analysis complete! Report saved to {output_file}")
        print(f"\nQuick Summary:")
        print(f"  Total matched issues: {total_issues:,}")
        print(f"  Unique functions: {unique_functions:,}")
        print(f"  Average function length: {avg_length:.1f} lines")
        print(f"  Functions with multiple issues: {len(multi_issue_functions)}")
        
    else:
        print("No function length data found in matched issues file")
    
    return 0


if __name__ == "__main__":
    exit(analyze_matched_function_stats())