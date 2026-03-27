#!/usr/bin/env python3
"""
Core analysis engine for Vulnhalla.

This module coordinates the aggregation of raw CodeQL findings and their
classification by an LLM. It loads issues from CodeQL result files,
groups them by issue type, runs LLM-based analysis to decide whether
each finding is a true positive, false positive, or needs more data,
and writes structured result files for further inspection (e.g. in the UI).

Analysis Pipeline Algorithm:
    1. Collect DBs via get_all_dbs(dbs_folder), parse issues.csv, group by issue['name'].
    2. For each issue: find containing function via find_function_by_line() (smallest line range).
    3. Extract snippet and full function code.
    4. Replace bracket references in the message; if references point outside current function, append those functions' code.
    5. Build prompt; save *_raw.json; run LLM analysis; save *_final.json.
    6. Classify by substring: "1337"/"7337-LEAN-VULN" → true, "1007"/"7337-LEAN-SECURE" → false, "7331"/"7337" → more, else → more; log stats.
"""

from pathlib import Path, PurePosixPath
import csv
import io
import logging
import re
import json
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple
from src.utils.common_functions import (
    get_all_dbs,
    read_file_lines_from_zip,
    read_file as read_file_utf8,
    write_file_ascii,
    read_yml
)

# LLM analyzer for security analysis
from src.llm.llm_analyzer import LLMAnalyzer
from src.utils.config_validator import validate_and_exit_on_error
from src.utils.logger import get_logger
from src.utils.exceptions import VulnhallaError, CodeQLError, LLMApiError

logger = get_logger(__name__)


