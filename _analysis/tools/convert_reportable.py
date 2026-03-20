#!/usr/bin/env python3
"""
Convert Reportable.csv to Vulnhalla issues.csv format

Filters for issues with First Detected date before 10/1/2025 and converts
to the expected Vulnhalla issues.csv format for analysis.
"""

import csv
import os
from datetime import datetime
from pathlib import Path


def parse_date(date_str):
    """Parse date from MM/DD/YY format to datetime object."""
    try:
        # Handle MM/DD/YY format (assuming 20YY for years)
        if '/' in date_str:
            month, day, year = date_str.split('/')
            # Convert 2-digit year to 4-digit (assume 20XX)
            if len(year) == 2:
                year = '20' + year
            return datetime(int(year), int(month), int(day))
    except (ValueError, IndexError):
        return None
    return None


def should_include_issue(first_detected):
    """Check if issue should be included based on first detected date."""
    cutoff_date = datetime(2025, 10, 1)  # 10/1/2025
    issue_date = parse_date(first_detected)
    
    if issue_date is None:
        print(f"Warning: Could not parse date '{first_detected}', including issue")
        return True  # Include if we can't parse the date
    
    return issue_date < cutoff_date


def convert_reportable_to_issues():
    """Convert Reportable.csv to issues.csv format."""
    
    reportable_file = r"C:\Users\tliggett\Downloads\Reportable.csv"
    output_file = r"C:\Users\tliggett\source\repos\Vulnhalla\tools\issues.csv"
    mapping_file = r"C:\Users\tliggett\source\repos\Vulnhalla\tools\cid_mapping.csv"
    
    print("REPORTABLE.CSV TO ISSUES.CSV CONVERTER")
    print("=" * 45)
    
    if not os.path.exists(reportable_file):
        print(f"ERROR: Reportable.csv not found at {reportable_file}")
        return 1
    
    # Read Reportable.csv
    print("Reading Reportable.csv...")
    reportable_issues = []
    
    with open(reportable_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            reportable_issues.append(row)
    
    print(f"Found {len(reportable_issues)} total issues")
    
    # Filter by date and convert
    print("Filtering and converting...")
    converted_issues = []
    mapping_records = []
    filtered_count = 0
    issue_id = 1
    
    for row in reportable_issues:
        first_detected = row.get('First Detected', '')
        
        if not should_include_issue(first_detected):
            filtered_count += 1
            continue
        
        # Convert to issues.csv format
        cid = row.get('CID', '')
        abk_classification = row.get('2. ABK_Classification', '')
        issue_type = row.get('Type', '')
        checker = row.get('Checker', '')
        file_path = row.get('File', '')
        line_number = row.get('Line Number', '0')
        
        # Build help field: CID + " " + ABK_Classification
        help_text = f"{cid} {abk_classification}".strip()
        
        # Create issues.csv row
        issues_row = {
            'name': issue_type,
            'help': help_text,
            'type': checker,
            'message': issue_type,  # Just use Type as requested
            'file': file_path,
            'start_line': line_number,
            'start_offset': '0',
            'end_line': line_number,
            'end_offset': '0'
        }
        
        converted_issues.append(issues_row)
        
        # Create mapping record for later reference
        mapping_record = {
            'issue_id': issue_id,
            'original_cid': cid,
            'first_detected': first_detected,
            'severity': row.get('Severity', ''),
            'component': row.get('Component', ''),
            'function': row.get('Function', ''),
            'impact': row.get('Impact', ''),
            'abk_classification': abk_classification
        }
        
        mapping_records.append(mapping_record)
        issue_id += 1
    
    print(f"Filtered out {filtered_count} issues (after 10/1/2025)")
    print(f"Converting {len(converted_issues)} issues")
    
    # Write issues.csv
    print(f"Writing issues.csv to {output_file}...")
    
    fieldnames = [
        'name', 'help', 'type', 'message', 'file', 
        'start_line', 'start_offset', 'end_line', 'end_offset'
    ]
    
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(converted_issues)
    
    # Write mapping file
    print(f"Writing CID mapping to {mapping_file}...")
    
    mapping_fieldnames = [
        'issue_id', 'original_cid', 'first_detected', 'severity', 
        'component', 'function', 'impact', 'abk_classification'
    ]
    
    with open(mapping_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=mapping_fieldnames)
        writer.writeheader()
        writer.writerows(mapping_records)
    
    print()
    print("CONVERSION SUMMARY:")
    print(f"Total issues processed: {len(reportable_issues)}")
    print(f"Issues filtered out (date): {filtered_count}")
    print(f"Issues converted: {len(converted_issues)}")
    print(f"Success rate: {len(converted_issues)/len(reportable_issues)*100:.1f}%")
    print()
    print("FILES CREATED:")
    print(f"  {output_file}")
    print(f"  {mapping_file}")
    print()
    print("Sample converted issues:")
    print("-" * 30)
    
    for i, issue in enumerate(converted_issues[:5]):
        print(f"{i+1}. {issue['name'][:40]}")
        print(f"   Help: {issue['help']}")
        print(f"   File: {issue['file']}")
        print(f"   Line: {issue['start_line']}")
        print()
    
    return 0


if __name__ == "__main__":
    exit(convert_reportable_to_issues())