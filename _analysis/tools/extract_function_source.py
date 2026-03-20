#!/usr/bin/env python3
"""
Extract function source code from src.zip using boundary information
"""

import csv
import zipfile
import os


def extract_function_source(issue_index=0):
    """Extract source code for a specific function from the matched issues."""
    
    # File paths
    matched_issues_path = "zCoD/matched_issues_with_cids.csv"
    src_zip_path = "C:/code/codeQL_CoD/codeql/src.zip"
    
    print("EXTRACTING FUNCTION SOURCE CODE")
    print("=" * 40)
    
    # Step 1: Read the specified issue
    try:
        with open(matched_issues_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            issues = list(reader)
            
        if issue_index >= len(issues):
            print(f"Error: Issue index {issue_index} out of range (0-{len(issues)-1})")
            return
            
        issue = issues[issue_index]
        
        print(f"Issue: {issue['name']}")
        print(f"Function: {issue['matched_function']}")
        print(f"File: {issue['file']}")
        print(f"Line range: {issue['function_start_line']}-{issue['function_end_line']}")
        print()
        
    except Exception as e:
        print(f"Error reading matched issues: {e}")
        return
        
    # Step 2: Extract source from zip file
    try:
        # Normalize the file path for zip lookup
        file_path = issue['file']
        if file_path.startswith('/code/'):
            file_path = file_path[6:]  # Remove '/code/' prefix
        
        # Try different path variations
        possible_paths = [
            file_path,
            file_path.lstrip('/'),  # Remove leading slash
            'code/' + file_path.lstrip('/'),  # Add code/ prefix
        ]
        
        print(f"Looking for file in src.zip...")
        
        with zipfile.ZipFile(src_zip_path, 'r') as zip_file:
            # List some files to understand structure
            all_files = zip_file.namelist()
            print(f"Zip contains {len(all_files):,} files")
            
            # Find the target file
            target_file = None
            for possible_path in possible_paths:
                if possible_path in all_files:
                    target_file = possible_path
                    break
                    
            if not target_file:
                # Try partial matching with filename
                filename = os.path.basename(file_path)
                matching_files = [f for f in all_files if f.endswith(filename)]
                
                if matching_files:
                    target_file = matching_files[0]
                    print(f"Found by filename match: {target_file}")
                else:
                    print(f"File not found in zip. Tried paths:")
                    for path in possible_paths:
                        print(f"  - {path}")
                    print(f"\nSample files in zip:")
                    for f in all_files[:10]:
                        print(f"  - {f}")
                    return
            else:
                print(f"Found file: {target_file}")
            
            # Read the file content
            with zip_file.open(target_file) as source_file:
                content = source_file.read().decode('utf-8', errors='replace')
                
        # Step 3: Extract the specific function lines
        lines = content.split('\n')
        start_line = int(issue['function_start_line'])
        end_line = int(issue['function_end_line'])
        
        print(f"File has {len(lines):,} lines total")
        print(f"Extracting lines {start_line} to {end_line}")
        
        # Adjust for 0-based indexing
        function_lines = lines[start_line-1:end_line]
        
        print(f"\nSOURCE CODE for {issue['matched_function']} (lines {start_line}-{end_line}):")
        print("=" * 80)
        
        if not function_lines:
            print("No lines found - checking line range...")
            # Show some context around the expected lines
            context_start = max(0, start_line - 5)
            context_end = min(len(lines), end_line + 5)
            print(f"Context lines {context_start+1}-{context_end}:")
            for i in range(context_start, context_end):
                marker = " >>> " if context_start <= i < end_line else "     "
                print(f"{marker}{i+1:4d}: {lines[i][:100]}")
        else:
            # Add vulnerability line highlighting
            vuln_line = int(issue['start_line']) if 'start_line' in issue else start_line
            
            for i, line in enumerate(function_lines, start=start_line):
                if i == vuln_line:
                    print(f">>> {i:4d}: {line}  <<<< VULNERABILITY FLAGGED HERE")
                else:
                    print(f"    {i:4d}: {line}")
            
        print("=" * 80)
        print(f"\nFunction details:")
        print(f"  Name: {issue['matched_function']}")
        print(f"  Length: {issue['function_length']} lines")
        print(f"  Issue: {issue['message']}")
        print(f"  Type: {issue['type']}")
        
    except Exception as e:
        print(f"Error extracting source code: {e}")
        return


if __name__ == "__main__":
    # Extract the first function (index 0)
    extract_function_source(0)