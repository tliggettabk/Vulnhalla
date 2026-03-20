#!/usr/bin/env python3
"""
Search for g_scr_main_mp functions with flexible path matching
"""

import csv
import os


def search_gscr_functions():
    """Search for functions from files containing g_scr_main_mp."""
    
    functions_file = "C:\\code\\codeQL_CoD\\codeql\\FunctionTree.csv"
    
    print("SEARCHING FOR G_SCR_MAIN_MP FUNCTIONS")
    print("=" * 40)
    
    if not os.path.exists(functions_file):
        print(f"ERROR: {functions_file} not found")
        return 1
    
    # Read all functions and search
    print(f"Searching functions in {functions_file}...")
    gscr_functions = []
    search_patterns = ["g_scr_main_mp", "GScr_MainMP", "gscr_main_mp"]
    
    with open(functions_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        
        for row in reader:
            file_path = row.get('file', '') or row.get('file_path', '')
            
            # Check if any search pattern is in the file path
            for pattern in search_patterns:
                if pattern in file_path:
                    gscr_functions.append(row)
                    break
    
    print(f"Found {len(gscr_functions)} functions matching g_scr_main_mp patterns")
    
    if gscr_functions:
        # Group by file path to see what files we found
        file_groups = {}
        for func in gscr_functions:
            file_path = func.get('file', '') or func.get('file_path', '')
            if file_path not in file_groups:
                file_groups[file_path] = []
            file_groups[file_path].append(func)
        
        print(f"\\nFound functions in {len(file_groups)} files:")
        for file_path, funcs in file_groups.items():
            print(f"  {file_path}: {len(funcs)} functions")
        
        # Create output file
        output_file = "zCoD/g_scr_main_mp_functions.csv"
        
        print(f"\\nWriting to {output_file}...")
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(gscr_functions)
        
        print(f"Successfully created {output_file}")
        
        # Show sample functions
        print(f"\\nFirst 15 functions:")
        print("-" * 60)
        
        for i, func in enumerate(gscr_functions[:15]):
            func_name = func.get('function_name', 'N/A')
            start_line = func.get('start_line', 'N/A')
            end_line = func.get('end_line', 'N/A')
            try:
                length = int(end_line) - int(start_line) + 1
            except:
                length = 'N/A'
            
            file_path = func.get('file', '') or func.get('file_path', '')
            filename = os.path.basename(file_path)
            
            print(f"  {i+1:2d}. {func_name}")
            print(f"      File: {filename}")
            print(f"      Lines: {start_line}-{end_line} ({length} lines)")
            print()
        
        if len(gscr_functions) > 15:
            print(f"  ... and {len(gscr_functions) - 15} more functions")
    
    else:
        print("No functions found matching g_scr_main_mp patterns")
        
        # Show some sample file paths for debugging
        print("\\nSample file paths from database:")
        with open(functions_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            sample_files = set()
            
            for i, row in enumerate(reader):
                if i >= 1000:  # Sample first 1000
                    break
                    
                file_path = row.get('file', '') or row.get('file_path', '')
                if file_path and 'game_mp' in file_path.lower():
                    sample_files.add(file_path)
            
            for file_path in sorted(sample_files)[:10]:
                print(f"  {file_path}")
    
    return 0


if __name__ == "__main__":
    exit(search_gscr_functions())