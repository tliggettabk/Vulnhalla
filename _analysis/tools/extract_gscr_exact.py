#!/usr/bin/env python3
"""
Extract functions from /code/src/game_iw9/game_mp/g_scr_main_mp.cpp
"""

import csv
import os


def extract_gscr_functions_exact():
    """Extract functions from the exact g_scr_main_mp.cpp path."""
    
    functions_file = "C:\\code\\codeQL_CoD\\codeql\\FunctionTree.csv"
    output_file = "zCoD/g_scr_main_mp_functions.csv"
    
    print("EXTRACTING G_SCR_MAIN_MP.CPP FUNCTIONS")
    print("=" * 40)
    
    if not os.path.exists(functions_file):
        print(f"ERROR: {functions_file} not found")
        return 1
    
    # The exact file path from the issues
    target_file_path = "/code/src/game_iw9/game_mp/g_scr_main_mp.cpp"
    
    # Read all functions and filter
    print(f"Searching for functions in: {target_file_path}")
    gscr_functions = []
    
    with open(functions_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        
        total_count = 0
        for row in reader:
            total_count += 1
            file_path = row.get('file', '') or row.get('file_path', '')
            
            # Exact match or contains the path
            if target_file_path in file_path or file_path.endswith("game_mp/g_scr_main_mp.cpp"):
                gscr_functions.append(row)
    
    print(f"Searched {total_count:,} total functions")
    print(f"Found {len(gscr_functions)} functions in g_scr_main_mp.cpp")
    
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
        print("-" * 70)
        print(f"{'#':<3} {'Function Name':<40} {'Lines':<15} {'Length':<8}")
        print("-" * 70)
        
        for i, func in enumerate(gscr_functions):
            func_name = func.get('function_name', 'N/A')
            start_line = func.get('start_line', 'N/A')
            end_line = func.get('end_line', 'N/A')
            
            try:
                length = int(end_line) - int(start_line) + 1
            except:
                length = 'N/A'
            
            # Truncate long function names
            if len(func_name) > 38:
                func_name = func_name[:35] + "..."
            
            print(f"{i+1:<3} {func_name:<40} {start_line}-{end_line:<8} {length:<8}")
        
        # Summary stats
        if gscr_functions:
            lengths = []
            for func in gscr_functions:
                try:
                    start = int(func.get('start_line', 0))
                    end = int(func.get('end_line', 0))
                    if end > start:
                        lengths.append(end - start + 1)
                except:
                    pass
            
            if lengths:
                print(f"\\nFunction Statistics:")
                print(f"  Total functions: {len(gscr_functions)}")
                print(f"  Average length: {sum(lengths)/len(lengths):.1f} lines")
                print(f"  Shortest function: {min(lengths)} lines")
                print(f"  Longest function: {max(lengths)} lines")
    
    else:
        print("No functions found in g_scr_main_mp.cpp")
        
        # Debug: show some sample file paths
        print("\\nSample file paths found in database:")
        count = 0
        with open(functions_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                file_path = row.get('file', '') or row.get('file_path', '')
                if 'game_mp' in file_path.lower():
                    print(f"  {file_path}")
                    count += 1
                    if count >= 10:  # Show max 10 examples
                        break
        
        if count == 0:
            print("  No game_mp files found in first scan")
    
    return 0


if __name__ == "__main__":
    exit(extract_gscr_functions_exact())