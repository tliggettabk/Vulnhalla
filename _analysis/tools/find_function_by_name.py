#!/usr/bin/env python3
"""
Find a specific function by name in the same file
"""

import csv
import zipfile
import os


def find_function_by_name(function_name, target_file_path):
    """Find a specific function by name in the given file."""
    
    src_zip_path = "C:/code/codeQL_CoD/codeql/src.zip"
    function_tree_path = "C:/code/codeQL_CoD/codeql/FunctionTree.csv"
    
    print(f"SEARCHING FOR FUNCTION: {function_name}")
    print("=" * 50)
    
    # Step 1: Search FunctionTree.csv for the function
    print("Searching function database...")
    
    found_function = None
    
    try:
        with open(function_tree_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['function_name'] == function_name:
                    # Check if it's in the target file
                    file_path = row['file'].lower()
                    if 'db_binarypatch_load.cpp' in file_path:
                        found_function = row
                        print(f"✓ Found {function_name} in {row['file']}")
                        break
        
        if not found_function:
            print(f"✗ Function '{function_name}' not found in db_binarypatch_load.cpp")
            print("Searching for any occurrence of this function name...")
            
            # Try broader search
            with open(function_tree_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                matches = []
                for row in reader:
                    if function_name.lower() in row['function_name'].lower():
                        matches.append(row)
                
                if matches:
                    print(f"Found {len(matches)} similar function names:")
                    for i, match in enumerate(matches[:10]):  # Show first 10
                        print(f"  {i+1}. {match['function_name']} in {os.path.basename(match['file'])}")
                else:
                    print(f"No functions found matching '{function_name}'")
            return
            
    except Exception as e:
        print(f"Error reading function tree: {e}")
        return
        
    # Step 2: Extract the source code
    start_line = int(found_function['start_line'])
    end_line = int(found_function['end_line'])
    
    print(f"\nFunction details:")
    print(f"  Name: {found_function['function_name']}")
    print(f"  File: {found_function['file']}")
    print(f"  Lines: {start_line}-{end_line}")
    print(f"  Length: {end_line - start_line + 1} lines")
    
    # Step 3: Extract source from zip
    try:
        # Try different possible paths in the zip
        possible_zip_paths = [
            "D_/mapped_drives/cod/trunk/code/src/database/db_binarypatch_load.cpp",
            "code/src/database/db_binarypatch_load.cpp",
            "src/database/db_binarypatch_load.cpp"
        ]
        
        zip_path = None
        with zipfile.ZipFile(src_zip_path, 'r') as zip_file:
            all_files = zip_file.namelist()
            for possible_path in possible_zip_paths:
                if possible_path in all_files:
                    zip_path = possible_path
                    break
            
            if not zip_path:
                # Try partial matching
                matching_files = [f for f in all_files if 'db_binarypatch_load.cpp' in f]
                if matching_files:
                    zip_path = matching_files[0]
                    print(f"Found by filename match: {zip_path}")
                else:
                    print("File not found in zip archive")
                    return
            
            with zip_file.open(zip_path) as source_file:
                content = source_file.read().decode('utf-8', errors='replace')
                
        lines = content.split('\n')
        function_lines = lines[start_line-1:end_line]
        
        print(f"\nSOURCE CODE for {function_name} (lines {start_line}-{end_line}):")
        print("=" * 80)
        
        for i, line in enumerate(function_lines, start=start_line):
            print(f"    {i:4d}: {line}")
            
        print("=" * 80)
        
    except Exception as e:
        print(f"Error extracting source: {e}")


if __name__ == "__main__":
    find_function_by_name("DB_BinaryPatch_BeginManifestLoad", 
                         "/code/src/database/db_binarypatch_load.cpp")