class IssueAnalyzer:
    """
    Analyzes all issues in CodeQL databases, fetches relevant code snippets,
    and forwards them to an LLM (via llm_analyzer) for triage.
    """

    def __init__(self, lang: str = "c", config: Optional[Dict[str, Any]] = None, prompt_file: Optional[str] = None, exact_only: bool = True, orchestrated: bool = False, plan_file: str = "", replay_lead: str = "", replay_synthesize: bool = False, plan_only: bool = False, cid: str = "", first_cid: bool = False, last_n: int = 0, parallel_leads: bool = True, batch: str = "") -> None:
        """
        Initialize the IssueAnalyzer with default parameters.

        Args:
            lang (str, optional): The language code. Defaults to 'c'.
            config (Dict, optional): Full LLM configuration dictionary. If not provided, loads from .env file.
            prompt_file (str, optional): System messages YAML filename to use
                (e.g. "system_messages.v12-verify-claims.yaml"). Defaults to "system_messages.yaml".
            exact_only (bool, optional): If True, get_class uses exact matching only (no fuzzy fallback). Defaults to True.
            orchestrated (bool, optional): If True, use Plan→Investigate→Synthesize engine instead of single-conversation. Defaults to False.
            cid (str, optional): Comma-separated CID(s) to process (e.g. "15518" or "15518,19309"). Defaults to "" (all).
            first_cid (bool, optional): If True, only process the first CID found in issues.csv. Defaults to False.
            last_n (int, optional): If > 0, process only the last N issues (for error recovery). Defaults to 0 (all).
            batch (str, optional): Batch identifier (e.g. "b3"). Uses issues-<batch>.csv instead of issues.csv. Defaults to "" (issues.csv).
        """
        self.lang = lang
        self.db_path: Optional[str] = None
        self.code_path: Optional[str] = None
        self.code_path_in_csv_row: Optional[str] = None
        self.config = config
        self.prompt_file = prompt_file
        self.exact_only = exact_only
        self.orchestrated = orchestrated
        self.plan_file = plan_file
        self.replay_lead = replay_lead
        self.replay_synthesize = replay_synthesize
        self.plan_only = plan_only
        self.cid = cid
        self.first_cid = first_cid
        self.last_n = last_n
        self.parallel_leads = parallel_leads
        self.batch = batch
        self._csv_run_tag: str = ""
        self._human_triage: Dict[str, Dict[str, str]] = {}

    # ----------------------------------------------------------------------
    # 0. Incremental CSV Tracking (orchestrated mode)
    # ----------------------------------------------------------------------

    # Human triage Excel — hardcoded for now
    _HUMAN_TRIAGE_XLSX = r"_analysis\x02-updateLineNums\Findings_WithCodeLine_WithTriageComment_Perfect.xlsx"

    _CID_CSV_COLUMNS = [
        "timestamp", "cid", "issue_type", "decision", "decision_code",
        "llm_verdict",
        "human_report", "human_triage_comment",
        "run_folder", "leads_count", "rounds", "tool_calls", "tool_calls_found",
        "prompt_tokens", "completion_tokens", "total_tokens",
        "estimated_cost_usd", "duration_seconds", "llm_seconds",
        "plan_seconds", "plan_llm_seconds",
        "investigate_seconds", "investigate_llm_seconds",
        "synthesize_seconds", "synthesize_llm_seconds",
        "model",
        "loc_initial", "loc_tool", "loc_total",
        "total_retries", "lead_failures", "status",
    ]

    _LEAD_CSV_COLUMNS = [
        "timestamp", "cid", "lead_id", "question", "answered", "confidence",
        "tool_calls", "tool_calls_cached", "tool_calls_found", "follow_up_rounds",
        "prompt_tokens", "completion_tokens", "total_tokens",
        "estimated_cost_usd", "duration_seconds", "llm_seconds",
        "loc_initial", "loc_tool", "loc_total", "loc_avg_per_tool",
        "retries",
    ]

    _TOOL_CALLS_CSV_COLUMNS = [
        "timestamp", "cid", "lead_id", "call_index", "tool",
        "first_arg", "args", "phase", "cached", "found", "loc",
        "duration_seconds",
    ]

    def _load_human_triage(self) -> Dict[str, Dict[str, str]]:
        """Load human triage data from the Perfect findings Excel.

        Returns a dict keyed by CID (str) with values {report, triage_comment}.
        Silently returns empty dict if the file is missing or unreadable.
        """
        xlsx_path = Path(self._HUMAN_TRIAGE_XLSX)
        if not xlsx_path.exists():
            logger.warning("Human triage Excel not found: %s", xlsx_path)
            return {}
        try:
            import openpyxl
            wb = openpyxl.load_workbook(str(xlsx_path), read_only=True, data_only=True)
            ws = wb.active
            headers = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
            cid_idx = headers.index("CID")
            report_idx = headers.index("Report")
            comment_idx = headers.index("Last Triage Comment")
            triage: Dict[str, Dict[str, str]] = {}
            for row in ws.iter_rows(min_row=2, values_only=True):
                cid_val = str(row[cid_idx]).strip() if row[cid_idx] is not None else ""
                if cid_val:
                    triage[cid_val] = {
                        "report": str(row[report_idx] or "").strip(),
                        "triage_comment": str(row[comment_idx] or "").strip(),
                    }
            wb.close()
            logger.info("Loaded human triage for %d CIDs from %s", len(triage), xlsx_path)
            return triage
        except Exception as e:
            logger.warning("Failed to load human triage Excel: %s", e)
            return {}

    def _append_cid_csv(self, base_output: str, finding_stats: Dict[str, Any]) -> None:
        """Append one row per CID to a timestamped run_cids CSV (incremental, crash-safe)."""
        csv_path = Path(base_output) / self.lang / f"run_cids_{self._csv_run_tag}.csv"
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not csv_path.exists()

        # Read run_summary.json for leads count, LOC aggregation, and verdict
        # (prefer in-memory findings passed by replay, fall back to disk)
        leads_count = 0
        loc_initial = loc_tool = loc_total = 0
        tool_calls_found = 0
        llm_verdict = ""
        run_folder = finding_stats.get("run_folder", "")
        findings_mem = finding_stats.get("findings")
        if findings_mem is not None:
            findings = findings_mem
            leads_count = len(findings)
        elif run_folder:
            summary_file = Path(run_folder) / "run_summary.json"
            findings = []
            if summary_file.exists():
                try:
                    with open(summary_file, "r", encoding="utf-8") as f:
                        summary = json.load(f)
                    findings = summary.get("findings", [])
                    leads_count = len(findings)
                    # Verdict: strip newlines/tabs so it stays one CSV row
                    raw_verdict = summary.get("verdict", "")
                    llm_verdict = re.sub(r'[\r\n\t]+', ' ', raw_verdict).strip()
                except (json.JSONDecodeError, OSError):
                    pass
        else:
            findings = []

        # Aggregate LOC and tool_calls_found from findings
        total_retries = 0
        lead_failures = 0
        for fl in findings:
            fl_loc = fl.get("loc", {})
            loc_initial += fl_loc.get("initial", 0)
            loc_tool += fl_loc.get("tool_total", 0)
            loc_total += fl_loc.get("total", 0)
            tool_calls_found += sum(
                1 for te in fl.get("tools_executed", [])
                if te.get("found")
            )
            total_retries += fl.get("retries", 0)
            if fl.get("status") == "failed" or (not fl.get("answered") and fl.get("confidence") == "none"):
                lead_failures += 1

        # CID-level status
        if lead_failures > 0:
            cid_status = f"lead_failures:{lead_failures}"
        else:
            cid_status = "ok"

        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cid": finding_stats.get("cid", ""),
            "issue_type": finding_stats.get("issue_type", ""),
            "decision": finding_stats.get("decision", ""),
            "decision_code": finding_stats.get("decision_code", ""),
            "llm_verdict": llm_verdict,
            "run_folder": run_folder,
            "leads_count": leads_count,
            "rounds": finding_stats.get("rounds", 0),
            "tool_calls": finding_stats.get("tool_calls", 0),
            "tool_calls_found": tool_calls_found,
            "prompt_tokens": finding_stats.get("prompt_tokens", 0),
            "completion_tokens": finding_stats.get("completion_tokens", 0),
            "total_tokens": finding_stats.get("total_tokens", 0),
            "estimated_cost_usd": finding_stats.get("estimated_cost_usd", 0),
            "duration_seconds": finding_stats.get("duration_seconds", 0),
            "llm_seconds": finding_stats.get("llm_seconds", 0),
            "plan_seconds": finding_stats.get("plan_seconds", 0),
            "plan_llm_seconds": finding_stats.get("plan_llm_seconds", 0),
            "investigate_seconds": finding_stats.get("investigate_seconds", 0),
            "investigate_llm_seconds": finding_stats.get("investigate_llm_seconds", 0),
            "synthesize_seconds": finding_stats.get("synthesize_seconds", 0),
            "synthesize_llm_seconds": finding_stats.get("synthesize_llm_seconds", 0),
            "model": finding_stats.get("model", ""),
            "loc_initial": loc_initial,
            "loc_tool": loc_tool,
            "loc_total": loc_total,
            "total_retries": total_retries,
            "lead_failures": lead_failures,
            "status": cid_status,
        }

        # Human triage lookup
        cid_str = str(row["cid"])
        human = self._human_triage.get(cid_str, {})
        row["human_report"] = human.get("report", "")
        row["human_triage_comment"] = human.get("triage_comment", "")

        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self._CID_CSV_COLUMNS)
            if write_header:
                writer.writeheader()
            writer.writerow(row)

    def _append_leads_csv(self, base_output: str, finding_stats: Dict[str, Any]) -> None:
        """Append one row per lead to run_leads.csv (incremental, crash-safe)."""
        # Prefer in-memory findings passed by replay, fall back to run_summary.json
        findings = finding_stats.get("findings")
        if findings is None:
            run_folder = finding_stats.get("run_folder", "")
            if not run_folder:
                return
            summary_file = Path(run_folder) / "run_summary.json"
            if not summary_file.exists():
                return
            try:
                with open(summary_file, "r", encoding="utf-8") as f:
                    summary = json.load(f)
            except (json.JSONDecodeError, OSError):
                return
            findings = summary.get("findings", [])

        if not findings:
            return

        csv_path = Path(base_output) / self.lang / f"run_leads_{self._csv_run_tag}.csv"
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not csv_path.exists()
        cid = finding_stats.get("cid", "")
        ts = datetime.now(timezone.utc).isoformat()

        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self._LEAD_CSV_COLUMNS)
            if write_header:
                writer.writeheader()
            for lead in findings:
                lead_loc = lead.get("loc", {})
                writer.writerow({
                    "timestamp": ts,
                    "cid": cid,
                    "lead_id": lead.get("id", ""),
                    "question": lead.get("question", ""),
                    "answered": lead.get("answered", ""),
                    "confidence": lead.get("confidence", ""),
                    "tool_calls": lead.get("tool_calls", 0),
                    "tool_calls_cached": lead.get("tool_calls_cached", 0),
                    "tool_calls_found": sum(
                        1 for te in lead.get("tools_executed", [])
                        if te.get("found")
                    ),
                    "follow_up_rounds": lead.get("follow_up_rounds", 0),
                    "prompt_tokens": lead.get("prompt_tokens", 0),
                    "completion_tokens": lead.get("completion_tokens", 0),
                    "total_tokens": lead.get("total_tokens", 0),
                    "estimated_cost_usd": lead.get("estimated_cost_usd", 0),
                    "duration_seconds": lead.get("duration_seconds", 0),
                    "llm_seconds": lead.get("llm_seconds", 0),
                    "loc_initial": lead_loc.get("initial", 0),
                    "loc_tool": lead_loc.get("tool_total", 0),
                    "loc_total": lead_loc.get("total", 0),
                    "loc_avg_per_tool": lead_loc.get("avg_per_tool_call", 0),
                    "retries": lead.get("retries", 0),
                })

    def _append_tool_calls_csv(self, base_output: str, finding_stats: Dict[str, Any]) -> None:
        """Append one row per tool call to run_tool_calls.csv (incremental, crash-safe)."""
        findings = finding_stats.get("findings")
        if findings is None:
            run_folder = finding_stats.get("run_folder", "")
            if not run_folder:
                return
            summary_file = Path(run_folder) / "run_summary.json"
            if not summary_file.exists():
                return
            try:
                with open(summary_file, "r", encoding="utf-8") as f:
                    summary = json.load(f)
            except (json.JSONDecodeError, OSError):
                return
            findings = summary.get("findings", [])

        if not findings:
            return

        csv_path = Path(base_output) / self.lang / f"run_tool_calls_{self._csv_run_tag}.csv"
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not csv_path.exists()
        cid = finding_stats.get("cid", "")
        ts = datetime.now(timezone.utc).isoformat()

        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self._TOOL_CALLS_CSV_COLUMNS)
            if write_header:
                writer.writeheader()
            for lead in findings:
                lead_id = lead.get("id", "")
                for idx, te in enumerate(lead.get("tools_executed", []), start=1):
                    args_clean = {k: v for k, v in te.get("args", {}).items()
                                  if k not in ("context", "reason")}
                    args_str = ", ".join(f"{k}={v}" for k, v in args_clean.items())
                    first_val = next(iter(args_clean.values()), "") if args_clean else ""
                    writer.writerow({
                        "timestamp": ts,
                        "cid": cid,
                        "lead_id": lead_id,
                        "call_index": idx,
                        "tool": te.get("tool", ""),
                        "first_arg": first_val,
                        "args": args_str,
                        "phase": te.get("phase", ""),
                        "cached": te.get("cached", False),
                        "found": te.get("found", ""),
                        "loc": te.get("loc", 0),
                        "duration_seconds": te.get("duration_seconds", 0),
                    })

    # ----------------------------------------------------------------------
    # 1. CSV Parsing and Data Gathering
    # ----------------------------------------------------------------------

    def parse_issues_csv(self, file_name: str) -> List[Dict[str, str]]:
        """
        Reads the issues.csv file produced by CodeQL (with a custom or default
        set of columns) and returns a list of dicts.

        Args:
            file_name (str): The path to 'issues.csv'.

        Returns:
            List[Dict[str, str]]: A list of issue objects parsed from CSV rows.
        
        Raises:
            CodeQLError: If file cannot be read (not found, permission denied, etc.).
        """
        field_names = [
            "name", "help", "type", "message",
            "file", "start_line", "start_offset",
            "end_line", "end_offset"
        ]
        issues = []
        try:
            with Path(file_name).open("r", encoding="utf-8") as f:
                csv_reader = csv.DictReader(f, fieldnames=field_names)
                for row in csv_reader:
                    issues.append(row)
        except FileNotFoundError as e:
            raise CodeQLError(f"Issues CSV file not found: {file_name}") from e
        except PermissionError as e:
            raise CodeQLError(f"Permission denied reading issues CSV: {file_name}") from e
        except OSError as e:
            raise CodeQLError(f"OS error while reading issues CSV: {file_name}") from e
        return issues

    @staticmethod
    def _resolve_db_path(dbs_dir: str) -> Optional[str]:
        """Find the first CodeQL DB under dbs_dir (lightweight — no issues.csv parsing)."""
        dbs = get_all_dbs(dbs_dir)
        if dbs:
            return dbs[0]
        return None

    def _derive_current_function(
        self, function_tree_file: str, code: str,
    ) -> Dict[str, str]:
        """Best-effort extraction of current_function from code header.

        The code written to 2_initial_code.json starts with:
            file: <path>
            <line>: <signature>
        We parse the file path and first line number, then look up in the
        function tree.
        """
        import re as _re
        match = _re.match(r"file:\s*(.+)\n(\d+):", code)
        if not match:
            return {}
        file_path_raw = match.group(1).strip()
        line_no = int(match.group(2))
        # Normalise for CSV lookup (same logic as process_issue_type)
        if ":" in file_path_raw:
            csv_path = file_path_raw.replace("\\", "/")
        else:
            csv_path = file_path_raw
        fn = self.find_function_by_line(function_tree_file, csv_path, line_no)
        return fn if fn else {}

    def collect_issues_from_databases(self, dbs_dir: str) -> Dict[str, List[Dict[str, str]]]:
        """
        Searches through all CodeQL databases in `dbs_folder`, collects issues
        from each DB, and groups them by issue name.

        Args:
            dbs_folder (str): The folder containing the language-specific databases.
                              or a folder that is the database itself.

        Returns:
            Dict[str, List[Dict[str, str]]]: All issues, grouped by issue name.
        
        Raises:
            CodeQLError: If database folder cannot be accessed or issues cannot be read.
        """
        issues_statistics: Dict[str, List[Dict[str, str]]] = {}
        
        actual_dbs = get_all_dbs(dbs_dir)
        for curr_db in actual_dbs:
            logger.info("Processing DB: %s", curr_db)
            curr_db_path = Path(curr_db)
            function_tree_csv = curr_db_path / "FunctionTree.csv"
            issues_filename = f"issues-{self.batch}.csv" if self.batch else "issues.csv"
            issues_file = curr_db_path / issues_filename
            if function_tree_csv.exists() and issues_file.exists():
                # parse_issues_csv() raises CodeQLError on errors
                issues = self.parse_issues_csv(str(issues_file))
                for issue in issues:
                    if issue["name"] not in issues_statistics:
                        issues_statistics[issue["name"]] = []
                    issue["db_path"] = curr_db
                    issues_statistics[issue["name"]].append(issue)
            else:
                logger.error("Error: Execute run_codeql_queries.py first!")
                continue

        return issues_statistics

    # ----------------------------------------------------------------------
    # 2. Function and Snippet Extraction
    # ----------------------------------------------------------------------

    def find_function_by_line(self, function_tree_file: str, file_path: str, line: int) -> Optional[Dict[str, str]]:
        """
        Finds the most specific (smallest) function containing the given file and line number.

        Algorithm:
            - Iterate rows where file_path substring appears
            - Keep rows where start_line <= line <= end_line and file_path in function["file"]
            - Return function with smallest (end_line - start_line), else None

        Args:
            function_tree_file (str): Path to the 'FunctionTree.csv' file.
            file_path (str): File path substring to match (uses substring containment).
            line (int): The line number to check within function range.

        Returns:
            Optional[Dict[str, str]]: The best matching function dictionary, or None if not found.
        
        Raises:
            CodeQLError: If function tree file cannot be read (not found, permission denied, etc.).
        """
        keys = ["function_name", "file", "start_line", "function_id", "end_line", "caller_id"]
        best_function = None
        smallest_range = float('inf')
        logger.debug(f"Searching for function in {function_tree_file} for {file_path}:{line}")
        try:
            with Path(function_tree_file).open("r", encoding="utf-8") as f:
                for row in f:
                    #file_path /C_/Users/tliggett/source/repos/CPlusPlusSmall/simpletest.cpp
                    #row C:/msys64/ucrt64/include/c++/14.2.0/bits/uses_allocator.h
                    if file_path in row:
                        fields = re.split(r',(?=(?:[^"]*"[^"]*")*[^"]*$)', row.strip())
                        if len(fields) != len(keys):
                            logger.debug(f"Malformed row in function tree: {row.strip()}")
                            continue  # Skip malformed rows

                        function = dict(zip(keys, fields))
                        try:
                            start_line = int(function["start_line"])
                            end_line = int(function["end_line"])

                        except ValueError:
                            logger.debug(f"Invalid line numbers in function: {function['function_name']}")
                            continue  # Skip if lines aren't integers
                        logger.debug(f"Checking function {function['function_name']} ")
                        # Check if the target line falls within this function's range
                        if start_line <= line <= end_line:
                            if file_path in function["file"]:
                                # Greedy selection: track the function with smallest range
                                # (most specific/nested function containing the line)
                                size = end_line - start_line
                                logger.debug(f"Function {function['function_name']} matches with size {size}")
                                if size < smallest_range:
                                    logger.debug(f"...and is the new best match")
                                    best_function = function
                                    smallest_range = size
        except FileNotFoundError as e:
            raise CodeQLError(f"Function tree file not found: {function_tree_file}") from e
        except PermissionError as e:
            raise CodeQLError(f"Permission denied reading function tree file: {function_tree_file}") from e
        except OSError as e:
            raise CodeQLError(f"OS error while reading function tree file: {function_tree_file}") from e

        return best_function

    def extract_function_code(self, code_file: List[str], function_dict: Dict[str, str]) -> str:
        """
        Produces lines of the function's code from a list of lines.

        Args:
            code_file (List[str]): A list of lines for the entire file.
            function_dict (Dict[str, str]): The dictionary describing the function.

        Returns:
            str: A snippet string of code for the function.
        """
        if not function_dict:
            return ""
        start_line_idx = int(function_dict["start_line"]) - 1  # Index for array access
        start_line_display = int(function_dict["start_line"])  # Index for display
        end_line = int(function_dict["end_line"])
        snippet_lines = code_file[start_line_idx:end_line]
        snippet = "\n".join(
            f"{start_line_display + i}: {s.replace(chr(9), '    ')}"
            for i, s in enumerate(snippet_lines)
        )
        return snippet

    # ----------------------------------------------------------------------
    # 3. Text Replacement & Prompt Building
    # ----------------------------------------------------------------------

    def create_bracket_reference_replacer(
        self,
        db_path: str,
        code_path: str
    ) -> Callable[[re.Match], str]:
        """
        Creates a replacement callback for re.sub to transform CodeQL bracket references
        into readable code snippets.

        Algorithm:
            - Parse (variable, path_type, file_path, line, offsets)
            - Resolve path: relative:// → code_path + file_path; else strip leading '/'
            - Read from src.zip, slice snippet, return "var 'snippet' (filename:line)"

        Args:
            db_path (str): Path to the current CodeQL database.
            code_path (str): Base path to the code. May differ on Windows vs. Linux.

        Returns:
            Callable[[re.Match], str]: A function that can be used with `re.sub`.
        
        Note:
            The returned callback function may raise `CodeQLError` if ZIP file cannot be read.
        """
        def replacement(match):
            variable = match.group(1)
            path_type = match.group(2)
            file_path = match.group(3)
            line_number = match.group(4)
            start_offset = match.group(5)
            end_offset = match.group(6)

            if path_type == "relative://":
                full_path = code_path + file_path
            else:
                full_path = file_path[1:] if file_path.startswith("/") else file_path
            logger.debug(f"@@@2Replacing bracket reference: variable={variable}, path_type={path_type}, file_path={file_path}, line={line_number}, offsets=({start_offset}, {end_offset})")
            code_text = read_file_lines_from_zip(
                str(Path(db_path) / "src.zip"),
                full_path
            )
            code_lines = code_text.split("\n")
            snippet = code_lines[int(line_number) - 1][int(start_offset) - 1:int(end_offset)]

            file_name = PurePosixPath(file_path).name
            return f"{variable} '{snippet}' ({file_name}:{int(line_number)})"

        return replacement

    def build_prompt_by_template(
        self,
        issue: Dict[str, str],
        message: str,
        snippet: str,
        code: str
    ) -> str:
        """
        Builds the final 'prompt' template to feed into an LLM, combining
        the code snippet, code content, and a set of hints.

        Args:
            issue (Dict[str, str]): The issue dictionary from parse_issues_csv.
            message (str): The processed "message" text to embed.
            snippet (str): The direct snippet from the code for the particular highlight.
            code (str): Additional code context (e.g. entire function).

        Returns:
            str: A final prompt string with the template + hints + snippet + code.
        
        Raises:
            VulnhallaError: If template files cannot be read (not found, permission denied, etc.).
        """
        # If language is 'c', many queries are stored under 'cpp'
        lang_folder = "cpp" if self.lang == "c" else self.lang

        # Try to read an existing template specific to the issue name
        templates_base = Path("data/templates") / lang_folder
        hints_path = templates_base / f"{issue['name']}.template"
        if not hints_path.exists():
            hints_path = templates_base / "general.template"

        hints = read_file_utf8(str(hints_path))

        # Read the larger general template
        template_path = templates_base / "template.template"
        template = read_file_utf8(str(template_path))

        file_name = PurePosixPath(issue["file"]).name
        location = f"look at {file_name}:{int(issue['start_line'])} with '{snippet}'"

        # Special case for "Use of object after its lifetime has ended"
        if issue["name"] == "Use of object after its lifetime has ended":
            message = message.replace("here", f"here ({location})", 1)

        prompt = template.format(
            name=issue["name"],
            description=issue["help"],
            message=message,
            location=location,
            hints=hints,
            code=code
        )
        return prompt

    # ----------------------------------------------------------------------
    # 4. Saving LLM Results
    # ----------------------------------------------------------------------

    def ensure_directories_exist(self, dirs: List[str]) -> None:
        """
        Creates all directories in the given list if they do not already exist.

        Args:
            dirs (List[str]): A list of directory paths to create if missing.
        
        Raises:
            VulnhallaError: If directory creation fails (permission denied, etc.).
        """
        for d in dirs:
            dir_path = Path(d)
            if not dir_path.exists():
                try:
                    dir_path.mkdir(parents=True, exist_ok=True)
                except PermissionError as e:
                    raise VulnhallaError(f"Permission denied creating directory: {d}") from e
                except OSError as e:
                    raise VulnhallaError(f"OS error creating directory: {d}") from e


    # ----------------------------------------------------------------------
    # 5. Main Analysis Routine
    # ----------------------------------------------------------------------

    def save_raw_input_data(
        self,
        prompt: str,
        function_tree_file: str,
        current_function: Dict[str, str],
        results_folder: str,
        issue_id: int,
        llm_analyzer: Optional[Any] = None
    ) -> None:
        """
        Saves the raw input data (prompt, function tree info, etc.) to a JSON file before
        sending it to the LLM.

        Args:
            prompt (str): The final prompt text sent to the LLM.
            function_tree_file (str): Path to 'FunctionTree.csv'.
            current_function (Dict[str, str]): The currently found function dict.
            results_folder (str): Folder path where we store the result files.
            issue_id (int): The numeric ID of the current issue.
            llm_analyzer (LLMAnalyzer, optional): The LLM analyzer instance for extracting model/config info.
        
        Raises:
            VulnhallaError: If file cannot be written (permission denied, etc.).
        """
        raw_dict: Dict[str, Any] = {
            "function_tree_file": function_tree_file,
            "current_function": current_function,
            "db_path": self.db_path,
            "code_path": self.code_path,
            "prompt": prompt
        }
        # Include model/provider metadata if available
        if llm_analyzer is not None:
            raw_dict["model"] = getattr(llm_analyzer, 'model', None)
            config = getattr(llm_analyzer, 'config', None)
            if config:
                raw_dict["provider"] = config.get("provider", "unknown")
                raw_dict["temperature"] = config.get("temperature")
                raw_dict["top_p"] = config.get("top_p")

        raw_data = json.dumps(raw_dict, ensure_ascii=False)

        raw_output_file = Path(results_folder) / f"{issue_id}_raw.json"
        write_file_ascii(str(raw_output_file), raw_data)


    def format_llm_messages(self, messages: List[str]) -> str:
        """
        Converts the list of messages returned by the LLM into a JSON-ish string to
        store as output.

        Args:
            messages (List[str]): The messages from the LLM.

        Returns:
            str: A string representation of LLM messages (somewhat JSON-formatted).
        """
        gpt_result = "[\n    " + ",\n    ".join(
            f"'''{item}'''" if "\n" in item else repr(item) for item in messages).replace("\\n", "\n    ").replace(
            "\\t", " ") + "\n]"
        return gpt_result


    def determine_issue_status(self, llm_content: str) -> Tuple[str, str]:
        """
        Checks the content returned by the LLM to see if it includes certain
        status codes that classify the issue as 'true' or 'false' or 'more'.

        Args:
            llm_content (str): The text content from the LLM's final response.

        Returns:
            Tuple[str, str]: (status, matched_code) where status is "true"/"false"/"more"
                and matched_code is the actual code found (e.g. "1337", "7337-LEAN-VULN").
        """
        if "7337-LEAN-VULN" in llm_content:
            return "true", "7337-LEAN-VULN"
        elif "1337" in llm_content:
            return "true", "1337"
        elif "7337-LEAN-SECURE" in llm_content:
            return "false", "7337-LEAN-SECURE"
        elif "1007" in llm_content:
            return "false", "1007"
        elif "7331" in llm_content:
            return "more", "7331"
        elif "7337" in llm_content:
            return "more", "7337"
        else:
            return "more", ""

    def append_extra_functions(
        self,
        extra_lines: List[tuple[str, str, str]],
        function_tree_file: str,
        src_zip_path: str,
        code: str,
        current_function: Dict[str, str]
    ) -> Tuple[str, List[Dict[str, str]]]:
        """
        Appends code from additional functions referenced outside the current function.

        Algorithm:
            - Skip references within current function range
            - For external refs: find containing function via find_function_by_line(), dedupe by dict equality
            - Append extracted function code; return updated code and functions list

        Args:
            extra_lines (List[tuple[str, str, str]]): References as (path_type, file_path, line_number).
            function_tree_file (str): Path to 'FunctionTree.csv'.
            src_zip_path (str): Path to the DB's src.zip file.
            code (str): The existing code snippet.
            current_function (Dict[str, str]): The currently found function dict.

        Returns:
            Tuple[str, List[Dict[str, str]]]: Extended code snippet and list of all functions.
        
        Raises:
            CodeQLError: If function tree file or ZIP file cannot be read.
        """
        functions = [current_function]
        for another_func_ref in extra_lines:
            # Unpack reference tuple: (path_type, file_path, line_number)
            path_type, file_ref, line_ref = another_func_ref
            file_ref = file_ref.strip()

            # Resolve file path based on path type
            if path_type == "relative://":
                file_ref = self.code_path + file_ref
            else:
                # Remove leading slash for absolute paths (file://)
                file_ref = file_ref[1:] if file_ref.startswith("/") else file_ref

            # If it's within the same function's line range, skip
            start_line_func = int(current_function["start_line"])
            end_line_func = int(current_function["end_line"])
            if start_line_func <= int(line_ref) <= end_line_func:
                continue

            # Find the function containing this reference using the greedy selection algorithm
            new_function = self.find_function_by_line(function_tree_file, "/" + file_ref, int(line_ref))
            # Deduplication: Only add if function was found and not already in the list
            if new_function and new_function not in functions:
                functions.append(new_function)
                # Read the function's source file and extract its code
                print(f"@@1Appending extra function {new_function['function_name']} for reference at {file_ref}:{line_ref}")
                code_file2 = read_file_lines_from_zip(src_zip_path, file_ref).split("\n")
                code += (
                    "\n\nfile: " + file_ref + "\n" +
                    self.extract_function_code(code_file2, new_function)
                )

        return code, functions

    def get_next_issue_id(self, issue_type: str) -> int:
        """
        Gets the maximum issue ID currently in the results folder.
        Returns 0 if no files exist. The caller should add 1 to get the next ID.
        """
        max_issue_id = 1
        base_output = "output/results_orchestrated" if self.orchestrated else "output/results"
        results_folder = Path(base_output) / self.lang / issue_type.replace(" ", "_").replace("/", "-")
        if not results_folder.exists() or len(list(results_folder.glob("*.json"))) == 0:
            return 1
            
        for file in results_folder.glob("*.json"):
            issue_id = int(file.stem.split("_")[0])
            max_issue_id = max(issue_id, max_issue_id)
        return max_issue_id + 1


    def process_issue_type(
        self,
        issue_type: str,
        issues_of_type: List[Dict[str, str]],
        llm_analyzer: LLMAnalyzer,
        run_stats: Optional[List[Dict[str, Any]]] = None,
        finding_offset: int = 0,
        total_findings: int = 0,
    ) -> None:
        """
        Processes all issues of a single type. Builds file/folder paths, runs
        analysis, calls the LLM, and saves results.

        Algorithm (per issue):
            - Normalize paths (Windows: ':'→'_', '\'→'/'; Linux: strip leading '/')
            - Find function; extract snippet [start_offset-1:end_offset]
            - Replace bracket refs; append extra functions if needed
            - Build prompt; save raw/final; run LLM
            - Classify by '1337'/'1007'/'7331'/'7337' with directional confidence; log stats

        Args:
            issue_type (str): The name of the issue type.
            issues_of_type (List[Dict[str, str]]): All issues belonging to that type.
            llm_analyzer (LLMAnalyzer): The LLM analyzer instance to use for queries.
            run_stats (List[Dict], optional): Accumulator list for per-finding stats.
        
        Raises:
            CodeQLError: If database files cannot be read (YAML, ZIP, CSV, etc.).
            VulnhallaError: If result files cannot be written.
            LLMError: If LLM analysis fails.
        """
        if run_stats is None:
            run_stats = []
        base_output = "output/results_orchestrated" if self.orchestrated else "output/results"
        results_folder = Path(base_output) / self.lang / issue_type.replace(" ", "_").replace("/", "-")
        self.ensure_directories_exist([str(results_folder)])

        issue_id = self.get_next_issue_id(issue_type)
        real_issues = []
        false_issues = []
        more_data = []
        skipped_issues = []  # Track issues skipped due to LLM errors (timeout, rate limit, etc.)

        logger.info("Found %d issues of type %s", len(issues_of_type), issue_type)
        logger.info("")
        for idx, issue in enumerate(issues_of_type):
            finding_num = finding_offset + idx + 1
            progress = "[%d/%d]" % (finding_num, total_findings) if total_findings else ""
            self.db_path = issue["db_path"]
            db_path_obj = Path(self.db_path)
            db_yml_path = db_path_obj / "codeql-database.yml"
            db_yml = read_yml(str(db_yml_path))
            self.code_path = db_yml["sourceLocationPrefix"]

            # Path normalization for cross-platform compatibility:
            # Windows paths contain ":" (e.g., "C:\path\to\code") which conflicts with
            # ZIP archive path handling. We normalize by:
            # - Replacing ":" with "_" (e.g., "C_" instead of "C:")
            # - Converting backslashes to forward slashes
            # Linux paths are absolute (start with "/") which we remove for ZIP access
            if ":" in self.code_path:
                # Windows path: normalize drive letter and separators
                #self.code_path = self.code_path.replace(":", "_").replace("\\", "/")
                self.code_path_in_csv_row = self.code_path.replace("\\", "/")
                self.code_path = self.code_path_in_csv_row.replace(":", "_")
            else:
                # Linux path: remove leading slash
                self.code_path = self.code_path[1:]

            function_tree_file = str(db_path_obj / "FunctionTree.csv")
            src_zip_path = str(db_path_obj / "src.zip")

            full_file_path = self.code_path + issue["file"]
            logger.info("*" * 80)
            if progress:
                logger.info("%s CID %s — %s", progress, issue.get('name', issue_id), issue["message"][:100])
            else:
                logger.info("Processing issue ID %d: %s", issue_id, issue["message"])
            logger.info("%s, line: %s", issue["file"], issue["start_line"])

            logger.debug(f"@@@3Processing issue {issue_id}: file path in CSV='{issue['file']}', resolved full path='{full_file_path}'")
            code_file_contents = read_file_lines_from_zip(src_zip_path, full_file_path).split("\n")

            current_function = self.find_function_by_line(
                function_tree_file,
                #"/" + 
                self.code_path_in_csv_row + issue["file"],
                int(issue["start_line"])
            )
            if not current_function:
                logger.warning("issue %s: Can't find the function or function is too big!", issue_id)
                continue

            snippet = code_file_contents[int(issue["start_line"]) - 1][
                int(issue["start_offset"]) - 1:int(issue["end_offset"])
            ]
            logger.debug(f"Extracted snippet: {snippet}")
            code = (
                "file: " + self.code_path_in_csv_row + issue["file"] + "\n" +
                self.extract_function_code(code_file_contents, current_function)
            )

            # Replace bracket refs in message
            bracket_pattern = r'\[\["(.*?)"\|"((?:relative://|file://))?(/.*?):(\d+):(\d+):\d+:(\d+)"\]\]'
            transform_func = self.create_bracket_reference_replacer(self.db_path, self.code_path)
            message = re.sub(bracket_pattern, transform_func, issue["message"])

            # Find extra refs for context expansion
            extra_lines_pattern = r'\[\[".*?"\|"((?:relative://|file://)?)(/.*?):(\d+):\d+:\d+:\d+"\]\]'
            extra_lines = re.findall(extra_lines_pattern, issue["message"])
            functions = [current_function]

            if extra_lines:
                code, functions = self.append_extra_functions(
                    extra_lines, function_tree_file, src_zip_path, code, current_function
                )

            prompt = self.build_prompt_by_template(issue, message, snippet, code)
            logger.debug(f"Final prompt for issue {issue_id}:\n{prompt}")
            logger.debug("*" * 80)
            # Save raw input to the LLM
            if not self.orchestrated:
                self.save_raw_input_data(prompt, function_tree_file, current_function, results_folder, issue_id, llm_analyzer)

            # Send to LLM (with error handling for timeouts and API errors)
            try:
                extra_kwargs = {}
                if self.orchestrated:
                    extra_kwargs["results_folder"] = results_folder
                    extra_kwargs["code"] = code
                    if self.plan_file:
                        extra_kwargs["plan_file"] = self.plan_file
                    if self.replay_lead:
                        extra_kwargs["replay_lead"] = self.replay_lead
                    if self.replay_synthesize:
                        extra_kwargs["replay_synthesize"] = True
                    if self.plan_only:
                        extra_kwargs["plan_only"] = True
                messages, content, finding_stats = llm_analyzer.run_llm_security_analysis(
                    prompt,
                    function_tree_file,
                    current_function,
                    functions,
                    self.db_path,
                    **extra_kwargs,
                )
            except LLMApiError as e:
                # Skip this issue on LLM errors (timeout, rate limit, etc.) and continue with others
                logger.warning("Issue ID: %s SKIPPED - LLM error: %s", issue_id, e)
                skipped_issues.append(issue_id)
                issue_id += 1
                continue

            gpt_result = self.format_llm_messages(messages)
            if not self.orchestrated:
                final_file = Path(results_folder) / f"{issue_id}_final.json"
                write_file_ascii(str(final_file), gpt_result)

            # Check status code in LLM content
            status, decision_code = self.determine_issue_status(content)
            if status == "true":
                real_issues.append(issue_id)
                status = "True Positive"
            elif status == "false":
                false_issues.append(issue_id)
                status = "False Positive"
            else:
                more_data.append(issue_id)
                status = "LLM needs More Data"

            # Log issue status
            logger.info("Issue ID: %s, LLM decision: -> %s", issue_id, status)
            if not self.orchestrated:
                logger.info("")
                logger.info("LLM Final Answer:\n%s", content)
                logger.info("")

            # Track per-finding stats for run summary
            finding_stats['cid'] = issue.get('name', str(issue_id))
            finding_stats['issue_type'] = issue_type
            finding_stats['decision'] = status
            finding_stats['decision_code'] = decision_code
            run_stats.append(finding_stats)

            # Incremental CSV tracking (orchestrated mode)
            if self.orchestrated:
                self._append_cid_csv(base_output, finding_stats)
                self._append_leads_csv(base_output, finding_stats)
                self._append_tool_calls_csv(base_output, finding_stats)

            issue_id += 1

        logger.info("")
        logger.info("Issue type: %s", issue_type)
        logger.info("Total issues: %d", len(issues_of_type))
        logger.info("True Positive: %d", len(real_issues))
        logger.info("False Positive: %d", len(false_issues))
        logger.info("LLM needs More Data: %d", len(more_data))
        if skipped_issues:
            logger.warning("Skipped (LLM errors): %d (IDs: %s)", len(skipped_issues), skipped_issues)
        logger.info("")


    def run(self, dbs_dir: str) -> None:
        """
        Main analysis routine:
        1. Initializes the LLM.
        2. Finds all CodeQL DBs for the given language.
        3. Parses each DB's issues.csv, aggregates them by issue type.
        4. Asks the LLM for each issue's snippet context, saving final results
           in various directory structures.
        
        Args:
            dbs_dir (str): Path to the directory containing downloaded databases.
                              or a folder that is the database itself.
            
        Raises:
            CodeQLError: If database files cannot be accessed or read.
            VulnhallaError: If directory creation or file writing fails.
            LLMError: If LLM initialization or analysis fails.
        """
        # Validate configuration before starting
        if self.config is None:
           validate_and_exit_on_error()
        
        # Capture console output for inclusion in summary JSON
        log_capture_stream = io.StringIO()
        log_capture_handler = logging.StreamHandler(log_capture_stream)
        log_capture_handler.setLevel(logging.INFO)
        log_capture_handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
        logging.getLogger().addHandler(log_capture_handler)

        prompt_loader = None
        if self.prompt_file:
            from src.utils.prompt_loader import PromptLoader
            prompt_loader = PromptLoader(system_messages_file=self.prompt_file)
            logger.info("Using prompt file: %s", self.prompt_file)

        if self.orchestrated:
            from src.llm.orchestrator import Orchestrator
            llm_analyzer = Orchestrator(prompt_loader=prompt_loader, exact_only=self.exact_only, parallel_leads=self.parallel_leads)
            llm_analyzer.init_llm_client(config=self.config)
            logger.info("Engine: orchestrated (Plan -> Investigate -> Synthesize)")
        else:
            llm_analyzer = LLMAnalyzer(prompt_loader=prompt_loader, exact_only=self.exact_only)
            llm_analyzer.init_llm_client(config=self.config)
            logger.info("Engine: single-conversation (llm_analyzer)")

        # Run-level stats accumulator
        run_stats: List[Dict[str, Any]] = []
        run_start_time = time.time()

        # Per-run CSV tag: timestamp + _partial for replay runs
        ts_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
        is_partial = bool(self.plan_file and (self.replay_lead or self.replay_synthesize))
        self._csv_run_tag = f"{ts_tag}_partial" if is_partial else ts_tag

        # Load human triage data once for CID CSV enrichment
        self._human_triage = self._load_human_triage() if self.orchestrated else {}

        # --- Plan-file replay: bypass issues.csv / DB scan entirely ---
        if self.plan_file and self.orchestrated:
            plan_path = Path(self.plan_file)
            run_folder = plan_path.parent
            plan_cid = run_folder.parent.name  # .../c/{CID}/run_NNN/...
            results_folder = str(run_folder.parent)  # .../c/{CID}

            # Load stored runtime context (if available)
            context_file = run_folder / "2_initial_code.json"
            if context_file.exists():
                with open(context_file, "r", encoding="utf-8") as f:
                    stored_ctx = json.load(f)
            else:
                stored_ctx = {}

            # Use stored context; fall back to resolving from DB dir for old runs
            prompt = stored_ctx.get("prompt", "")
            code = stored_ctx.get("code", "")
            current_function = stored_ctx.get("current_function", {})
            functions = stored_ctx.get("functions", [current_function])
            function_tree_file = stored_ctx.get("function_tree_file", "")
            db_path = stored_ctx.get("db_path", "")

            # Old 2_initial_code.json files don't have runtime context.
            # Try to resolve FunctionTree.csv and db_path from dbs_dir.
            if not function_tree_file or not db_path:
                resolved_db = self._resolve_db_path(dbs_dir)
                if resolved_db:
                    if not db_path:
                        db_path = resolved_db
                    if not function_tree_file:
                        function_tree_file = str(Path(resolved_db) / "FunctionTree.csv")
                    if not current_function and code:
                        # Try to derive current_function from the code header
                        # The code starts with "file: <path>\n<line>: <sig>"
                        current_function = self._derive_current_function(
                            function_tree_file, code)
                    if not functions or functions == [{}]:
                        functions = [current_function] if current_function else []
                    logger.info("Plan replay: CID %s from %s (context resolved from DB)",
                                plan_cid, run_folder)
                else:
                    logger.info("Plan replay: CID %s from %s (no stored context, no DB fallback)",
                                plan_cid, run_folder)
            else:
                logger.info("Plan replay: CID %s from %s (stored context, no DB scan)",
                            plan_cid, run_folder)

            extra_kwargs: Dict[str, Any] = {
                "results_folder": results_folder,
                "code": code,
                "plan_file": self.plan_file,
            }
            if self.replay_lead:
                extra_kwargs["replay_lead"] = self.replay_lead
            if self.replay_synthesize:
                extra_kwargs["replay_synthesize"] = True
            if self.plan_only:
                extra_kwargs["plan_only"] = True

            try:
                messages, content, finding_stats = llm_analyzer.run_llm_security_analysis(
                    prompt, function_tree_file, current_function, functions, db_path,
                    **extra_kwargs,
                )
            except LLMApiError as e:
                logger.warning("CID %s SKIPPED - LLM error: %s", plan_cid, e)
                messages, content, finding_stats = [], "", {}

            if content:
                status, decision_code = self.determine_issue_status(content)
                if status == "true":
                    status = "True Positive"
                elif status == "false":
                    status = "False Positive"
                else:
                    status = "LLM needs More Data"
                logger.info("CID %s, LLM decision: -> %s", plan_cid, status)
                finding_stats['cid'] = plan_cid
                finding_stats['decision'] = status
                finding_stats['decision_code'] = decision_code
                run_stats.append(finding_stats)

                # Incremental CSV tracking (replay mode)
                base_output = "output/results_orchestrated"
                self._append_cid_csv(base_output, finding_stats)
                self._append_leads_csv(base_output, finding_stats)
                self._append_tool_calls_csv(base_output, finding_stats)
        else:
            # --- Normal mode: gather issues from all DBs ---
            issues_statistics = self.collect_issues_from_databases(dbs_dir)

            # --- Last N filter (for error recovery) ---
            if self.last_n > 0:
                # Flatten all issues with their types, sort by issue name (CID), take last N
                all_issues_with_type = []
                for issue_type, issues in issues_statistics.items():
                    for issue in issues:
                        all_issues_with_type.append((issue_type, issue))
                
                # Sort by CID (issue name) to ensure consistent ordering
                all_issues_with_type.sort(key=lambda x: x[1].get("name", ""))
                
                # Take only the last N issues
                last_issues = all_issues_with_type[-self.last_n:] if self.last_n < len(all_issues_with_type) else all_issues_with_type
                
                # Rebuild issues_statistics with only the last N
                issues_statistics = {}
                for issue_type, issue in last_issues:
                    if issue_type not in issues_statistics:
                        issues_statistics[issue_type] = []
                    issues_statistics[issue_type].append(issue)
                
                found_cids = {issue.get("name") for _, issue in last_issues}
                logger.info("Last %d filter: processing %d issue(s) with CIDs: %s", 
                           self.last_n, len(last_issues), ", ".join(sorted(found_cids)))

            # --- CID filters ---
            if self.cid:
                # Filter to specific CID(s): comma-separated list
                cid_set = {c.strip() for c in self.cid.split(",") if c.strip()}
                filtered: Dict[str, List[Dict[str, str]]] = {}
                for issue_type, issues in issues_statistics.items():
                    matching = [i for i in issues if i.get("name", "") in cid_set]
                    if matching:
                        filtered[issue_type] = matching
                found_cids = {i.get("name") for v in filtered.values() for i in v}
                missing = cid_set - found_cids
                if missing:
                    logger.warning("CID filter: %s not found in issues.csv", ", ".join(sorted(missing)))
                issues_statistics = filtered
                logger.info("CID filter: %d issue(s) matching %s",
                            sum(len(v) for v in filtered.values()), ", ".join(sorted(cid_set)))
            elif self.first_cid:
                # Keep only the first CID encountered (by insertion order)
                first_type = next(iter(issues_statistics), None)
                if first_type and issues_statistics[first_type]:
                    first_issue = issues_statistics[first_type][0]
                    first_name = first_issue.get("name", "")
                    issues_statistics = {first_type: [first_issue]}
                    logger.info("first_cid: processing only CID %s", first_name)

            total_issues = 0
            for issue_type in issues_statistics:
                total_issues += len(issues_statistics[issue_type])
            logger.info("Total issues found: %d", total_issues)
            logger.info("")

            # Process all issues, type by type
            finding_offset = 0
            for issue_type in issues_statistics.keys():
                self.process_issue_type(
                    issue_type, issues_statistics[issue_type], llm_analyzer, run_stats,
                    finding_offset=finding_offset, total_findings=total_issues,
                )
                finding_offset += len(issues_statistics[issue_type])

        # --- Write run_summary.json ---
        run_duration = time.time() - run_start_time
        tp_count = sum(1 for s in run_stats if s.get('decision') == 'True Positive')
        fp_count = sum(1 for s in run_stats if s.get('decision') == 'False Positive')
        md_count = sum(1 for s in run_stats if s.get('decision') == 'LLM needs More Data')
        total_prompt_tokens = sum(s.get('prompt_tokens', 0) for s in run_stats)
        total_completion_tokens = sum(s.get('completion_tokens', 0) for s in run_stats)
        total_all_tokens = sum(s.get('total_tokens', 0) for s in run_stats)
        total_cost = sum(s.get('estimated_cost_usd', 0) for s in run_stats)

        # LOC aggregation
        total_initial_loc = sum(s.get('loc', {}).get('initial', 0) for s in run_stats)
        total_tool_loc = sum(s.get('loc', {}).get('tool_total', 0) for s in run_stats)
        total_loc = sum(s.get('loc', {}).get('total', 0) for s in run_stats)
        total_tool_calls_for_loc = sum(s.get('tool_calls', 0) for s in run_stats)
        avg_loc_per_tool = round(total_tool_loc / total_tool_calls_for_loc, 1) if total_tool_calls_for_loc else 0

        prompt_file_used = llm_analyzer.prompt_loader.system_messages_file
        summary = {
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "model": getattr(llm_analyzer, 'model', None),
            "provider": (llm_analyzer.config or {}).get("provider", "unknown"),
            "prompt_file": prompt_file_used,
            "exact_only": self.exact_only,
            "language": self.lang,
            "dbs_dir": dbs_dir,
            "findings_processed": len(run_stats),
            "totals": {
                "true_positives": tp_count,
                "false_positives": fp_count,
                "more_data": md_count,
                "prompt_tokens": total_prompt_tokens,
                "completion_tokens": total_completion_tokens,
                "total_tokens": total_all_tokens,
                "estimated_cost_usd": round(total_cost, 4),
                "run_duration_seconds": round(run_duration, 2),
                "loc": {
                    "initial": total_initial_loc,
                    "tool_total": total_tool_loc,
                    "total": total_loc,
                    "avg_per_tool_call": avg_loc_per_tool,
                },
            },
            "averages_per_finding": {
                "prompt_tokens": total_prompt_tokens // len(run_stats) if run_stats else 0,
                "completion_tokens": total_completion_tokens // len(run_stats) if run_stats else 0,
                "total_tokens": total_all_tokens // len(run_stats) if run_stats else 0,
                "estimated_cost_usd": round(total_cost / len(run_stats), 4) if run_stats else 0,
                "loc": {
                    "initial": total_initial_loc // len(run_stats) if run_stats else 0,
                    "tool_total": total_tool_loc // len(run_stats) if run_stats else 0,
                    "total": total_loc // len(run_stats) if run_stats else 0,
                    "avg_per_tool_call": avg_loc_per_tool,
                },
            },
            "findings": run_stats
        }

        # Capture console output and add to summary
        logging.getLogger().removeHandler(log_capture_handler)
        summary["console_output"] = log_capture_stream.getvalue()
        log_capture_stream.close()

        base_output = "output/results_orchestrated" if self.orchestrated else "output/results"
        if not self.orchestrated:
            # Orchestrated mode already writes per-run summaries into run_NNN/
            summary_path = Path(base_output) / self.lang / "run_summary.json"
            self.ensure_directories_exist([str(summary_path.parent)])
            summary_json = json.dumps(summary, indent=2, ensure_ascii=False)
            write_file_ascii(str(summary_path), summary_json)

        # Also save run_summary into each CID output folder with matching {id}_summary.json naming
        if not self.orchestrated:
            for finding in run_stats:
                cid = finding.get('cid', '')
                if cid:
                    cid_folder = Path(base_output) / self.lang / str(cid)
                    if cid_folder.exists():
                        # Find the highest existing ID in this folder to match naming
                        existing = sorted(cid_folder.glob("*_final.json"))
                        if existing:
                            latest_id = existing[-1].stem.replace("_final", "")
                            per_cid_summary = cid_folder / f"{latest_id}_summary.json"
                            write_file_ascii(str(per_cid_summary), summary_json)
                            logger.info("Per-CID summary written to %s", per_cid_summary)

        logger.info("=" * 80)
        if not self.orchestrated:
            logger.info("RUN SUMMARY written to %s", summary_path)
        logger.info("Findings: %d | TP: %d | FP: %d | More Data: %d", len(run_stats), tp_count, fp_count, md_count)
        logger.info("Total tokens: %d | Estimated cost: $%.4f | Duration: %.1fs", total_all_tokens, total_cost, run_duration)
        logger.info("=" * 80)

if __name__ == '__main__':
    # Initialize logging
    from src.utils.logger import setup_logging
    setup_logging()
    
    # Loads configuration from .env file
    # Or use: analyzer = IssueAnalyzer(lang="c", config={...})
    analyzer = IssueAnalyzer(lang="c")
    #tracedb = r"C:\tmp\codeql-dbs\simple-cpp-db" 
    tracedb = r"C:\tmp\codeql-dbs\f20260212" 
#r"C:\code\codeQL_CoD\codeql"
    analyzer.run(tracedb)