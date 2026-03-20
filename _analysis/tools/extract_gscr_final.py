#!/usr/bin/env python3
"""
Extract functions from g_scr_main_mp.cpp using correct path format
"""

import csv
import os


def extract_gscr_functions_correct():
    """Extract functions from g_scr_main_mp.cpp using the actual database path format."""
    
    functions_file = "C:\\code\\codeQL_CoD\\codeql\\FunctionTree.csv"
    output_file = "zCoD/g_scr_main_mp_functions.csv"
    
    print("EXTRACTING G_SCR_MAIN_MP.CPP FUNCTIONS")
    print("=" * 40)
    
    if not os.path.exists(functions_file):
        print(f"ERROR: {functions_file} not found")
        return 1
    
    # Search for g_scr_main_mp.cpp in any path format
    print("Searching for g_scr_main_mp.cpp functions...")
    gscr_functions = []
    matching_paths = set()
    
    with open(functions_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        
        total_count = 0
        for row in reader:
            total_count += 1
            file_path = row.get('file', '') or row.get('file_path', '')
            
            # Check if the file path contains g_scr_main_mp.cpp
            if 'g_scr_main_mp.cpp' in file_path:
                gscr_functions.append(row)
                matching_paths.add(file_path)
    
    print(f"Searched {total_count:,} total functions")
    print(f"Found {len(gscr_functions)} functions in g_scr_main_mp.cpp")
    
    if matching_paths:
        print(f"\\nMatching file paths found:")
        for path in sorted(matching_paths):
            print(f"  {path}")
    
    if gscr_functions:
        # Write filtered functions to new CSV
        print(f"\\nWriting to {output_file}...")
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(gscr_functions)
        
        print(f"Successfully created {output_file}")
        
        # Sort by line number for easier reading
        try:
            gscr_functions.sort(key=lambda x: int(x.get('start_line', 0)))
        except:
            pass  # If sorting fails, continue with unsorted
        
        # Show function details
        print(f"\\nFunctions in g_scr_main_mp.cpp:")
        print("-" * 75)
        print(f"{'#':<3} {'Function Name':<45} {'Lines':<15} {'Length':<8}")
        print("-" * 75)
        
        for i, func in enumerate(gscr_functions):
            func_name = func.get('function_name', 'N/A')
            start_line = func.get('start_line', 'N/A')
            end_line = func.get('end_line', 'N/A')
            
            try:
                length = int(end_line) - int(start_line) + 1
            except:
                length = 'N/A'
            
            # Truncate long function names
            if len(func_name) > 43:
                func_name = func_name[:40] + "..."
            
            print(f"{i+1:<3} {func_name:<45} {start_line}-{end_line:<8} {length:<8}")
        
        # Summary stats
        if gscr_functions:
            lengths = []
            line_coverage = []
            
            for func in gscr_functions:
                try:
                    start = int(func.get('start_line', 0))
                    end = int(func.get('end_line', 0))
                    if end > start:
                        length = end - start + 1
                        lengths.append(length)
                        line_coverage.extend([start, end])
                except:
                    pass
            
            if lengths:
                print(f"\\nFunction Statistics:")
                print(f"  Total functions: {len(gscr_functions)}")
                print(f"  Average length: {sum(lengths)/len(lengths):.1f} lines")
                print(f"  Shortest function: {min(lengths)} lines")
                print(f"  Longest function: {max(lengths)} lines")
                
                if line_coverage:
                    print(f"  File line coverage: {min(line_coverage)}-{max(line_coverage)}")
    
    else:
        print("No functions found in g_scr_main_mp.cpp")
        print("\\nThis could mean:")
        print("  1. The file doesn't have any functions in the database")
        print("  2. The path format doesn't match")
        print("  3. The issues reference line numbers outside of function boundaries")
    
    return 0


if __name__ == "__main__":
    exit(extract_gscr_functions_correct())