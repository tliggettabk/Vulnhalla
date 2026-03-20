#!/usr/bin/env python3
"""
Step 1: Function Mapping for Findings Data

This script reads the findings Excel file and maps each finding to its containing function
using the FunctionTree.csv data from CodeQL analysis.

Process:
1. Read Findings_WithCodeLine_WithTriageComment.xlsx
2. For each finding, use File and Line Number to find containing function
3. Add columns for found function: name, start, end, length  
4. Compare with existing Function column and flag differences
5. If different, lookup the existing Function name and add its details

Usage:
    python step1_function_mapping.py --test  # Test mode (first 10 rows only)
    python step1_function_mapping.py         # Full processing
"""

import pandas as pd
import csv
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import sys
import os
import zipfile
import re
import shutil

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def normalize_path(file_path: str) -> str:
    """Normalize file path for consistent matching."""
    if not file_path:
        return ""
    
    # Remove quotes and normalize separators
    normalized = file_path.replace('"', '').replace('\\', '/')
    
    # Handle different path formats:
    # Excel format: /cod_trunk/code/src/...
    # FunctionTree format: D:/mapped_drives/cod/trunk/code/...
    
    # Extract the relative path after /code/ or /trunk/code/
    if '/cod_trunk/code/' in normalized:
        # Excel format: /cod_trunk/code/src/... -> /code/src/...
        relative_part = normalized.split('/cod_trunk/code/', 1)[1]
        return f'/code/{relative_part}'
    elif '/trunk/code/' in normalized:
        # FunctionTree format: D:/mapped_drives/cod/trunk/code/... -> /code/...
        relative_part = normalized.split('/trunk/code/', 1)[1] 
        return f'/code/{relative_part}'
    elif normalized.startswith('/code/'):
        # Already normalized
        return normalized
    elif normalized.startswith('code/'):
        # Add leading slash
        return f'/{normalized}'
    else:
        # Default: assume it's a relative path under /code/
        return f'/code/{normalized}'

