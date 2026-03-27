"""
CodeQL database lookup utilities.

This module provides functions to query CodeQL CSV files (FunctionTree.csv,
Macros.csv, GlobalVars.csv, Classes.csv) and extract code snippets from
the source archive.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from src.utils.exceptions import CodeQLError
from src.utils.common_functions import read_file_lines_from_zip
from src.utils.csv_parser import parse_csv_row


class CodeQLDBLookup:
    """
    Encapsulates CodeQL database lookup operations for functions, macros,
    global variables, classes, and caller relationships.
    """

    def _iter_csv_lines(
        self,
        file_path: Union[str, Path],
        file_type_name: str
    ):
        """
        Generator that yields lines from a CSV file, handling file I/O errors.

        This helper centralizes CSV file opening, line iteration, and error handling.
        Each method can iterate over the yielded lines and apply method-specific logic.

        Args:
            file_path: Path to the CSV file to read.
            file_type_name: Descriptive name for the file type (e.g., "Function tree file",
                           "Macros CSV", "GlobalVars CSV") for error messages.

        Yields:
            str: Each line from the CSV file (including newline characters).

        Raises:
            CodeQLError: If file cannot be read (not found, permission denied, etc.).
        """
        try:
            with Path(file_path).open("r", encoding="utf-8") as f:
                while True:
                    line = f.readline()
                    if not line:
                        break
                    yield line
        except (FileNotFoundError, PermissionError, OSError) as e:
            raise self._convert_csv_file_error(e, file_path, file_type_name) from e


    @staticmethod
    def _convert_csv_file_error(
        error: Exception,
        file_path: Union[str, Path],
        file_type_name: str
    ) -> CodeQLError:
        """
        Convert file I/O exceptions to CodeQLError with consistent messaging.

        Args:
            error: The original exception (FileNotFoundError, PermissionError, or OSError).
            file_path: Path to the CSV file that caused the error.
            file_type_name: Descriptive name for the file type (e.g., "Function tree file",
                           "Macros CSV", "GlobalVars CSV") for error messages.

        Returns:
            CodeQLError: Converted exception with appropriate message.
        """
        file_path_str = str(file_path)
        if isinstance(error, FileNotFoundError):
            return CodeQLError(f"{file_type_name} not found: {file_path_str}")
        elif isinstance(error, PermissionError):
            return CodeQLError(f"Permission denied reading {file_type_name}: {file_path_str}")
        elif isinstance(error, OSError):
            return CodeQLError(f"OS error while reading {file_type_name}: {file_path_str}")
        else:
            # Fallback for unexpected exception types
            return CodeQLError(f"Error reading {file_type_name}: {file_path_str}")

    def find_method_implementations(
        self,
        lookup_csv: str,
        bare_method: str,
        namespace_hint: str = "",
        limit: int = 5,
    ) -> Tuple[List[str], int]:
        """
        Find qualified names of functions whose bare name matches `bare_method`.

        Used to suggest alternative implementations when Class::method is not
        found (e.g. the method is pure virtual and only concrete subclasses
        have it).

        Args:
            lookup_csv: Path to FunctionLookup.csv.
            bare_method: The unqualified method name (e.g. "Allocate").
            namespace_hint: Optional namespace prefix to prioritize matches from
                the same namespace (e.g. "Telescope" from "Telescope::Foo::Allocate").
            limit: Maximum number of results to return.

        Returns:
            Tuple of (list of up to `limit` qualified names, total match count).
            The total count lets callers decide whether suggestions are useful
            (e.g. suppress when total > 20 and there's no namespace hint).
        """
        keys = ["qualified_name", "function_name", "file", "start_line", "end_line"]
        same_ns: List[str] = []
        other: List[str] = []
        try:
            for line in self._iter_csv_lines(lookup_csv, "FunctionLookup CSV"):
                if bare_method not in line:
                    continue
                row_dict = parse_csv_row(line, keys)
                if not row_dict:
                    continue
                f_name = row_dict["function_name"].replace("\"", "").strip()
                if f_name == bare_method:
                    q_name = row_dict["qualified_name"].replace("\"", "").strip()
                    if namespace_hint and q_name.startswith(namespace_hint + "::"):
                        same_ns.append(q_name)
                    else:
                        other.append(q_name)
        except Exception:
            pass  # Best-effort; don't break tool execution
        total = len(same_ns) + len(other)
        # Prioritize same-namespace matches, then fill with others
        return (same_ns + other)[:limit], total

    def lookup_function(
        self,
        lookup_csv: str,
        function_name: str,
    ) -> Union[str, Dict[str, str]]:
        """
        Look up a function by name using FunctionLookup.csv (flat table, no caller gate).

        Matching strategy (first match wins):
          1. Exact match on qualified_name  (e.g. "PagedVirtualAddressAllocator::SetPageType")
          2. Exact match on function_name   (bare name, e.g. "SetPageType")
             — only if there is exactly ONE match (skip ambiguous bare names like "Allocate")
          3. Suffix match on qualified_name  (e.g. input "Class::Method" matches "Namespace::Class::Method")
             — only if there is exactly ONE match

        Args:
            lookup_csv: Path to FunctionLookup.csv.
            function_name: The name the LLM asked for (e.g. "SetPageType" or
                          "PagedVirtualAddressAllocator::SetPageType").

        Returns:
            Dict with keys [qualified_name, function_name, file, start_line, end_line]
            if found, or an error message string if not found.

        Raises:
            CodeQLError: If FunctionLookup CSV cannot be read.
        """
        keys = ["qualified_name", "function_name", "file", "start_line", "end_line"]
        search_name = function_name.strip().split("(")[0].strip()  # strip params if present
        search_bare = search_name.split("::")[-1]  # bare name for pre-filter

        qualified_matches: List[Dict[str, str]] = []
        bare_matches: List[Dict[str, str]] = []
        suffix_matches: List[Dict[str, str]] = []

        for line in self._iter_csv_lines(lookup_csv, "FunctionLookup CSV"):
            # Cheap pre-filter: bare name must appear somewhere in the row
            if search_bare not in line:
                continue

            row_dict = parse_csv_row(line, keys)
            if not row_dict or not row_dict.get("start_line"):
                continue

            q_name = row_dict["qualified_name"].replace("\"", "").strip()
            f_name = row_dict["function_name"].replace("\"", "").strip()

            # 1. Exact qualified match
            if q_name == search_name:
                qualified_matches.append(row_dict)

            # 2. Exact bare name match
            if f_name == search_bare:
                bare_matches.append(row_dict)

            # 3. Suffix match on qualified name (input is a partial qualifier)
            if ("::" in search_name
                    and q_name != search_name
                    and q_name.endswith("::" + search_name.split("::", 1)[-1])
                    and search_name.split("::")[0] in q_name):
                suffix_matches.append(row_dict)

        # Return first match from the priority tiers
        if qualified_matches:
            if len(qualified_matches) == 1:
                return qualified_matches[0]
            # Multiple qualified matches — pick the one in the most relevant file
            # (shouldn't happen often since qualified names are unique, but be safe)
            return qualified_matches[0]

        if len(bare_matches) == 1:
            return bare_matches[0]

        if len(suffix_matches) == 1:
            return suffix_matches[0]

        # Build informative error message
        if len(bare_matches) > 1:
            files = sorted(set(
                m["file"].replace("\"", "").rsplit("/", 1)[-1]
                for m in bare_matches[:5]
            ))
            return (
                f"Function '{function_name}' is ambiguous — {len(bare_matches)} functions "
                f"named '{search_bare}' exist (in {', '.join(files)}). "
                f"Use the qualified name like 'ClassName::{search_bare}' to disambiguate."
            )

        if len(suffix_matches) > 1:
            qualified_names = sorted(set(
                m["qualified_name"].replace("\"", "") for m in suffix_matches[:5]
            ))
            return (
                f"Function '{function_name}' matched {len(suffix_matches)} functions: "
                f"{', '.join(qualified_names)}. Use the full qualified name to disambiguate."
            )

        return (
            f"Function '{function_name}' not found. Make sure you're using "
            "the correct tool and args."
        )

    def get_function_by_line(
        self,
        function_tree_file: str,
        file: str,
        line: int
    ) -> Optional[Dict[str, str]]:
        """
        Retrieve the function dictionary from a CSV (FunctionTree.csv) that matches
        the specified file and line coverage.

        Args:
            function_tree_file (str): Path to the FunctionTree.csv file.
            file (str): Name of the file as it appears in the CSV row.
            line (int): A line number within the function's start_line and end_line range.

        Returns:
            Optional[Dict[str, str]]: The matching function row as a dict, or None if not found.
        
        Raises:
            CodeQLError: If function tree file cannot be read (not found, permission denied, etc.).
        """
        keys = ["function_name", "file", "start_line", "function_id", "end_line", "caller_id"]
        for function in self._iter_csv_lines(function_tree_file, "Function tree file"):
            if file in function:
                row_dict = parse_csv_row(function, keys)
                if row_dict and row_dict["start_line"] and row_dict["end_line"]:
                    start = int(row_dict["start_line"])
                    end = int(row_dict["end_line"])
                    if start <= line <= end:
                        return row_dict
        return None


    def get_function_by_name(
            self,
            function_tree_file: str,
            function_name: str,
            all_function: List[Dict[str, Any]],
            less_strict: bool = False
        ) -> Tuple[Union[str, Dict[str, str]], Optional[Dict[str, str]]]:
            """
            Retrieve a function by searching function_name in FunctionTree.csv.
            If not found, tries partial match if less_strict is True.

            Args:
                function_tree_file (str): Path to FunctionTree.csv.
                function_name (str): Desired function name (e.g., 'MyClass::MyFunc').
                all_function (List[Dict[str, Any]]): A list of known function dictionaries.
                less_strict (bool, optional): If True, use partial matching. Defaults to False.

            Returns:
                Tuple[Union[str, Dict[str, str]], Optional[Dict[str, str]]]:
                    - The found function (dict) or an error message (str).
                    - The "parent function" that references it, if relevant.
            
            Raises:
                CodeQLError: If function tree file cannot be read (not found, permission denied, etc.).
            """
            keys = ["function_name", "file", "start_line", "function_id", "end_line", "caller_id"]
            function_name_only = function_name.split("::")[-1]

            for current_function in all_function:
                try:
                    with Path(function_tree_file).open("r", encoding="utf-8") as f:
                        while True:
                            row = f.readline()
                            if not row:
                                break
                            if current_function["function_id"] in row:
                                row_dict = parse_csv_row(row, keys)
                                if not row_dict:
                                    continue

                                candidate_name = row_dict["function_name"].replace("\"", "")
                                if (candidate_name == function_name_only
                                        or (less_strict and function_name_only in candidate_name)):
                                    return row_dict, current_function
                except (FileNotFoundError, PermissionError, OSError) as e:
                    raise self._convert_csv_file_error(e, function_tree_file, "Function tree file") from e

            # Try partial matching if less_strict is False
            if not less_strict:
                return self.get_function_by_name(function_tree_file, function_name, all_function, True)
            else:
                err = (
                    f"Function '{function_name}' not found. Make sure you're using "
                    "the correct tool and args."
                )
                return err, None


    def get_macro(
        self,
        curr_db: str,
        macro_name: str,
        less_strict: bool = False
    ) -> Union[str, Dict[str, str]]:
        """
        Return macro info from Macros.csv for the given macro_name.
        If not found, tries partial match if less_strict is True.

        Args:
            curr_db (str): Path to the current CodeQL database folder.
            macro_name (str): Macro name to search for.
            less_strict (bool, optional): If True, use partial matching.

        Returns:
            Union[str, Dict[str, str]]:
                - A dict with 'macro_name' and 'body' if found,
                - or an error message string if not found.
        
        Raises:
            CodeQLError: If Macros CSV file cannot be read (not found, permission denied, etc.).
        """
        macro_file = Path(curr_db) / "Macros.csv"
        keys = ["macro_name", "body"]

        for macro in self._iter_csv_lines(macro_file, "Macros CSV"):
            if macro_name in macro:
                row_dict = parse_csv_row(macro, keys)
                if not row_dict:
                    continue

                actual_name = row_dict["macro_name"].replace("\"", "")
                if (actual_name == macro_name
                        or (less_strict and macro_name in actual_name)):
                    return row_dict

        if not less_strict:
            return self.get_macro(curr_db, macro_name, True)
        else:
            return (
                f"Macro '{macro_name}' not found. Make sure you're using the correct tool "
                "with correct args."
            )


    def get_global_var(
        self,
        curr_db: str,
        global_var_name: str,
        less_strict: bool = False
    ) -> Union[str, Dict[str, str]]:
        """
        Return a global variable from GlobalVars.csv matching global_var_name.
        If not found, tries partial match if less_strict is True.

        Args:
            curr_db (str): Path to current CodeQL database folder.
            global_var_name (str): The name of the global variable to find.
            less_strict (bool, optional): If True, use partial matching.

        Returns:
            Union[str, Dict[str, str]]:
                - A dict with ['global_var_name','file','start_line','end_line'] if found,
                - or an error message string if not found.
        
        Raises:
            CodeQLError: If GlobalVars CSV file cannot be read (not found, permission denied, etc.).
        """
        global_var_file = Path(curr_db) / "GlobalVars.csv"
        keys = ["global_var_name", "file", "start_line", "end_line"]
        var_name_only = global_var_name.split("::")[-1]

        for line in self._iter_csv_lines(global_var_file, "GlobalVars CSV"):
            if var_name_only in line:
                data_dict = parse_csv_row(line, keys)
                if not data_dict:
                    continue

                actual_name = data_dict["global_var_name"].replace("\"", "")
                if (actual_name == var_name_only
                        or (less_strict and var_name_only in actual_name)):
                    return data_dict

        if not less_strict:
            return self.get_global_var(curr_db, global_var_name, True)
        else:
            return (
                f"Global var '{global_var_name}' not found. "
                "Could it be a macro or should you use another tool?"
            )


    def get_class(
        self,
        curr_db: str,
        class_name: str,
        less_strict: bool = False,
        exact_only: bool = False
    ) -> Union[str, Dict[str, str]]:
        """
        Return class info (type, class_name, file, start_line, end_line, simple_name)
        from Classes.csv for class_name. If not found, tries partial match unless exact_only is True.

        Args:
            curr_db (str): Path to current CodeQL database folder.
            class_name (str): The name of the class/struct/union to find.
            less_strict (bool, optional): If True, use partial matching.
            exact_only (bool, optional): If True, never fall back to partial matching.
                Returns 'not found' instead of a fuzzy/closest match.

        Returns:
            Union[str, Dict[str, str]]:
                - A dict with keys ['type','class_name','file','start_line','end_line','simple_name']
                - or an error message string if not found.
        
        Raises:
            CodeQLError: If Classes CSV file cannot be read (not found, permission denied, etc.).
        """
        classes_file = Path(curr_db) / "Classes.csv"
        keys = ["type", "class_name", "file", "start_line", "end_line", "simple_name"]
        class_name_only = class_name.strip().rstrip(":").split("::")[-1].strip()
        if not class_name_only:
            return f"Class '{class_name}' is not a valid class name."

        # Search all three CSVs with the current match strictness.
        # On the first pass (less_strict=False), only exact matches are returned.
        # If none found, we recurse with less_strict=True to allow substring matching.
        # This ensures an exact typedef/enum hit is preferred over a substring
        # class hit (e.g. "StLayerMaskOMPV" finds the typedef, not "StLayerMaskOMPVRaw").
        csv_sources = [
            (classes_file, "Classes CSV"),
        ]
        enum_file = Path(curr_db) / "EnumLookup.csv"
        if enum_file.exists():
            csv_sources.append((enum_file, "EnumLookup CSV"))
        alias_file = Path(curr_db) / "TypeAliasLookup.csv"
        if alias_file.exists():
            csv_sources.append((alias_file, "TypeAliasLookup CSV"))

        for csv_file, csv_label in csv_sources:
            for row in self._iter_csv_lines(csv_file, csv_label):
                if class_name_only in row:
                    row_dict = parse_csv_row(row, keys)
                    if not row_dict:
                        continue
                    actual_class = row_dict["class_name"].replace('"', '')
                    simple_class = row_dict["simple_name"].replace('"', '')
                    if (
                        actual_class == class_name_only
                        or simple_class == class_name_only
                        or (less_strict and not exact_only and class_name_only in actual_class)
                        or (less_strict and not exact_only and class_name_only in simple_class)
                    ):
                        return row_dict

        if not less_strict and not exact_only:
            return self.get_class(curr_db, class_name, True, exact_only)

        return f"Class/enum/typedef '{class_name}' not found. Could it be a Namespace?"


    def get_caller_function(
        self,
        function_tree_file: str,
        current_function: Dict[str, str]
    ) -> Union[str, Dict[str, str]]:
        """
        Return the caller function from function_tree_file that calls current_function.

        Args:
            function_tree_file (str): Path to FunctionTree.csv.
            current_function (Dict[str, str]): The function dictionary whose caller we want.

        Returns:
            Union[str, Dict[str, str]]:
                - Dict describing the caller if found
                - or an error string if the caller wasn't found.
        
        Raises:
            CodeQLError: If function tree file cannot be read (not found, permission denied, etc.).
        """
        keys = ["function_name", "file", "start_line", "function_id", "end_line", "caller_id"]
        caller_id = current_function["caller_id"].replace("\"", "").strip()

        for line in self._iter_csv_lines(function_tree_file, "Function tree file"):
            if caller_id in line:
                data_dict = parse_csv_row(line, keys)
                if not data_dict:
                    continue
                if data_dict["function_id"].replace("\"", "").strip() == caller_id:
                    return data_dict

        # Fallback if 'caller_id' is in format file:line
        maybe_line = caller_id.split(":")
        if len(maybe_line) == 2:
            file_part, line_part = maybe_line
            function = self.get_function_by_line(function_tree_file, file_part[1:], int(line_part))
            if function:
                return function

        return (
            "Caller function was not found. "
            "Make sure you are using the correct tool with the correct args."
        )


    def extract_function_lines_from_db(
        self,
        db_path: str,
        current_function: Dict[str, str],
    ) -> Tuple[str, int, int, List[str]]:
        """
        Extract function lines from the CodeQL database source archive.

        Args:
            db_path (str): Path to the CodeQL database directory.
            current_function (Dict[str, str]): The function dictionary.

        Returns:
            Tuple[str, int, int, List[str]]:
                - file_path (str): The file path (after .replace and [1:])
                - start_line (int): Starting line number
                - end_line (int): Ending line number
                - all_lines (List[str]): Full file splitlines
        """
        src_zip = Path(db_path) / "src.zip"
        file_path = current_function["file"].replace("\"", "")[1:]
        file_path = file_path.replace(":","D_")  # Normalize path separators - fixed to match actual ZIP structure
        if not file_path.strip():
            raise CodeQLError(f"Empty file path in function record: {current_function}")
        #logger.debug(f"@@@4Extracting function lines: file_path='{file_path}', start_line={current_function['start_line']}, end_line={current_function['end_line']}")
        code_file = read_file_lines_from_zip(str(src_zip), file_path)
        lines = code_file.split("\n")

        start_line = int(current_function["start_line"])
        end_line = int(current_function["end_line"])
        return file_path, start_line, end_line, lines


    @staticmethod
    def format_numbered_snippet(file_path: str, start_line: int, snippet_lines: List[str]) -> str:
        """
        Format a code snippet with line numbers.

        Args:
            file_path (str): Path to the source file.
            start_line (int): Starting line number (1-indexed).
            snippet_lines (List[str]): The code lines to format.

        Returns:
            str: Formatted snippet with line numbers.
        """
        snippet = "\n".join(
            f"{start_line + i}: {text}" for i, text in enumerate(snippet_lines)
        )
        return f"file: {file_path}\n{snippet}"
