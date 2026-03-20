#!/usr/bin/env python3
"""
Quick test to verify vulnerability type and message extraction from LLM analysis results.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ui.results_loader import ResultsLoader

def test_extraction():
    """Test the vulnerability type and message extraction."""
    loader = ResultsLoader()
    
    # Load issues to test extraction
    issues, errors = loader.load_all_issues("c")
    
    if errors:
        print("Errors encountered:")
        for err in errors:
            print(f"  {err}")
    
    if not issues:
        print("No issues found!")
        return
    
    print(f"Found {len(issues)} issues:")
    print()
    
    for issue in issues:
        print(f"Issue ID: {issue.id}")
        print(f"Issue Name: {issue.name}")
        print(f"Issue Type: {issue.issue_type}")
        if issue.message:
            print(f"Message: {issue.message[:100]}...")  # Truncate for display
        else:
            print("Message: None")
        print(f"File: {issue.file}:{issue.line}")
        print("-" * 50)

if __name__ == "__main__":
    test_extraction()