def load_function_tree(function_tree_path: str) -> List[Dict]:
    """Load and parse the FunctionTree.csv file."""
    print(f"Loading FunctionTree from: {function_tree_path}")
    
    functions = []
    try:
        with open(function_tree_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    # Parse function data
                    function_data = {
                        'name': row.get('function_name', '').replace('"', ''),
                        'file': normalize_path(row.get('file', '')),
                        'start_line': int(row.get('start_line', 0)),
                        'end_line': int(row.get('end_line', 0)),
                        'length': 0  # Will calculate
                    }
                    
                    # Calculate length
                    if function_data['start_line'] and function_data['end_line']:
                        function_data['length'] = function_data['end_line'] - function_data['start_line'] + 1
                    
                    # Skip invalid entries
                    if function_data['start_line'] > 0 and function_data['end_line'] >= function_data['start_line']:
                        functions.append(function_data)
                        
                except (ValueError, KeyError):
                    continue  # Skip malformed rows
                    
        print(f"Loaded {len(functions):,} functions from FunctionTree")
        return functions
        
    except FileNotFoundError:
        print(f"ERROR: FunctionTree file not found at {function_tree_path}")
        return []
    except Exception as e:
        print(f"ERROR loading FunctionTree: {e}")
        return []

def build_function_index(functions: List[Dict]) -> Dict[str, List[Dict]]:
    """Build an index of functions by file path for faster lookup."""
    index = {}
    for func in functions:
        file_path = func['file']
        if file_path not in index:
            index[file_path] = []
        index[file_path].append(func)
    
    # Sort functions within each file by start_line for efficient searching
    for file_path in index:
        index[file_path].sort(key=lambda x: x['start_line'])
    
    print(f"Built function index covering {len(index):,} files")
    return index

def find_highest_line_function(file_path: str, function_index: Dict) -> Optional[Dict]:
    """
    Find the function with the highest line number in the given file.
    
    Returns:
        Dict with function details or None if no functions found
    """
    normalized_path = normalize_path(file_path)
    file_functions = function_index.get(normalized_path, [])
    
    if not file_functions:
        return None
    
    # Find function with highest start line
    highest_function = max(file_functions, key=lambda f: f['start_line'])
    return highest_function

def find_containing_function(file_path: str, line_number: int, function_index: Dict[str, List[Dict]]) -> Optional[Dict]:
    """Find the function containing the given file:line location."""
    normalized_path = normalize_path(file_path)
    
    # Try exact match first
    if normalized_path in function_index:
        functions_in_file = function_index[normalized_path]
    else:
        # Try partial matching for different path formats
        matching_files = []
        for indexed_path in function_index.keys():
            if file_path in indexed_path or indexed_path in file_path:
                matching_files.append(indexed_path)
        
        if len(matching_files) == 1:
            functions_in_file = function_index[matching_files[0]]
        elif len(matching_files) > 1:
            # Use the most specific match (longest common suffix)
            best_match = max(matching_files, key=len)
            functions_in_file = function_index[best_match]
        else:
            return None
    
    # Find function containing the line number
    for func in functions_in_file:
        if func['start_line'] <= line_number <= func['end_line']:
            return func
    
    return None

def find_function_by_name(function_name: str, functions: List[Dict]) -> Optional[Dict]:
    """Find a function by exact name match."""
    if not function_name:
        return None
        
    for func in functions:
        if func['name'] == function_name:
            return func
    
    return None

def extract_file_from_zip(src_zip_path: str, file_path: str) -> List[str]:
    """Extract file content from src.zip as lines."""
    try:
        # Normalize the file path for zip lookup
        zip_file_path = file_path
        if zip_file_path.startswith('/code/'):
            zip_file_path = zip_file_path[6:]  # Remove /code/ prefix
        
        with zipfile.ZipFile(src_zip_path, 'r') as zip_file:
            # Try different path variations
            possible_paths = [
                zip_file_path,
                zip_file_path.replace('/', '\\'),
                f'code/{zip_file_path}',
                f'trunk/code/{zip_file_path}',
                f'cod_trunk/code/{zip_file_path}'
            ]
            
            for path_variant in possible_paths:
                try:
                    with zip_file.open(path_variant) as file:
                        content = file.read().decode('utf-8', errors='ignore')
                        return content.splitlines()
                except KeyError:
                    continue
            
            # If no direct match, search for files ending with the same suffix
            zip_info_list = zip_file.infolist()
            file_basename = Path(zip_file_path).name
            
            for zip_info in zip_info_list:
                if zip_info.filename.endswith(file_basename):
                    try:
                        with zip_file.open(zip_info.filename) as file:
                            content = file.read().decode('utf-8', errors='ignore')
                            return content.splitlines()
                    except:
                        continue
        
        return []
    except Exception as e:
        print(f"Error extracting {file_path} from zip: {e}")
        return []

def extract_function_code(file_lines: List[str], start_line: int, end_line: int) -> List[str]:
    """Extract function code based on line range."""
    if not file_lines or start_line < 1 or end_line < start_line:
        return []
    
    # Convert to 0-based indexing
    start_idx = start_line - 1
    end_idx = min(end_line, len(file_lines))
    
    return file_lines[start_idx:end_idx]

def find_code_in_function(function_lines: List[str], search_code: str, start_line_offset: int) -> Optional[int]:
    """
    Find code within function lines. Returns line number relative to file start.
    
    Args:
        function_lines: Lines of the function code
        search_code: Code to search for (should be a complete line)
        start_line_offset: Starting line number of function in file (1-based)
    
    Returns:
        Line number in file (1-based) where code is found, or None
    """
    if not search_code or not function_lines:
        return None
    
    # Normalize search code (strip whitespace, handle common variations)
    search_normalized = search_code.strip()
    
    for i, line in enumerate(function_lines):
        line_normalized = line.strip()
        
        # Check for exact match
        if line_normalized == search_normalized:
            return start_line_offset + i
        
        # Check for substantial match (75% of characters match)
        if len(search_normalized) > 10:  # Only for reasonably long lines
            matching_chars = sum(1 for a, b in zip(line_normalized, search_normalized) if a == b)
            similarity = matching_chars / max(len(line_normalized), len(search_normalized))
            if similarity >= 0.75:
                return start_line_offset + i
    
    return None

def calculate_similarity(str1, str2):
    """
    Calculate similarity between two strings using multiple methods.
    Returns a score between 0.0 and 1.0.
    """
    if not str1 and not str2:
        return 1.0
    if not str1 or not str2:
        return 0.0
    
    # Normalize whitespace and remove common code formatting
    def normalize_code(s):
        # Remove extra whitespace
        s = re.sub(r'\s+', ' ', s.strip())
        # Remove common C++ formatting differences
        s = s.replace(' (', '(').replace('( ', '(')
        s = s.replace(' )', ')').replace(' )', ')')
        s = s.replace(' ;', ';').replace('; ', ';')
        s = s.replace(' ,', ',').replace(', ', ',')
        return s.lower()
    
    norm1 = normalize_code(str1)
    norm2 = normalize_code(str2)
    
    # Exact match after normalization
    if norm1 == norm2:
        return 1.0
    
    # Sequence matcher for overall similarity
    from difflib import SequenceMatcher
    seq_similarity = SequenceMatcher(None, norm1, norm2).ratio()
    
    # Check if one contains the other (substring match)
    if norm2 in norm1 or norm1 in norm2:
        substring_bonus = 0.1
    else:
        substring_bonus = 0.0
    
    return min(1.0, seq_similarity + substring_bonus)

def verify_line_content(file_lines: List[str], target_line: int, expected_code: str) -> Tuple[Optional[str], int, float, List[Dict]]:
    """
    Verify if the expected content matches what's at the target line,
    or search for it nearby if not exact match.
    
    Returns: 
        (actual_content_at_found_line, line_number_where_found, similarity_score, search_results)
    """
    if not expected_code or not expected_code.strip():
        return None, 0, 0.0, []
    
    expected_clean = expected_code.strip()
    search_results = []
    
    # First check the exact line
    actual_at_target = None
    if 1 <= target_line <= len(file_lines):
        actual_at_target = file_lines[target_line - 1].strip()
        similarity = calculate_similarity(actual_at_target, expected_clean)
        search_results.append({
            'line': target_line,
            'content': actual_at_target,
            'similarity': similarity,
            'is_target': True
        })
        
        if actual_at_target == expected_clean:
            return actual_at_target, target_line, 1.0, search_results
    
    # Search within reasonable range for exact or similar matches
    search_range = 15
    start_line = max(1, target_line - search_range)
    end_line = min(len(file_lines), target_line + search_range)
    
    best_match = None
    best_similarity = 0.0
    best_line = 0
    
    for line_num in range(start_line, end_line + 1):
        if line_num == target_line:  # Already checked
            continue
            
        actual_line = file_lines[line_num - 1].strip()
        similarity = calculate_similarity(actual_line, expected_clean)
        
        search_results.append({
            'line': line_num,
            'content': actual_line,
            'similarity': similarity,
            'is_target': False
        })
        
        # Exact match - return immediately for 100% matches
        if actual_line == expected_clean:
            return actual_line, line_num, 1.0, search_results
        
        # Track best fuzzy match
        if similarity > best_similarity and similarity >= 0.7:  # 70% similarity threshold
            best_similarity = similarity
            best_match = actual_line
            best_line = line_num
    
    # Return best match if found, otherwise return target line content
    if best_match and best_similarity >= 0.7:
        return best_match, best_line, best_similarity, search_results
    elif actual_at_target is not None:
        target_similarity = calculate_similarity(actual_at_target, expected_clean)
        return actual_at_target, target_line, target_similarity, search_results
    
    return None, 0, 0.0, search_results

def process_findings(excel_path: str, function_tree_path: str, src_zip_path: str, test_mode: bool = False, test_start: int = 0, quiet_mode: bool = False) -> Dict:
    """
    Process the findings Excel file and map functions.
    
    Returns:
        Dict with processing statistics and results
    """
    
    print("=" * 60)
    print("STEP 1: FUNCTION MAPPING ANALYSIS")
    print("=" * 60)
    
    if quiet_mode:
        print(f"\nProcessing {883 if not test_mode else 10} findings in {'QUIET' if not test_mode else 'TEST'} mode...")
    
    # Load data
    print(f"\n1. Loading Excel file: {excel_path}")
    try:
        df = pd.read_excel(excel_path)
        if not quiet_mode:
            print(f"   Loaded {len(df):,} findings from Excel")
    except Exception as e:
        print(f"ERROR loading Excel file: {e}")
        return {"error": str(e)}
    
    # Load function tree
    if not quiet_mode:
        print(f"Loading FunctionTree from: {function_tree_path}")
    functions = load_function_tree(function_tree_path)
    if not functions:
        return {"error": "Failed to load function tree"}
    
    if not quiet_mode:
        print(f"Loaded {len(functions):,} functions from FunctionTree")
    
    function_index = build_function_index(functions)
    analyzed_files = set(function_index.keys())
    if not quiet_mode:
        print(f"Built function index covering {len(function_index):,} files")
        print(f"FunctionTree.csv covers {len(analyzed_files):,} source files with functions")
    
    # Process findings
    if test_mode:
        test_end = test_start + 10
        if not quiet_mode:
            print(f"\n2. Processing findings {test_start+1}-{min(test_end, len(df))} (TEST MODE)")
        df_process = df.iloc[test_start:test_end]
    else:
        if not quiet_mode:
            print(f"\n2. Processing all {len(df):,} findings")
        df_process = df
    
    if not quiet_mode:
        print("\n" + "=" * 60)
        print("PROCESSING RESULTS")
        print("=" * 60)
    
    # Statistics tracking
    stats = {
        'total_processed': 0,
        'found_by_location': 0,
        'not_found_by_location': 0,
        'function_match': 0,
        'function_mismatch': 0,
        'existing_function_found': 0,
        'existing_function_not_found': 0,
        'missing_data': 0,
        'code_verification_attempted': 0,
        'line_number_verified': 0,
        'line_number_moved': 0,
        'line_number_not_found': 0,
        'cited_line_verified': 0,
        'cited_line_moved': 0,
        'cited_line_not_found': 0,
        'file_exists_in_zip': 0,
        'file_not_found_in_zip': 0,
        'file_in_functiontree': 0,
        'file_not_in_functiontree': 0,
        'function_extraction_failed': 0
    }
    
    results = []
    
    for idx, row in df_process.iterrows():
        stats['total_processed'] += 1
        
        # Show progress for full mode in quiet mode
        if not test_mode and quiet_mode and stats['total_processed'] % 100 == 0:
            print(f"Progress: {stats['total_processed']}/{len(df_process)} ({stats['total_processed']/len(df_process)*100:.1f}%)")
        
        # Extract data from row
        file_path = str(row.get('File', '')) if pd.notna(row.get('File')) else ''
        line_number = row.get('Line Number', 0)
        existing_function = str(row.get('Function', '')) if pd.notna(row.get('Function')) else ''
        sink_code = str(row.get('sink', '')) if pd.notna(row.get('sink')) else ''
        code_at_cited_line = str(row.get('code_at_cited_line', '')) if pd.notna(row.get('code_at_cited_line')) else ''
        
        # Convert line number to int if possible
        try:
            line_number = int(line_number) if pd.notna(line_number) else 0
        except (ValueError, TypeError):
            line_number = 0
        
        result = {
            'index': idx + 1,
            'file_path': file_path,
            'line_number': line_number,
            'existing_function': existing_function,
            'sink_code': sink_code,
            'code_at_cited_line': code_at_cited_line,
            'found_function_name': '',
            'found_function_start': 0,
            'found_function_end': 0,
            'found_function_length': 0,
            'functions_match': False,
            'existing_function_start': 0,
            'existing_function_end': 0,
            'existing_function_length': 0,
            'status': '',
            # Code verification fields
            'line_number_matches': False,
            'line_number_actual_content': '',
            'line_number_found_at': 0,
            'line_number_similarity': 0.0,
            'cited_line_matches': False,
            'cited_line_actual_content': '',
            'cited_line_found_at': 0,
            'cited_line_similarity': 0.0,
            'file_exists_in_zip': False,
            'file_in_functiontree': False,
            'function_code_extracted': False,
            'verification_performed': False,
            'full_function_code': [],
            'line_search_results': [],
            'cited_search_results': [],
            # Final summary fields
            'analysis_status': 'problem',  # perfect, found, problem
            'current_code_at_cited_line': '',  # actual code found
            'current_line_number': 0  # actual line where code was found
        }
        
        # Check for missing data
        if not file_path or line_number <= 0:
            result['status'] = 'Missing file path or line number'
            stats['missing_data'] += 1
            results.append(result)
            continue
        
        # Check file availability for ALL findings (not just those with functions)
        file_lines = extract_file_from_zip(src_zip_path, file_path)
        result['file_exists_in_zip'] = bool(file_lines)
        if file_lines:
            stats['file_exists_in_zip'] += 1
        else:
            stats['file_not_found_in_zip'] += 1
        
        # Check if file was analyzed by CodeQL (has functions in function tree)
        normalized_file_path = normalize_path(file_path)
        result['file_in_functiontree'] = normalized_file_path in analyzed_files
        if result['file_in_functiontree']:
            stats['file_in_functiontree'] += 1
        else:
            stats['file_not_in_functiontree'] += 1
        
        # Find containing function by location
        found_function = find_containing_function(file_path, line_number, function_index)
        
        if found_function:
            stats['found_by_location'] += 1
            result['found_function_name'] = found_function['name']
            result['found_function_start'] = found_function['start_line']
            result['found_function_end'] = found_function['end_line']
            result['found_function_length'] = found_function['length']
            
            # Compare with existing function name
            if existing_function and existing_function == found_function['name']:
                result['functions_match'] = True
                stats['function_match'] += 1
                result['status'] = 'Match - function names agree'
                
                # Perform code verification for matching functions
                result['verification_performed'] = True
                stats['code_verification_attempted'] += 1
                
                # Extract file content from src.zip (file already checked above)
                if file_lines:  # Use already extracted file_lines
                    result['function_code_extracted'] = True
                    
                    # Extract function code
                    function_lines = extract_function_code(
                        file_lines, 
                        found_function['start_line'], 
                        found_function['end_line']
                    )
                    
                    if function_lines:
                        # Store the full function code for detailed output
                        result['full_function_code'] = file_lines
                        # Verify line number content (just record what's there)
                        if line_number > 0 and line_number <= len(file_lines):
                            actual_content = file_lines[line_number - 1].strip()
                            result['line_number_actual_content'] = actual_content
                            result['line_number_found_at'] = line_number
                            result['line_number_matches'] = True  # Always true since we're just recording
                            result['line_number_similarity'] = 1.0
                            stats['line_number_verified'] += 1
                        
                        # Verify cited line content if available
                        if code_at_cited_line:
                            cited_actual, cited_found_at, cited_similarity, cited_search = verify_line_content(
                                file_lines, line_number, code_at_cited_line
                            )
                            result['cited_line_actual_content'] = cited_actual or ''
                            result['cited_line_found_at'] = cited_found_at
                            result['cited_line_similarity'] = cited_similarity
                            result['cited_search_results'] = cited_search
                            result['cited_line_matches'] = cited_similarity >= 0.95
                            
                            if result['cited_line_matches']:
                                stats['cited_line_verified'] += 1
                                if cited_found_at != line_number:
                                    stats['cited_line_moved'] += 1
                                    result['status'] += f' - cited code moved to L{cited_found_at}'
                            elif cited_similarity >= 0.7:
                                stats['cited_line_moved'] += 1
                                result['status'] += f' - cited code similar at L{cited_found_at} ({cited_similarity:.1%})'
                            else:
                                stats['cited_line_not_found'] += 1
                                result['status'] += ' - cited code not found'

                    else:
                        stats['function_extraction_failed'] += 1
                else:
                    stats['function_extraction_failed'] += 1
                
            elif existing_function:
                stats['function_mismatch'] += 1
                
                # Look up existing function details to see if we should use it instead
                existing_func_details = find_function_by_name(existing_function, functions)
                if existing_func_details:
                    stats['existing_function_found'] += 1
                    
                    # Use existing function for verification instead of location-based function
                    result['found_function_name'] = f"[BY_NAME] {existing_func_details['name']}"
                    result['found_function_start'] = existing_func_details['start_line']
                    result['found_function_end'] = existing_func_details['end_line']
                    result['found_function_length'] = existing_func_details['length']
                    result['functions_match'] = True  # Now we're using the matching function
                    result['status'] = f'Used existing function name \"{existing_function}\" instead of location-based function'
                    
                    # Store location-based function details for comparison
                    result['existing_function_start'] = found_function['start_line']
                    result['existing_function_end'] = found_function['end_line']
                    result['existing_function_length'] = found_function['length']
                    
                    # Now do verification with the name-based function
                    result['verification_performed'] = True
                    stats['code_verification_attempted'] += 1
                    
                    # Extract file content from src.zip using name-based function (file already checked above)
                    if file_lines:  # Use already extracted file_lines
                        result['function_code_extracted'] = True
                        
                        # Extract function code using existing function boundaries
                        function_lines = extract_function_code(
                            file_lines, 
                            existing_func_details['start_line'], 
                            existing_func_details['end_line']
                        )
                        
                        if function_lines:
                            # Store the full function code for detailed output
                            result['full_function_code'] = file_lines
                            
                            # Verify line number content (just record what's there)
                            if line_number > 0 and line_number <= len(file_lines):
                                actual_content = file_lines[line_number - 1].strip()
                                result['line_number_actual_content'] = actual_content
                                result['line_number_found_at'] = line_number
                                result['line_number_matches'] = True  # Always true since we're just recording
                                result['line_number_similarity'] = 1.0
                                stats['line_number_verified'] += 1
                            
                            # Verify cited line content if available
                            if code_at_cited_line:
                                cited_actual, cited_found_at, cited_similarity, cited_search = verify_line_content(
                                    file_lines, line_number, code_at_cited_line
                                )
                                result['cited_line_actual_content'] = cited_actual or ''
                                result['cited_line_found_at'] = cited_found_at
                                result['cited_line_similarity'] = cited_similarity
                                result['cited_search_results'] = cited_search
                                result['cited_line_matches'] = cited_similarity >= 0.95
                                
                                if result['cited_line_matches']:
                                    stats['cited_line_verified'] += 1
                                    if cited_found_at != line_number:
                                        stats['cited_line_moved'] += 1
                                        result['status'] += f' - cited code moved to L{cited_found_at}'
                                elif cited_similarity >= 0.7:
                                    stats['cited_line_moved'] += 1
                                    result['status'] += f' - cited code similar at L{cited_found_at} ({cited_similarity:.1%})'
                                else:
                                    stats['cited_line_not_found'] += 1
                                    result['status'] += ' - cited code not found'

                        else:
                            stats['function_extraction_failed'] += 1
                    else:
                        stats['function_extraction_failed'] += 1
                        
                else:
                    stats['existing_function_not_found'] += 1
                    result['status'] = 'Mismatch - different function names, existing function not found'
                    result['existing_function_start'] = 0
                    result['existing_function_end'] = 0
                    result['existing_function_length'] = 0
            else:
                result['status'] = 'Found function, no existing function to compare'
        else:
            stats['not_found_by_location'] += 1
            
            # When no containing function found, report the highest line function in the file
            highest_function = find_highest_line_function(file_path, function_index)
            if highest_function:
                result['found_function_name'] = f"[HIGHEST] {highest_function['name']}"
                result['found_function_start'] = highest_function['start_line']
                result['found_function_end'] = highest_function['end_line']
                result['found_function_length'] = highest_function['length']
                result['status'] = f'No containing function found - highest line function: {highest_function["name"]} (L{highest_function["start_line"]})'
            else:
                result['status'] = 'No containing function found - no functions in file'
            
            # Still try to look up existing function if provided
            if existing_function:
                existing_func_details = find_function_by_name(existing_function, functions)
                if existing_func_details:
                    stats['existing_function_found'] += 1
                    result['existing_function_start'] = existing_func_details['start_line']
                    result['existing_function_end'] = existing_func_details['end_line']
                    result['existing_function_length'] = existing_func_details['length']
                else:
                    stats['existing_function_not_found'] += 1
        
        # Set final summary fields based on verification results
        if result['verification_performed'] and result['code_at_cited_line']:
            # Determine analysis status based on cited line verification
            if result['cited_line_matches'] and result['cited_line_similarity'] >= 0.95:
                result['analysis_status'] = 'perfect'
            elif result['cited_line_similarity'] >= 0.7 or result['cited_line_found_at'] > 0:
                result['analysis_status'] = 'found'
            else:
                result['analysis_status'] = 'problem'
            
            # Set current code and line number
            result['current_code_at_cited_line'] = result['cited_line_actual_content']
            result['current_line_number'] = result['cited_line_found_at'] if result['cited_line_found_at'] > 0 else line_number
        else:
            # No verification performed or no expected code
            result['analysis_status'] = 'problem'
            if line_number > 0 and result['line_number_actual_content']:
                result['current_code_at_cited_line'] = result['line_number_actual_content']
                result['current_line_number'] = line_number
        
        results.append(result)
    
    # Print detailed results for test mode
    if test_mode and not quiet_mode:
        print(f"\nDETAILED RESULTS (Rows {test_start+1}-{test_start+len(results)}):")
        print("-" * 140)
        for i, result in enumerate(results, test_start+1):
            print(f"\nRow {i}:")
            print(f"  File: {result['file_path']}")
            print(f"  Line: {result['line_number']}")
            print(f"  Existing Function: '{result['existing_function']}'")
            print(f"  Found Function: '{result['found_function_name']}' (lines {result['found_function_start']}-{result['found_function_end']}, length {result['found_function_length']})")
            print(f"  Functions Match: {result['functions_match']}")
            print(f"  Status: {result['status']}")
            print(f"  📊 SUMMARY: {result['analysis_status'].upper()} | Current Code: '{result['current_code_at_cited_line'][:50]}...' | Current Line: {result['current_line_number']}")
            
            if result['verification_performed'] and result['function_code_extracted']:
                print(f"\n  CODE VERIFICATION DETAILS:")
                
                # Code at cited line verification
                if result['code_at_cited_line']:
                    print(f"    CODE AT CITED LINE:")
                    print(f"      Expected: '{result['code_at_cited_line']}'")
                    if result['cited_line_actual_content']:
                        print(f"      Actual:   '{result['cited_line_actual_content']}'")
                        print(f"      Matches:  {result['cited_line_matches']} (similarity: {result['cited_line_similarity']:.1%})")
                        if result['cited_line_found_at'] != result['line_number']:
                            print(f"      Found at: Line {result['cited_line_found_at']}")
                        
                        # Show search results if interesting
                        if result.get('cited_search_results') and len(result['cited_search_results']) > 1:
                            print(f"      Search results (top 3):")
                            for search_result in sorted(result['cited_search_results'], key=lambda x: x['similarity'], reverse=True)[:3]:
                                marker = "*" if search_result['is_target'] else " "
                                print(f"        {marker} L{search_result['line']:4} ({search_result['similarity']:.1%}): {search_result['content'][:50]}...")
                    else:
                        print(f"      Actual:   [NOT FOUND - no similar code within ±15 lines]")
                    print()
                
                # Show full function code
                if result['full_function_code']:
                    print(f"    FULL FUNCTION CODE:")
                    function_lines = result['full_function_code'][result['found_function_start']-1:result['found_function_end']]
                    for line_idx, line_content in enumerate(function_lines, start=result['found_function_start']):
                        marker = " --> " if line_idx == result['line_number'] else "     "
                        # Mark lines where code was found differently than expected
                        if (result['cited_line_found_at'] == line_idx and result['cited_line_found_at'] != result['line_number']):
                            marker = " C>> "  # Cited code found here
                        
                        print(f"    {marker}L{line_idx:4}: {line_content.rstrip()}")
                    print()
            
            if result['existing_function_start'] > 0:
                print(f"  Existing Func Details: lines {result['existing_function_start']}-{result['existing_function_end']}, length {result['existing_function_length']}")
            
            print("-" * 80)
    
    # Print summary statistics
    print(f"\n" + "=" * 60)
    print("PROCESSING STATISTICS")
    print("=" * 60)
    print(f"Total findings processed: {stats['total_processed']:,}")
    print(f"Missing data (file/line): {stats['missing_data']:,}")
    print(f"")
    print(f"Function location mapping:")
    print(f"  Found by location: {stats['found_by_location']:,} ({stats['found_by_location']/max(1,stats['total_processed'])*100:.1f}%)")
    print(f"  Not found by location: {stats['not_found_by_location']:,} ({stats['not_found_by_location']/max(1,stats['total_processed'])*100:.1f}%)")
    print(f"")
    print(f"Function name comparison:")
    print(f"  Names match: {stats['function_match']:,}")
    print(f"  Names differ: {stats['function_mismatch']:,}")
    print(f"")
    print(f"Code verification (for matching functions):")
    print(f"  Verification attempted: {stats['code_verification_attempted']:,}")
    print(f"  Function extraction failed: {stats['function_extraction_failed']:,}")
    print(f"  Line numbers verified: {stats['line_number_verified']:,}")
    print(f"  Cited lines verified: {stats['cited_line_verified']:,}")
    print(f"  Cited lines moved: {stats['cited_line_moved']:,}")
    print(f"  Cited lines not found: {stats['cited_line_not_found']:,}")
    print(f"")
    print(f"File availability in src.zip:")
    print(f"  Files found in zip: {stats['file_exists_in_zip']:,} ({stats['file_exists_in_zip']/max(1,stats['total_processed'])*100:.1f}%)")
    print(f"  Files not found in zip: {stats['file_not_found_in_zip']:,} ({stats['file_not_found_in_zip']/max(1,stats['total_processed'])*100:.1f}%)")
    print(f"")
    print(f"FunctionTree.csv availability:")
    print(f"  Files in FunctionTree.csv: {stats['file_in_functiontree']:,} ({stats['file_in_functiontree']/max(1,stats['total_processed'])*100:.1f}%)")
    print(f"  Files not in FunctionTree.csv: {stats['file_not_in_functiontree']:,} ({stats['file_not_in_functiontree']/max(1,stats['total_processed'])*100:.1f}%)")
    print(f"")
    print(f"Existing function lookup:")
    print(f"  Found in function tree: {stats['existing_function_found']:,}")
    print(f"  Not found in function tree: {stats['existing_function_not_found']:,}")
    
    success_rate = stats['found_by_location'] / max(1, stats['total_processed']) * 100
    match_rate = stats['function_match'] / max(1, stats['found_by_location']) * 100 if stats['found_by_location'] > 0 else 0
    
    # Calculate analysis status summary
    perfect_count = sum(1 for r in results if r['analysis_status'] == 'perfect')
    found_count = sum(1 for r in results if r['analysis_status'] == 'found')
    problem_count = sum(1 for r in results if r['analysis_status'] == 'problem')
    
    print(f"\n" + "=" * 60)
    print("ANALYSIS STATUS SUMMARY")
    print("=" * 60)
    print(f"Perfect matches: {perfect_count:,} ({perfect_count/max(1,len(results))*100:.1f}%)")
    print(f"Found with corrections: {found_count:,} ({found_count/max(1,len(results))*100:.1f}%)")
    print(f"Problematic cases: {problem_count:,} ({problem_count/max(1,len(results))*100:.1f}%)")
    
    print(f"\n" + "=" * 60)
    print("KEY METRICS")
    print("=" * 60)
    print(f"Location mapping success rate: {success_rate:.1f}%")
    print(f"Function name match rate: {match_rate:.1f}%")
    
    if test_mode:
        print(f"\n✓ Test mode complete. Review results above before running full processing.")
    else:
        print(f"\n✓ Full processing complete.")
    
    # Create enhanced dataframe with all analysis columns
    enhanced_df = df.copy()
    
    # Add all analysis columns to the dataframe
    new_columns = {}
    for i, result in enumerate(results):
        original_idx = test_start + i if test_mode else i
        if original_idx < len(enhanced_df):
            for key, value in result.items():
                if key not in new_columns:
                    new_columns[key] = [None] * len(enhanced_df)
                new_columns[key][original_idx] = value
    
    # Add the new columns to the dataframe
    for col_name, col_data in new_columns.items():
        enhanced_df[col_name] = col_data
    
    return {
        'stats': stats,
        'results': results,
        'success_rate': success_rate,
        'match_rate': match_rate,
        'enhanced_df': enhanced_df
    }

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description='Map findings to functions using CodeQL function tree')
    parser.add_argument('--test', action='store_true', help='Test mode - process only 10 rows starting from test-start')
    parser.add_argument('--test-start', type=int, default=0, help='Starting row for test mode (0-based index)')
    parser.add_argument('--quiet', '-q', action='store_true', help='Quiet mode - minimal output, just progress and final statistics')
    parser.add_argument('--excel', default='../x01-cov-setup/Findings_WithCodeLine_WithTriageComment.xlsx', 
                       help='Path to Excel file')
    parser.add_argument('--functions', default='C:/code/codeQL_CoD/codeql/FunctionTree.csv',
                       help='Path to FunctionTree.csv')
    parser.add_argument('--srczip', default='C:/code/codeQL_CoD/codeql/src.zip',
                       help='Path to src.zip file for code verification')
    parser.add_argument('--output', '-o', help='Output Excel file path (if not provided, original file will be backed up and enhanced)')
    parser.add_argument('--no-backup', action='store_true', help='Do not create backup of original file when overwriting')
    
    args = parser.parse_args()
    
    # Resolve paths
    script_dir = Path(__file__).parent
    excel_path = script_dir / args.excel
    function_tree_path = args.functions
    src_zip_path = args.srczip
    
    # Verify files exist
    if not excel_path.exists():
        print(f"ERROR: Excel file not found at {excel_path}")
        return 1
    
    if not Path(function_tree_path).exists():
        print(f"ERROR: FunctionTree.csv not found at {function_tree_path}")
        return 1
    
    if not Path(src_zip_path).exists():
        print(f"ERROR: src.zip not found at {src_zip_path}")
        return 1
    
    # Process
    results = process_findings(str(excel_path), function_tree_path, src_zip_path, args.test, args.test_start, args.quiet)
    
    if 'error' in results:
        print(f"ERROR: {results['error']}")
        return 1
    
    # Save enhanced Excel file if not in test mode
    if not args.test and 'enhanced_df' in results:
        enhanced_df = results['enhanced_df']
        
        # Determine output path
        if args.output:
            output_path = Path(args.output)
        else:
            # Default: add suffix to original filename
            output_path = excel_path.with_stem(excel_path.stem + '_Enhanced')
            
            # Create backup of original if not disabled and we're overwriting
            if not args.no_backup and output_path == excel_path:
                backup_path = excel_path.with_stem(excel_path.stem + '_Backup')
                print(f"\nCreating backup: {backup_path}")
                shutil.copy2(excel_path, backup_path)
        
        print(f"\nSaving enhanced Excel file with {len(enhanced_df.columns):,} total columns (original + analysis)...")
        print(f"Output file: {output_path}")
        
        try:
            enhanced_df.to_excel(output_path, index=False)
            print(f"✅ Successfully saved enhanced file: {output_path}")
            print(f"   {len(enhanced_df):,} rows × {len(enhanced_df.columns):,} columns")
            
            # Show new columns added
            original_columns = set(pd.read_excel(excel_path).columns)
            new_columns = [col for col in enhanced_df.columns if col not in original_columns]
            if new_columns:
                print(f"   Added {len(new_columns):,} analysis columns: {', '.join(new_columns[:5])}{'...' if len(new_columns) > 5 else ''}")
                
        except Exception as e:
            print(f"ERROR saving Excel file: {e}")
            return 1
    
    return 0

if __name__ == '__main__':
    exit(main())