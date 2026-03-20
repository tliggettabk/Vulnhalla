#!/usr/bin/env python3
"""
Add function start_line and end_line columns to matched_issues_with_cids.csv
"""

import csv
import os
import os.path


def add_function_boundaries():
    """Add start_line and end_line columns from FunctionTree.csv to matched issues."""
    
    # File paths
    function_tree_path = "C:/code/codeQL_CoD/codeql/FunctionTree.csv"
    matched_issues_path = "zCoD/matched_issues_with_cids.csv"
    output_path = "zCoD/matched_issues_with_cids_enhanced.csv"
    
    print("ADDING FUNCTION BOUNDARIES TO MATCHED ISSUES")
    print("=" * 50)
    
    # Step 1: Load function data from FunctionTree.csv
    print("Loading function data from FunctionTree.csv...")
    
    function_lookup = {}  # key: (function_name, file_path) -> (start_line, end_line)
    
    try:
        with open(function_tree_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                func_name = row['function_name'] 
                file_path = row['file']
                start_line = row['start_line']
                end_line = row['end_line']
                
                # Create lookup key using function name and file path  
                # Use normalized file path for matching
                normalized_file = file_path.replace('\\', '/').lower()
                if normalized_file.startswith('d:/mapped_drives/cod/trunk/'):
                    normalized_file = normalized_file.replace('d:/mapped_drives/cod/trunk/', '')
                
                lookup_key = (func_name, normalized_file)
                function_lookup[lookup_key] = (start_line, end_line)
                
        print(f"Loaded {len(function_lookup):,} functions from FunctionTree.csv")
    except Exception as e:
        print(f"Error reading FunctionTree.csv: {e}")
        return
        
    # Step 2: Process matched issues and add function boundaries
    print("\\nProcessing matched issues...")
    
    matched_count = 0
    unmatched_count = 0
    
    try:
        with open(matched_issues_path, 'r', encoding='utf-8') as infile, \
             open(output_path, 'w', newline='', encoding='utf-8') as outfile:
            
            reader = csv.DictReader(infile)
            
            # Add new columns to the fieldnames
            fieldnames = reader.fieldnames + ['function_start_line', 'function_end_line']
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for row in reader:
                func_name = row['matched_function']
                file_path = row['file']
                
                # Normalize file path for lookup
                normalized_file = file_path.replace('\\', '/').lower()
                if normalized_file.startswith('/code/'):
                    normalized_file = normalized_file.replace('/code/', '')
                
                lookup_key = (func_name, normalized_file)
                
                # Try multiple lookup strategies if direct match fails
                if lookup_key in function_lookup:
                    start_line, end_line = function_lookup[lookup_key]
                    row['function_start_line'] = start_line
                    row['function_end_line'] = end_line
                    matched_count += 1
                    
                    # Debug output for first few matches
                    if matched_count <= 3:
                        print(f"  ✓ Matched {func_name} in {normalized_file}: lines {start_line}-{end_line}")
                else:
                    # Try alternative lookup: check if any key contains this function name and ends with same filename
                    found_match = False
                    filename_only = os.path.basename(normalized_file)
                    
                    for (fn, fp), (start_line, end_line) in function_lookup.items():
                        if fn == func_name and fp.endswith(filename_only):
                            row['function_start_line'] = start_line
                            row['function_end_line'] = end_line
                            matched_count += 1
                            found_match = True
                            if matched_count <= 3:
                                print(f"  ✓ Alternative match {func_name} in {fp}: lines {start_line}-{end_line}")
                            break
                    
                    if not found_match:
                        row['function_start_line'] = ''  # Empty for unmatched
                        row['function_end_line'] = ''
                        unmatched_count += 1
                        
                        # Debug output for first few unmatched
                        if unmatched_count <= 3:
                            print(f"  ✗ No match for {func_name} in {normalized_file}")
                
                writer.writerow(row)
        
        print(f"\\nSuccessfully created enhanced file: {output_path}")
        
        # Try to replace original - if it fails, just leave both files
        try:
            os.replace(output_path, matched_issues_path)
            print(f"✓ Updated original file: {matched_issues_path}")
        except PermissionError:
            print(f"⚠ Could not replace original file (may be open in editor)")
            print(f"📁 Enhanced file saved as: {output_path}")
            print(f"💡 Close the CSV file in your editor and manually replace it")
        
        print(f"\\nProcessing complete!")
        print(f"✓ Functions matched with boundaries: {matched_count}")
        print(f"✗ Functions without boundaries: {unmatched_count}")
        print(f"📁 Updated file: {matched_issues_path}")
        
        # Show sample of the updated data
        print(f"\\nSample of updated data (first 3 rows):")
        with open(matched_issues_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for i, row in enumerate(reader):
                if i < 4:  # Header + 3 data rows
                    if i == 0:
                        print(f"Headers: {', '.join(row[-2:])}")  # Show last 2 columns (new ones)
                    else:
                        print(f"Row {i}: {row[0][:20]}... | start: {row[-2]} | end: {row[-1]}")
                        
    except Exception as e:
        print(f"Error processing files: {e}")
        return


if __name__ == "__main__":
    add_function_boundaries()