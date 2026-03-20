#!/usr/bin/env python3
"""
Search for related g_scr files that do have functions
"""

import csv
import os
from collections import Counter


def find_related_gscr_files():
    """Find files with similar names that do have functions."""
    
    functions_file = "C:\\code\\codeQL_CoD\\codeql\\FunctionTree.csv"
    
    print("SEARCHING FOR RELATED G_SCR FILES WITH FUNCTIONS")
    print("=" * 50)
    
    related_files = Counter()
    
    with open(functions_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            file_path = row.get('file', '') or row.get('file_path', '')
            filename = os.path.basename(file_path).lower()
            
            # Look for files that contain "g_scr" or "gscr" or "scr_main"
            if any(pattern in filename for pattern in ['g_scr', 'gscr', 'scr_main']):
                related_files[file_path] += 1
    
    if related_files:
        print(f"Found {len(related_files)} related files with functions:")
        print("-" * 60)
        
        for file_path, func_count in related_files.most_common():
            print(f"{func_count:3d} functions: {file_path}")
        
        # Also show some sample function names from the most common file
        if related_files:
            top_file = related_files.most_common(1)[0][0]
            print(f"\\nSample functions from {os.path.basename(top_file)}:")
            
            sample_count = 0
            with open(functions_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    file_path = row.get('file', '') or row.get('file_path', '')
                    if file_path == top_file:
                        func_name = row.get('function_name', 'N/A')
                        start_line = row.get('start_line', 'N/A')
                        end_line = row.get('end_line', 'N/A')
                        print(f"  {func_name} (lines {start_line}-{end_line})")
                        sample_count += 1
                        if sample_count >= 5:
                            break
    
    else:
        print("No related g_scr files found with functions")
    
    return 0


if __name__ == "__main__":
    exit(find_related_gscr_files())