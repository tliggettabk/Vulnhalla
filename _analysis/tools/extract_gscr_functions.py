#!/usr/bin/env python3
"""
Extract g_scr_main_mp.cpp functions from FunctionTree.csv
"""

import csv
import os


def extract_gscr_functions():
    """Extract functions from g_scr_main_mp.cpp to a separate CSV."""
    
    functions_file = "C:\\code\\codeQL_CoD\\codeql\\FunctionTree.csv"
    output_file = "zCoD/g_scr_main_mp_functions.csv"
    
    print("EXTRACTING G_SCR_MAIN_MP.CPP FUNCTIONS")
    print("=" * 40)
    
    if not os.path.exists(functions_file):
        print(f"ERROR: {functions_file} not found")
        return 1
    
    # Read all functions
    print(f"Reading functions from {functions_file}...")
    all_functions = []
    
    with open(functions_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        
        for row in reader:
            all_functions.append(row)
    
    print(f"Loaded {len(all_functions):,} total functions")
    
    # Filter for g_scr_main_mp.cpp functions
    target_file = "g_scr_main_mp.cpp"
    gscr_functions = []
    
    for func in all_functions:
        file_path = func.get('file', '') or func.get('file_path', '')
        if target_file in file_path:
            gscr_functions.append(func)
    
    print(f"Found {len(gscr_functions)} functions in {target_file}")
    
    if gscr_functions:
        # Write filtered functions to new CSV
        print(f"Writing to {output_file}...")
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(gscr_functions)
        
        print(f"Successfully created {output_file}")
        
        # Show some sample functions
        print(f"\\nSample functions from {target_file}:")
        print("-" * 50)
        
        for i, func in enumerate(gscr_functions[:10]):  # Show first 10
            func_name = func.get('function_name', 'N/A')
            start_line = func.get('start_line', 'N/A')
            end_line = func.get('end_line', 'N/A')
            length = int(func.get('end_line', 0)) - int(func.get('start_line', 0)) + 1 if func.get('start_line') and func.get('end_line') else 'N/A'
            
            print(f"  {i+1:2d}. {func_name} (lines {start_line}-{end_line}, {length} lines)")
        
        if len(gscr_functions) > 10:
            print(f"  ... and {len(gscr_functions) - 10} more functions")
    
    else:
        print(f"No functions found in {target_file}")
        print("Available files (sample):")
        
        # Show some available file paths for reference
        file_paths = set()
        for func in all_functions[:100]:  # Sample first 100
            file_path = func.get('file', '') or func.get('file_path', '')
            if file_path:
                file_paths.add(os.path.basename(file_path))
        
        for i, filename in enumerate(sorted(file_paths)[:20]):
            print(f"  {filename}")
        
        if len(file_paths) > 20:
            print(f"  ... and {len(file_paths) - 20} more files")
    
    return 0


if __name__ == "__main__":
    exit(extract_gscr_functions())