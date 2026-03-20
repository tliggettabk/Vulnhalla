# Vulnhalla Issues.csv Format Documentation

## Expected Column Structure

Vulnhalla expects the issues.csv file to have the following columns in this exact order:

### Core Required Columns (in order):
1. **name** - Issue name/identifier 
2. **help** - Help text or additional context
3. **type** - Issue type/category
4. **message** - Issue description/message
5. **file** - File path where issue was found
6. **start_line** - Starting line number of the issue
7. **start_offset** - Starting character offset 
8. **end_line** - Ending line number of the issue
9. **end_offset** - Ending character offset

### Optional Enhanced Columns (when available):
10. **matched_function** - Function name where issue is located
11. **function_length** - Length of the containing function
12. **function_start_line** - Starting line of the containing function  
13. **function_end_line** - Ending line of the containing function

## Columns Sent to the LLM

When Vulnhalla analyzes issues using the LLM, it sends the following columns from issues.csv:

1. **name** - Used as the issue type name in the prompt template
2. **help** - Used as the "Description" field in the prompt template  
3. **message** - Processed and used as the "Message" field (with bracket references replaced)
4. **file** - Used to construct the "Location" field (shows filename:line_number)
5. **start_line** - Used in the "Location" field and for code snippet extraction
6. **start_offset** - Used for extracting the exact code snippet
7. **end_offset** - Used for extracting the exact code snippet

## LLM Prompt Structure

The LLM receives a formatted prompt using this template structure:

```
### Issue Overview
Name: {name}
Description: {help}  
Message: {processed message}
Location: look at {filename}:{start_line} with '{code_snippet}'

### Hints for Validation
{issue-specific or general hints}

### Code
{full_function_code}
```

## Data Processing Details

### Message Processing
- The **message** field is processed to replace bracket references with actual code context
- Pattern: `[["text"|"relative://path/to/file:line:col:line:col"]]`
- Bracket references are replaced with readable text and code snippets

### Code Snippet Extraction
- The **code snippet** is extracted using: `code_file_contents[start_line-1][start_offset-1:end_offset]`
- Provides the exact problematic code highlighted by CodeQL

### Function Context
- The **full function code** is provided as additional context around the issue location
- Found using FunctionTree.csv to locate the containing function
- **Additional functions** may be included if the message references code outside the current function

## Columns NOT Sent to LLM

These columns are part of the standard format but are not directly sent to the LLM:
- **type** - Used for internal categorization
- **end_line** - Used for processing but not in prompt
- **matched_function** - Used internally for function mapping
- **function_length** - Used for validation/filtering
- **function_start_line** - Used for code extraction
- **function_end_line** - Used for code extraction

## Parser Implementation

The core parser is defined in `src/vulnhalla.py`:

```python
field_names = [
    "name", "help", "type", "message",
    "file", "start_line", "start_offset",
    "end_line", "end_offset"
]
```

Enhanced columns are added by tools like `add_function_boundaries.py` when mapping issues to specific functions from CodeQL's FunctionTree data.

## Template Files

- Main template: `data/templates/cpp/template.template`
- Issue-specific hints: `data/templates/cpp/{issue_name}.template`
- Fallback hints: `data/templates/cpp/general.template`