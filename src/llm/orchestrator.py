#!/usr/bin/env python3
"""
Orchestrated security analysis engine.

Replaces the single-conversation loop in llm_analyzer.py with a
Plan → Investigate → Synthesize pipeline where Python controls
tool execution, deduplication, and phase sequencing.
"""

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import litellm

from src.codeql.db_lookup import CodeQLDBLookup
from src.utils.llm_config import load_llm_config, get_model_name
from src.utils.config_validator import validate_llm_config_dict
from src.utils.logger import get_logger
from src.utils.exceptions import LLMApiError, LLMConfigError
from src.utils.prompt_loader import PromptLoader

logger = get_logger(__name__)

# Path to the planner prompt YAML (relative to project root)
_PLAN_PROMPT_FILE = "orchestrator_plan.yaml"
_INVESTIGATE_PROMPT_FILE = "orchestrator_investigate.yaml"
_SYNTHESIZE_PROMPT_FILE = "orchestrator_synthesize.yaml"

# Max follow-up tool calls per lead (on top of seed tools)
_MAX_FOLLOWUP_TOOLS = 12

# Rolling budget extension: grant 4 more rounds if recent tools are productive
_FOLLOWUP_EXTENSION = 4
_FOLLOWUP_HARD_CAP = 20
_EXTENSION_THRESHOLD = 0.8   # fraction of last N tools that must have found data

# Early termination configuration - based on analysis of 149 cases
_EARLY_TERMINATION_ENABLED = True
_EARLY_TERMINATION_THRESHOLD = 6  # consecutive failures before early termination

# Shared reason field added to every tool so the model must articulate
# *why* it needs this call before making it.
_REASON_PARAM = {
    "type": "string",
    "description": (
        "One sentence: what specific evidence will this call provide "
        "that is not already in the conversation?"
    ),
}

# Native function-calling tool schemas for the investigator
_INVESTIGATOR_TOOLS: list = [
    {
        "type": "function",
        "function": {
            "name": "get_function_code",
            "description": (
                "Retrieves a function's source code from the codebase. "
                "Use Class::Method for class methods."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "function_name": {
                        "type": "string",
                        "description": "The function name, e.g. 'my_func' or 'MyClass::my_method'.",
                    },
                    "reason": _REASON_PARAM,
                },
                "required": ["function_name", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_caller_function",
            "description": (
                "Retrieves the source code of a function's caller. "
                "Pass function_name to get a specific function's caller, "
                "or omit it to get the flagged function's caller."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "function_name": {
                        "type": "string",
                        "description": "Optional: the function whose caller to retrieve.",
                    },
                    "reason": _REASON_PARAM,
                },
                "required": ["reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_class",
            "description": (
                "Retrieves class/struct/union/enum source code. "
                "If you need a specific method, use get_function_code instead."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "object_name": {
                        "type": "string",
                        "description": "The class/struct/union/enum name.",
                    },
                    "reason": _REASON_PARAM,
                },
                "required": ["object_name", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_macro_or_global",
            "description": (
                "Retrieves a macro definition or global variable. "
                "Searches macros first, then global variables."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The macro or global variable name.",
                    },
                    "reason": _REASON_PARAM,
                },
                "required": ["name", "reason"],
            },
        },
    },
]


class Orchestrator:
    """
    Plan → Investigate → Synthesize analysis engine.

    Phase 1 (PLAN):  LLM decomposes the alert into investigation leads.
    Phase 2 (INVESTIGATE): Python executes tools, focused LLM calls per lead.
    Phase 3 (SYNTHESIZE): LLM renders a verdict from all findings.
    """

    def __init__(
        self,
        prompt_loader: Optional[PromptLoader] = None,
        exact_only: bool = True,
        parallel_leads: bool = True,
    ) -> None:
        self.prompt_loader = prompt_loader or PromptLoader()
        self.exact_only = exact_only
        self.parallel_leads = parallel_leads
        self.db_lookup = CodeQLDBLookup()

        self.config: Optional[Dict[str, Any]] = None
        self.model: Optional[str] = None

        # Token tracking
        self._tokens: Dict[str, int] = {
            "prompt": 0, "completion": 0, "total": 0, "cost": 0.0,
            "llm_seconds": 0.0,
        }

        # Global tool-result cache: (tool_name, frozen_args) → response_str
        self._tool_cache: Dict[Tuple[str, str], Tuple[str, bool]] = {}

        # Current run folder (set at start of each analyze/replay call)
        self._current_run_folder: Optional[Path] = None
        self._total_leads: int = 0

        # Retry tracking
        self._last_retries: int = 0  # retries on the most recent _llm_call
        self._lead_retries: int = 0  # total retries across all calls in current lead

        # Thread-safety: lock for global token accumulation
        self._tokens_lock = threading.Lock()

        # Load system messages from YAML
        self._plan_messages = self._load_plan_prompt()
        self._investigate_messages = self._load_investigate_prompt()
        self._synthesize_messages = self._load_synthesize_prompt()

    # ------------------------------------------------------------------
    # Init / config  (mirrors LLMAnalyzer for compatibility)
    # ------------------------------------------------------------------

    def init_llm_client(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Configure the LLM model via LiteLLM, same as LLMAnalyzer."""
        try:
            if config:
                validate_llm_config_dict(config)
                self.config = config
                provider = config.get("provider", "openai")
                model = config.get("model", "gpt-4o")
                self.model = get_model_name(provider, model)
            else:
                config = load_llm_config()
                validate_llm_config_dict(config)
                self.config = config
                self.model = config.get("model", "gpt-4o")

            logger.info("Orchestrator using model: %s", self.model)
            self._setup_litellm_env()
        except ValueError as e:
            raise LLMConfigError(f"Invalid LLM configuration: {e}") from e
        except Exception as e:
            raise LLMConfigError(f"Failed to initialize LLM client: {e}") from e

    def _setup_litellm_env(self) -> None:
        """Delegate to the same env-var setup used by LLMAnalyzer."""
        import os
        if not self.config:
            return
        provider = self.config.get("provider", "openai")
        api_key = self.config.get("api_key")
        if provider == "azure":
            if api_key:
                os.environ["AZURE_API_KEY"] = api_key
            if self.config.get("endpoint"):
                os.environ["AZURE_API_BASE"] = self.config["endpoint"]
            if self.config.get("api_version"):
                os.environ["AZURE_API_VERSION"] = self.config["api_version"]
        elif api_key:
            env_map = {
                "openai": "OPENAI_API_KEY",
                "anthropic": "ANTHROPIC_API_KEY",
            }
            var = env_map.get(provider, f"{provider.upper()}_API_KEY")
            os.environ[var] = api_key

    # ------------------------------------------------------------------
    # Prompt loading
    # ------------------------------------------------------------------

    def _load_plan_prompt(self) -> List[Dict[str, str]]:
        """Load the planner system messages from orchestrator_plan.yaml."""
        plan_loader = PromptLoader(system_messages_file=_PLAN_PROMPT_FILE)
        msgs = plan_loader.load_system_messages()
        if msgs:
            return msgs
        # Fallback: minimal planner prompt
        return [{"role": "system", "content": (
            "You are an expert security researcher. Given a static analysis alert "
            "and code, return a JSON array of 3-5 investigation leads. Each lead has: "
            "question, why, tool, args. Return ONLY JSON."
        )}]

    def _load_investigate_prompt(self) -> List[Dict[str, str]]:
        """Load the investigator system messages from orchestrator_investigate.yaml."""
        inv_loader = PromptLoader(system_messages_file=_INVESTIGATE_PROMPT_FILE)
        msgs = inv_loader.load_system_messages()
        if msgs:
            return msgs
        return [{"role": "system", "content": (
            "You are a security code investigator. Answer the assigned question using "
            "the provided tool results. Respond with JSON: {answered, finding, confidence} "
            "or {need_tools: [...]} if you need more code."
        )}]

    def _load_synthesize_prompt(self) -> List[Dict[str, str]]:
        """Load the synthesizer system messages from orchestrator_synthesize.yaml."""
        syn_loader = PromptLoader(system_messages_file=_SYNTHESIZE_PROMPT_FILE)
        msgs = syn_loader.load_system_messages()
        if msgs:
            return msgs
        return [{"role": "system", "content": (
            "You are a security researcher. Given investigation findings about a "
            "static analysis issue, render a verdict with one status code: "
            "1337 (vulnerable), 1007 (secure), 7331 (need data), 7337-LEAN-VULN/SECURE."
        )}]

    # ------------------------------------------------------------------
    # LLM call helper
    # ------------------------------------------------------------------

    def _llm_call(
        self,
        messages: List[Dict[str, Any]],
        label: str = "llm_call",
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[str, Dict[str, Any], Any]:
        """
        Make a single LLM completion call.

        Returns:
            (content, call_stats, tool_calls) where call_stats has
            prompt_tokens, completion_tokens, total_tokens, cost;
            tool_calls is a list of tool-call objects or None.
        """
        if not self.model:
            raise RuntimeError("LLM model not initialized. Call init_llm_client() first.")

        _retries_this_call = 0  # local (thread-safe); mirrored to self._last_retries
        self._last_retries = 0  # kept for backward compat

        completion_params: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "timeout": 300,
            "max_completion_tokens": 16384,
        }
        if tools:
            completion_params["tools"] = tools
        # gpt-5.1-codex doesn't support temperature/top_p
        if self.model and "gpt-5.1-codex" not in self.model:
            temperature = float((self.config or {}).get("temperature", 0.2))
            top_p = float((self.config or {}).get("top_p", 0.2))
            completion_params["temperature"] = temperature
            completion_params["top_p"] = top_p

        max_retries = 6
        for attempt in range(1, max_retries + 1):
            try:
                _t0 = time.time()
                response = litellm.completion(**completion_params)
                _llm_elapsed = time.time() - _t0
                if attempt > 1:
                    logger.info("  %s succeeded on retry %d/%d", label, attempt, max_retries)
                _retries_this_call = attempt - 1
                self._last_retries = _retries_this_call
                break
            except (litellm.Timeout, litellm.RateLimitError, litellm.APIConnectionError) as e:
                _retries_this_call = attempt
                self._last_retries = _retries_this_call
                if attempt < max_retries:
                    is_rate_limit = isinstance(e, litellm.RateLimitError) or "429" in str(e)
                    wait = (10 * attempt) if is_rate_limit else (2 ** attempt)
                    logger.warning("  %s attempt %d/%d failed (%s), retrying in %ds...",
                                   label, attempt, max_retries, type(e).__name__, wait)
                    time.sleep(wait)
                else:
                    tag = "timed out" if isinstance(e, litellm.Timeout) else str(type(e).__name__)
                    raise LLMApiError(f"LLM request {tag} after {max_retries} attempts: {e}") from e
            except litellm.AuthenticationError as e:
                raise LLMApiError(f"Auth failed: {e}") from e
            except litellm.APIError as e:
                raise LLMApiError(f"LLM API error: {e}") from e
            except Exception as e:
                raise LLMApiError(f"Unexpected LLM error: {e}") from e

        if not response.choices:
            raise LLMApiError("Empty LLM response")

        # Per-call stats
        usage = getattr(response, "usage", None)
        call_stats: Dict[str, Any] = {
            "prompt_tokens": usage.get("prompt_tokens", 0) if usage else 0,
            "completion_tokens": usage.get("completion_tokens", 0) if usage else 0,
            "total_tokens": usage.get("total_tokens", 0) if usage else 0,
            "cost": 0.0,
            "llm_seconds": round(_llm_elapsed, 3),
            "retries": _retries_this_call,
        }
        try:
            call_stats["cost"] = litellm.completion_cost(completion_response=response)
        except Exception:
            pass

        # Accumulate into global totals (thread-safe)
        with self._tokens_lock:
            self._tokens["prompt"] += call_stats["prompt_tokens"]
            self._tokens["completion"] += call_stats["completion_tokens"]
            self._tokens["total"] += call_stats["total_tokens"]
            self._tokens["cost"] += call_stats["cost"]
            self._tokens["llm_seconds"] += call_stats["llm_seconds"]

        # Accumulate retries for the current lead (kept for sequential compat)
        self._lead_retries = getattr(self, '_lead_retries', 0) + _retries_this_call

        msg_obj = response.choices[0].message
        content = msg_obj.content or ""
        tool_calls = getattr(msg_obj, "tool_calls", None)
        logger.info("[%s] tokens: prompt=%s, completion=%s, tool_calls=%s",
                    label,
                    call_stats["prompt_tokens"],
                    call_stats["completion_tokens"],
                    len(tool_calls) if tool_calls else 0)
        return content, call_stats, tool_calls

    # ------------------------------------------------------------------
    # Tool execution (reuses db_lookup, same as llm_analyzer)
    # ------------------------------------------------------------------

    def execute_tool(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        function_tree_file: str,
        current_function: Dict[str, str],
        all_functions: List[Dict[str, str]],
        db_path: str,
    ) -> Tuple[str, bool]:
        """
        Execute a tool call and return (result_string, found_bool).

        Results are cached globally — duplicate calls return the cached value.
        The bool indicates whether the tool actually found the requested data
        (False for not-found, ambiguous, unknown tool, etc.).
        """
        # Strip metadata-only params from cache key (reason/context are not real args)
        clean_args = {k: v for k, v in tool_args.items() if k not in ("context", "reason")}
        cache_key = (tool_name, json.dumps(clean_args, sort_keys=True))

        if cache_key in self._tool_cache:
            logger.info("  [cache hit] %s(%s)", tool_name, clean_args)
            return self._tool_cache[cache_key]  # already a (str, bool) tuple

        logger.info("  [tool] %s(%s)", tool_name, clean_args)
        db_path_clean = db_path.replace(" ", "")
        result = ""
        found = False

        if tool_name == "get_function_code" and "function_name" in tool_args:
            # Use FunctionLookup.csv (flat name-based lookup, no caller-tree gate)
            lookup_csv = str(Path(db_path_clean) / "FunctionLookup.csv")
            fn = self.db_lookup.lookup_function(
                lookup_csv, tool_args["function_name"]
            )
            result = self._extract_code(db_path_clean, fn)
            found = isinstance(fn, dict)

            # When Class::method fails, suggest other implementations of `method`
            if not found and "::" in tool_args["function_name"]:
                parts = tool_args["function_name"].split("::")
                bare_method = parts[-1].split("(")[0].strip()
                # Use first namespace segment as hint (e.g. "Telescope" from "Telescope::Foo::Bar")
                ns_hint = parts[0].strip() if len(parts) > 2 else ""
                suggestions, total = self.db_lookup.find_method_implementations(
                    lookup_csv, bare_method, namespace_hint=ns_hint, limit=5
                )
                # Only show suggestions when they're meaningful:
                # - With a namespace hint: always show (namespace-filtered results are relevant)
                # - Without a namespace hint: only if the bare name is specific enough
                #   (≤20 total matches). Common names like Get/Set/Init (hundreds+) would
                #   be misleading noise.
                if suggestions and (ns_hint or total <= 20):
                    result += (
                        f"\n\nOther implementations of '{bare_method}' exist"
                        + (f" ({total} total)" if total > len(suggestions) else "")
                        + ": " + ", ".join(suggestions)
                        + ". If this method was declared '= 0' (pure virtual) in a "
                        "class you already inspected, the interface signature IS "
                        "your evidence — stop searching and use it. Otherwise, try "
                        "one of the concrete implementations listed above."
                    )

        elif tool_name == "get_caller_function":
            fn_name = tool_args.get("function_name")
            if fn_name:
                # Use FunctionLookup.csv to find the target, then look up
                # its full record (with caller_id) from FunctionTree.csv
                lookup_csv = str(Path(db_path_clean) / "FunctionLookup.csv")
                target_fn = self.db_lookup.lookup_function(lookup_csv, fn_name)
                if isinstance(target_fn, dict):
                    # Get the FunctionTree record so we have caller_id
                    tree_fn = self.db_lookup.get_function_by_line(
                        function_tree_file,
                        target_fn["file"].replace("\"", ""),
                        int(target_fn["start_line"]),
                    )
                    if tree_fn:
                        caller = self.db_lookup.get_caller_function(function_tree_file, tree_fn)
                    else:
                        caller = f"Function '{fn_name}' found but has no caller info."
                else:
                    caller = f"Function '{fn_name}' not found in function lookup."
            else:
                caller = self.db_lookup.get_caller_function(function_tree_file, current_function)
            if isinstance(caller, dict):
                all_functions.append(caller)
                result = self._extract_code(db_path_clean, caller)
                found = True
            else:
                result = str(caller)

        elif tool_name == "get_macro_or_global" and "name" in tool_args:
            symbol = tool_args["name"]
            macro = self.db_lookup.get_macro(db_path_clean, symbol)
            if isinstance(macro, dict):
                result = f"[macro] {macro['body']}"
                found = True
            else:
                gvar = self.db_lookup.get_global_var(db_path_clean, symbol)
                if isinstance(gvar, dict):
                    result = "[global_var] " + self._extract_code(db_path_clean, gvar)
                    found = True
                else:
                    result = f"'{symbol}' not found as macro or global variable."

        # Backward compat: accept old tool names from existing plan files
        elif tool_name == "get_macro" and "macro_name" in tool_args:
            symbol = tool_args["macro_name"]
            macro = self.db_lookup.get_macro(db_path_clean, symbol)
            if isinstance(macro, dict):
                result = f"[macro] {macro['body']}"
                found = True
            else:
                gvar = self.db_lookup.get_global_var(db_path_clean, symbol)
                if isinstance(gvar, dict):
                    result = "[global_var] " + self._extract_code(db_path_clean, gvar)
                    found = True
                else:
                    result = f"'{symbol}' not found as macro or global variable."

        elif tool_name == "get_global_var" and "global_var_name" in tool_args:
            symbol = tool_args["global_var_name"]
            gvar = self.db_lookup.get_global_var(db_path_clean, symbol)
            if isinstance(gvar, dict):
                result = "[global_var] " + self._extract_code(db_path_clean, gvar)
                found = True
            else:
                macro = self.db_lookup.get_macro(db_path_clean, symbol)
                if isinstance(macro, dict):
                    result = f"[macro] {macro['body']}"
                    found = True
                else:
                    result = f"'{symbol}' not found as macro or global variable."

        elif tool_name == "get_class" and "object_name" in tool_args:
            cls = self.db_lookup.get_class(
                db_path_clean, tool_args["object_name"], exact_only=self.exact_only
            )
            if isinstance(cls, dict):
                result = self._extract_code(db_path_clean, cls)
                # If the snippet doesn't end with }; the CodeQL range may
                # have been truncated by preprocessor conditionals.  Append
                # an explicit note so the LLM knows the definition is
                # complete and doesn't burn tool calls looking for more.
                stripped = result.rstrip()
                if stripped and not stripped.endswith("};"):
                    result += (
                        "\n[end of class definition — no additional members "
                        "exist in this class beyond what is shown above]"
                    )
                found = True
            else:
                result = str(cls)
        else:
            result = f"Unknown tool or missing args: {tool_name}({tool_args})"

        self._tool_cache[cache_key] = (result, found)
        return (result, found)

    def _extract_code(self, db_path: str, function_or_error) -> str:
        """Extract source code for a function dict, or return error string."""
        if not isinstance(function_or_error, dict):
            return str(function_or_error)
        try:
            file_path, start_line, end_line, lines = (
                self.db_lookup.extract_function_lines_from_db(db_path, function_or_error)
            )
            snippet_lines = lines[start_line - 1 : end_line]
            return self.db_lookup.format_numbered_snippet(file_path, start_line, snippet_lines)
        except Exception as e:
            name = function_or_error.get("function_name", str(function_or_error))
            return f"Error: could not retrieve source code for '{name}': {e}"

    # ==================================================================
    # PHASE 1: PLAN
    # ==================================================================

    def plan(
        self,
        prompt: str,
    ) -> List[Dict[str, Any]]:
        """
        Ask the LLM to decompose the alert into investigation leads.

        Args:
            prompt: The full user prompt (issue overview + code).

        Returns:
            List of lead dicts, each with keys:
              question, why, tool, args
        """
        messages = self._plan_messages[:] + [{"role": "user", "content": prompt}]
        raw, _plan_stats, _ = self._llm_call(messages, label="PLAN")

        # Parse JSON from the response (strip markdown fences if present)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            # Remove ```json ... ``` wrapper
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()

        try:
            leads = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("PLAN returned non-JSON: %s", raw[:300])
            # Attempt to extract JSON array from the response
            start = raw.find("[")
            end = raw.rfind("]")
            if start != -1 and end != -1:
                try:
                    leads = json.loads(raw[start : end + 1])
                except json.JSONDecodeError:
                    logger.error("Could not parse leads from PLAN response")
                    return []
            else:
                return []

        if not isinstance(leads, list):
            logger.error("PLAN returned non-list: %s", type(leads).__name__)
            return []

        # Validate and normalize leads
        valid_tools = {"get_function_code", "get_caller_function", "get_class",
                       "get_macro_or_global",
                       "get_global_var", "get_macro"}  # old names for backward compat
        validated: List[Dict[str, Any]] = []
        for i, lead in enumerate(leads):  # No cap — let the planner decide
            if not isinstance(lead, dict):
                continue

            # Normalise tools: accept both singular "tool"/"args" and plural "tools" array
            tools_raw = lead.get("tools", None)
            if tools_raw is None:
                # Legacy single-tool format
                single_tool = lead.get("tool", "")
                single_args = lead.get("args", {})
                tools_raw = [{"tool": single_tool, "args": single_args}] if single_tool else []

            if not isinstance(tools_raw, list):
                tools_raw = [tools_raw]

            # Validate each tool entry
            tool_steps: List[Dict[str, Any]] = []
            for t in tools_raw:
                if not isinstance(t, dict):
                    continue
                tname = t.get("tool", "")
                if tname not in valid_tools:
                    logger.warning("PLAN lead %d has invalid tool '%s', skipping tool", i, tname)
                    continue
                tool_steps.append({"tool": tname, "args": t.get("args", {})})

            if not tool_steps:
                logger.warning("PLAN lead %d has no valid tools, skipping lead", i)
                continue

            # Validate 'lines' — must be a list of ints
            raw_lines = lead.get("lines", [])
            if not isinstance(raw_lines, list):
                raw_lines = []
            validated_lines: List[int] = []
            for ln in raw_lines:
                try:
                    validated_lines.append(int(ln))
                except (ValueError, TypeError):
                    pass

            validated.append({
                "id": lead.get("id", str(i + 1)),
                "question": lead.get("question", ""),
                "why": lead.get("why", ""),
                "evaluate": lead.get("evaluate", ""),
                "lines": validated_lines,
                "tools": tool_steps,
            })

        logger.info("PLAN produced %d leads", len(validated))
        for lead in validated:
            tool_summary = ", ".join(f"{t['tool']}({t['args']})" for t in lead["tools"])
            logger.info("  Lead %s: %s -> %s",
                        lead["id"], lead["question"][:80], tool_summary)
        return validated

    # ==================================================================
    # PHASE 2: INVESTIGATE
    # ==================================================================

    def investigate_lead(
        self,
        lead: Dict[str, Any],
        code: str,
        function_tree_file: str,
        current_function: Dict[str, str],
        all_functions: List[Dict[str, str]],
        db_path: str,
    ) -> Dict[str, Any]:
        """
        Investigate a single lead: execute seed tools, then run a focused
        LLM conversation until the agent answers or exhausts its budget.

        Returns:
            Dict with keys: id, question, evaluate, answered, finding,
            confidence, tool_calls, tool_calls_cached, follow_up_rounds,
            tools_executed, prompt_tokens, completion_tokens, total_tokens,
            estimated_cost_usd, duration_seconds, messages
        """
        lead_start = time.time()
        lead_id = lead["id"]
        question = lead["question"]
        why = lead.get("why", "")
        evaluate = lead.get("evaluate", "")
        lines = lead.get("lines", [])
        seed_tools = lead["tools"]
        total_tool_calls = 0
        cached_tool_calls = 0
        tools_executed: List[Dict[str, Any]] = []
        lead_tokens = {"prompt": 0, "completion": 0, "total": 0, "cost": 0.0, "llm_seconds": 0.0}
        lead_retries = 0  # local retry counter (thread-safe for parallel leads)
        self._lead_retries = 0  # kept for sequential backward compat
        audit_log: List[Dict[str, Any]] = []  # collects garbage responses for audit
        # LOC tracking
        initial_loc = code.count('\n') + (1 if code else 0)
        tool_loc_total = 0
        tool_loc_calls = 0

        _TOOL_LEDGER_MARKER = "@@PRIOR_TOOL_RESULTS@@"
        tool_ledger: List[Dict[str, str]] = []  # [{tool, arg_summary, result_summary}]

        logger.info("")
        logger.info("─" * 60)
        logger.info("INVESTIGATE Lead %s/%d: %s", lead_id, self._total_leads, question[:80])
        logger.info("─" * 60)

        # --- Execute seed tools ---
        seed_results: List[Dict[str, Any]] = []
        for t in seed_tools:
            cache_key = (t["tool"], json.dumps(
                {k: v for k, v in t["args"].items() if k not in ("context", "reason")}, sort_keys=True))
            was_cached = cache_key in self._tool_cache
            _tool_t0 = time.time()
            result, result_found = self.execute_tool(
                t["tool"], t["args"],
                function_tree_file, current_function, all_functions, db_path,
            )
            _tool_elapsed = round(time.time() - _tool_t0, 4)
            seed_results.append({
                "tool": t["tool"],
                "args": t["args"],
                "result": result,
            })
            # LOC tracking for seed tool results
            result_loc = 0
            if result_found and result:
                result_loc = result.count('\n') + 1
                tool_loc_total += result_loc
                tool_loc_calls += 1
            tools_executed.append({
                "tool": t["tool"], "args": t["args"],
                "cached": was_cached, "phase": "seed",
                "found": result_found, "loc": result_loc,
                "duration_seconds": _tool_elapsed,
            })
            total_tool_calls += 1
            if was_cached:
                cached_tool_calls += 1

        # --- Build messages with native function-call history ---
        lines_str = ", ".join(str(ln) for ln in lines) if lines else "(not specified)"
        user_content = (
            f"## Flagged Code\n```\n{code}\n```\n\n"
            f"## Your Assignment\n"
            f"**QUESTION**: {question}\n"
            f"**EVALUATE**: {evaluate}\n"
            f"**LINES**: {lines_str}\n\n"
            f"Initial tool lookups have already been performed. Review the "
            f"results carefully \u2014 they may already contain the answer."
        )

        messages: List[Dict[str, Any]] = self._investigate_messages[:]
        messages.append({"role": "user", "content": user_content})

        # Synthetic assistant tool_calls for seed results
        seed_tool_calls = []
        for i, t in enumerate(seed_tools):
            seed_tool_calls.append({
                "id": f"seed_{i}",
                "type": "function",
                "function": {
                    "name": t["tool"],
                    "arguments": json.dumps(t["args"]),
                },
            })
        messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": seed_tool_calls,
        })

        # Seed tool result messages (native role:tool format)
        for i, sr in enumerate(seed_results):
            messages.append({
                "role": "tool",
                "tool_call_id": f"seed_{i}",
                "name": sr["tool"],
                "content": sr["result"],
            })

        # Build ledger entries for seed tools
        for sr in seed_results:
            clean = {k: v for k, v in sr["args"].items() if k not in ("context", "reason")}
            arg_val = next(iter(clean.values()), "") if clean else ""
            tool_ledger.append({
                "tool": sr["tool"],
                "arg_summary": f"{sr['tool']}({arg_val})",
                "result_summary": self._summarize_tool_result(sr["result"]),
            })

        # --- Conversation loop: native function calling ---
        round_count = 0
        nudge_count = 0
        _MAX_NUDGES = 1
        effective_limit = _MAX_FOLLOWUP_TOOLS
        while round_count < effective_limit:
            round_count += 1

            # --- Inject/update PRIOR TOOL RESULTS summary ---
            if tool_ledger:
                ledger_lines = []
                for idx, entry in enumerate(tool_ledger, 1):
                    ledger_lines.append(f"{idx}. {entry['arg_summary']} \u2192 {entry['result_summary']}")
                ledger_content = (
                    f"{_TOOL_LEDGER_MARKER}\n"
                    "PRIOR TOOL RESULTS (do NOT re-request these — you will get the same response):\n"
                    + "\n".join(ledger_lines)
                )
                replaced = False
                for i, msg in enumerate(messages):
                    if msg.get("role") == "system" and _TOOL_LEDGER_MARKER in (msg.get("content") or ""):
                        messages[i] = {"role": "system", "content": ledger_content}
                        replaced = True
                        break
                if not replaced:
                    # Insert after the main system message (index 1)
                    messages.insert(1, {"role": "system", "content": ledger_content})

            logger.info("Lead %s round %d/%d (messages: %d, tools so far: %d)",
                        lead_id, round_count, _MAX_FOLLOWUP_TOOLS,
                        len(messages), total_tool_calls)
            raw, call_stats, tc_list = self._llm_call(
                messages, label=f"INVESTIGATE-{lead_id}",
                tools=_INVESTIGATOR_TOOLS,
            )
            lead_tokens["prompt"] += call_stats["prompt_tokens"]
            lead_tokens["completion"] += call_stats["completion_tokens"]
            lead_tokens["total"] += call_stats["total_tokens"]
            lead_tokens["cost"] += call_stats["cost"]
            lead_tokens["llm_seconds"] += call_stats["llm_seconds"]
            lead_retries += call_stats.get("retries", 0)

            # --- Model requested more tools via native function calling ---
            if tc_list:
                logger.info("Lead %s round %d: model requested %d tools",
                            lead_id, round_count, len(tc_list))
                # Append assistant message with tool_calls
                messages.append({
                    "role": "assistant",
                    "content": raw if raw else None,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": (
                                    tc.function.arguments
                                    if isinstance(tc.function.arguments, str)
                                    else json.dumps(tc.function.arguments)
                                ),
                            },
                        }
                        for tc in tc_list
                    ],
                })
                # Execute each tool and append as role:tool
                for tc in tc_list:
                    tc_name = tc.function.name
                    tc_args_raw = tc.function.arguments
                    tc_args = (
                        json.loads(tc_args_raw)
                        if isinstance(tc_args_raw, str)
                        else tc_args_raw
                    )
                    cache_key = (tc_name, json.dumps(
                        {k: v for k, v in tc_args.items() if k not in ("context", "reason")},
                        sort_keys=True))
                    was_cached = cache_key in self._tool_cache
                    _tool_t0 = time.time()
                    result, result_found = self.execute_tool(
                        tc_name, tc_args,
                        function_tree_file, current_function, all_functions, db_path,
                    )
                    _tool_elapsed = round(time.time() - _tool_t0, 4)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc_name,
                        "content": result,
                    })
                    # LOC tracking for followup tool results
                    result_loc = 0
                    if result_found and result:
                        result_loc = result.count('\n') + 1
                        tool_loc_total += result_loc
                        tool_loc_calls += 1
                    tools_executed.append({
                        "tool": tc_name, "args": tc_args,
                        "cached": was_cached, "phase": "followup",
                        "found": result_found, "loc": result_loc,
                        "duration_seconds": _tool_elapsed,
                    })
                    total_tool_calls += 1
                    if was_cached:
                        cached_tool_calls += 1
                # Build ledger entries for follow-up tools
                for tc in tc_list:
                    tc_name = tc.function.name
                    tc_args_raw = tc.function.arguments
                    tc_parsed = json.loads(tc_args_raw) if isinstance(tc_args_raw, str) else tc_args_raw
                    clean = {k: v for k, v in tc_parsed.items() if k not in ("context", "reason")}
                    arg_val = next(iter(clean.values()), "") if clean else ""
                    # Find the matching tool result from messages (just appended above)
                    result_text = ""
                    for msg in reversed(messages):
                        if msg.get("role") == "tool" and msg.get("tool_call_id") == tc.id:
                            result_text = msg.get("content", "")
                            break
                    # Only add if not already in ledger (avoid duplicates from cache)
                    ledger_key = f"{tc_name}({arg_val})"
                    if not any(e["arg_summary"] == ledger_key for e in tool_ledger):
                        tool_ledger.append({
                            "tool": tc_name,
                            "arg_summary": ledger_key,
                            "result_summary": self._summarize_tool_result(result_text),
                        })

                # Don't count all-cached rounds against budget
                all_cached = all(
                    te["cached"] for te in tools_executed[-len(tc_list):]
                )
                if all_cached:
                    round_count -= 1
                    logger.info("Lead %s: all tools cached, not counting round", lead_id)
                # Wind-down nudge: when 80% of budget spent, tell model to wrap up
                if round_count == int(effective_limit * 0.8) and not all_cached:
                    messages.append({
                        "role": "user",
                        "content": (
                            "You are running low on tool calls. Answer the question "
                            "now with the evidence you have gathered so far. Do not "
                            "request more tools unless absolutely critical."
                        ),
                    })
                    logger.info("Lead %s: wind-down nudge injected at round %d",
                                lead_id, round_count)

                # Rolling budget extension: if at the limit but recent tools
                # are productive, grant another extension (up to hard cap).
                if round_count == effective_limit and effective_limit < _FOLLOWUP_HARD_CAP:
                    window = tools_executed[-_FOLLOWUP_EXTENSION:]
                    if window:
                        found_rate = sum(1 for t in window if t.get("found")) / len(window)
                        if found_rate >= _EXTENSION_THRESHOLD:
                            new_limit = min(effective_limit + _FOLLOWUP_EXTENSION, _FOLLOWUP_HARD_CAP)
                            logger.info(
                                "Lead %s: extending budget %d -> %d (last %d tools: %.0f%% found)",
                                lead_id, effective_limit, new_limit, len(window), found_rate * 100,
                            )
                            effective_limit = new_limit

                # Early termination: check for consecutive failures
                if _EARLY_TERMINATION_ENABLED:
                    consecutive_failures = self._count_consecutive_failures(messages)
                    if consecutive_failures >= _EARLY_TERMINATION_THRESHOLD:
                        early_term_msg = (
                            f"{consecutive_failures} consecutive failures detected - "
                            "make your decision per initial guidance (0% success rate continuing)."
                        )
                        messages.append({
                            "role": "user",
                            "content": early_term_msg
                        })
                        logger.info(
                            "Lead %s: early termination triggered at round %d (%d consecutive failures)",
                            lead_id, round_count, consecutive_failures
                        )
                        # Last chance for model to respond, then we'll exit the loop
                        raw, call_stats, tc_list = self._llm_call(
                            messages, label=f"INVESTIGATE-{lead_id}-FINAL",
                            tools=None,  # No more tools allowed
                        )
                        lead_tokens["prompt"] += call_stats["prompt_tokens"]
                        lead_tokens["completion"] += call_stats["completion_tokens"]
                        lead_tokens["total"] += call_stats["total_tokens"]
                        lead_tokens["cost"] += call_stats["cost"]
                        lead_tokens["llm_seconds"] += call_stats["llm_seconds"]
                        lead_retries += call_stats.get("retries", 0)
                        
                        # Parse the final response
                        parsed = self._parse_investigator_response(raw)
                        if parsed and parsed.get("answered"):
                            logger.info("Lead %s answered after early termination (confidence: %s)",
                                        lead_id, parsed.get("confidence", "?"))
                            messages.append({"role": "assistant", "content": raw})
                            _loc = {"initial": initial_loc, "tool_total": tool_loc_total, "total": initial_loc + tool_loc_total, "avg_per_tool_call": round(tool_loc_total / tool_loc_calls, 1) if tool_loc_calls else 0}
                            return self._build_lead_result(
                                lead_id, question, why, evaluate, lines, True,
                                self._extract_finding_text(parsed),
                                parsed.get("confidence", "medium"),
                                total_tool_calls, cached_tool_calls, round_count,
                                tools_executed, lead_tokens, lead_start, messages,
                                loc=_loc, audit_log=audit_log,
                                lead_retries=lead_retries,
                            )
                        else:
                            # Model didn't provide a clear answer even with early termination guidance
                            finding_text = self._extract_finding_text(parsed) if parsed else raw.strip()[:2000]
                            audit_log.append({"round": round_count, "type": "early_termination", "raw": raw})
                            messages.append({"role": "assistant", "content": raw})
                            _loc = {"initial": initial_loc, "tool_total": tool_loc_total, "total": initial_loc + tool_loc_total, "avg_per_tool_call": round(tool_loc_total / tool_loc_calls, 1) if tool_loc_calls else 0}
                            return self._build_lead_result(
                                lead_id, question, why, evaluate, lines, False, finding_text, "low",
                                total_tool_calls, cached_tool_calls, round_count,
                                tools_executed, lead_tokens, lead_start, messages,
                                loc=_loc, audit_log=audit_log,
                                lead_retries=lead_retries,
                            )
                
                continue  # loop for model's next response

            # --- Model responded with content (no tool_calls) ---
            parsed = self._parse_investigator_response(raw)

            if parsed is None:
                # Unparseable — treat raw text as the finding
                logger.warning("Lead %s: unparseable response, using raw text", lead_id)
                audit_log.append({"round": round_count, "type": "unparseable", "raw": raw})
                messages.append({"role": "assistant", "content": raw})
                _loc = {"initial": initial_loc, "tool_total": tool_loc_total, "total": initial_loc + tool_loc_total, "avg_per_tool_call": round(tool_loc_total / tool_loc_calls, 1) if tool_loc_calls else 0}
                return self._build_lead_result(
                    lead_id, question, why, evaluate, lines, True, raw.strip()[:2000], "low",
                    total_tool_calls, cached_tool_calls, round_count,
                    tools_executed, lead_tokens, lead_start, messages,
                    loc=_loc, audit_log=audit_log,
                    lead_retries=lead_retries,
                )

            if parsed.get("answered"):
                logger.info("Lead %s answered in round %d (confidence: %s)",
                            lead_id, round_count, parsed.get("confidence", "?"))
                messages.append({"role": "assistant", "content": raw})
                _loc = {"initial": initial_loc, "tool_total": tool_loc_total, "total": initial_loc + tool_loc_total, "avg_per_tool_call": round(tool_loc_total / tool_loc_calls, 1) if tool_loc_calls else 0}
                return self._build_lead_result(
                    lead_id, question, why, evaluate, lines, True,
                    self._extract_finding_text(parsed),
                    parsed.get("confidence", "medium"),
                    total_tool_calls, cached_tool_calls, round_count,
                    tools_executed, lead_tokens, lead_start, messages,
                    loc=_loc, audit_log=audit_log,
                    lead_retries=lead_retries,
                )

            # answered:false — nudge once to try tools before giving up
            if nudge_count < _MAX_NUDGES:
                nudge_count += 1
                logger.info("Lead %s: answered:false — nudging to try tools (attempt %d)",
                            lead_id, nudge_count)
                audit_log.append({"round": round_count, "type": "no_tools", "raw": raw})
                messages.append({"role": "assistant", "content": raw})
                messages.append({
                    "role": "user",
                    "content": (
                        "Before concluding you cannot answer, try using the "
                        "available tools. For example, if get_class failed, try "
                        "get_function_code for the specific method(s) you need."
                    ),
                })
                continue

            logger.warning("Lead %s: not answered after %d nudges", lead_id, nudge_count)
            finding_text = self._extract_finding_text(parsed) if parsed else raw.strip()[:2000]
            audit_log.append({"round": round_count, "type": "no_tools_final", "raw": raw})
            messages.append({"role": "assistant", "content": raw})
            _loc = {"initial": initial_loc, "tool_total": tool_loc_total, "total": initial_loc + tool_loc_total, "avg_per_tool_call": round(tool_loc_total / tool_loc_calls, 1) if tool_loc_calls else 0}
            return self._build_lead_result(
                lead_id, question, why, evaluate, lines, False, finding_text, "low",
                total_tool_calls, cached_tool_calls, round_count,
                tools_executed, lead_tokens, lead_start, messages,
                loc=_loc, audit_log=audit_log,
                lead_retries=lead_retries,
            )

        # Budget exhausted
        logger.warning("Lead %s: round budget exhausted (%d rounds)", lead_id, round_count)
        audit_log.append({"round": round_count, "type": "budget_exhausted", "raw": raw})
        messages.append({"role": "assistant", "content": raw})
        _loc = {"initial": initial_loc, "tool_total": tool_loc_total, "total": initial_loc + tool_loc_total, "avg_per_tool_call": round(tool_loc_total / tool_loc_calls, 1) if tool_loc_calls else 0}
        return self._build_lead_result(
            lead_id, question, why, evaluate, lines, False,
            "Investigation budget exhausted before answering.", "low",
            total_tool_calls, cached_tool_calls, round_count,
            tools_executed, lead_tokens, lead_start, messages,
            loc=_loc, audit_log=audit_log,
            lead_retries=lead_retries,
        )

    def _build_lead_result(
        self,
        lead_id: str, question: str, why: str, evaluate: str,
        lines: List[int],
        answered: bool, finding: str, confidence: str,
        tool_calls: int, tool_calls_cached: int,
        follow_up_rounds: int,
        tools_executed: List[Dict[str, Any]],
        lead_tokens: Dict[str, Any],
        lead_start: float,
        messages: List[Dict[str, str]],
        loc: Optional[Dict[str, Any]] = None,
        audit_log: Optional[List[Dict[str, Any]]] = None,
        lead_retries: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Assemble the full per-lead result dict."""
        result = {
            "id": lead_id,
            "question": question,
            "why": why,
            "evaluate": evaluate,
            "lines": lines,
            "answered": answered,
            "finding": finding,
            "confidence": confidence,
            "tool_calls": tool_calls,
            "tool_calls_cached": tool_calls_cached,
            "follow_up_rounds": follow_up_rounds,
            "tools_executed": tools_executed,
            "retries": lead_retries if lead_retries is not None else getattr(self, '_lead_retries', 0),
            "prompt_tokens": lead_tokens["prompt"],
            "completion_tokens": lead_tokens["completion"],
            "total_tokens": lead_tokens["total"],
            "estimated_cost_usd": round(lead_tokens["cost"], 4),
            "duration_seconds": round(time.time() - lead_start, 2),
            "llm_seconds": round(lead_tokens["llm_seconds"], 2),
            "model": self.model or "unknown",
            "messages": messages,
        }
        if audit_log:
            result["audit_log"] = audit_log
        if loc:
            result["loc"] = loc
        return result

    def investigate_all(
        self,
        leads: List[Dict[str, Any]],
        code: str,
        function_tree_file: str,
        current_function: Dict[str, str],
        all_functions: List[Dict[str, str]],
        db_path: str,
    ) -> List[Dict[str, Any]]:
        """Run investigate_lead for each lead, return all findings.

        When self.parallel_leads is True, leads are investigated
        concurrently using a thread pool (up to 4 workers).  The
        shared tool-result cache benefits all threads; the global
        token accumulator is protected by self._tokens_lock.

        Results are returned in the same order as the input leads
        regardless of execution mode.
        """
        self._total_leads = len(leads)

        if not self.parallel_leads or len(leads) <= 1:
            return self._investigate_all_sequential(leads, code,
                function_tree_file, current_function, all_functions, db_path)

        logger.info("Parallel lead investigation: %d leads, up to %d workers",
                     len(leads), min(len(leads), 4))
        # Pre-allocate results list to preserve lead ordering
        findings: List[Optional[Dict[str, Any]]] = [None] * len(leads)

        def _run_lead(index: int, lead: Dict[str, Any]) -> None:
            try:
                finding = self.investigate_lead(
                    lead, code,
                    function_tree_file, current_function, all_functions, db_path,
                )
            except (LLMApiError, Exception) as e:
                logger.warning("Lead %s failed: %s", lead["id"], e)
                finding = {
                    "id": lead["id"],
                    "question": lead["question"],
                    "answered": False,
                    "finding": f"Investigation failed: {e}",
                    "confidence": "none",
                    "tool_calls": 0,
                    "retries": 0,
                    "status": "failed",
                }
            findings[index] = finding
            answered = "✓" if finding.get("answered") else "✗"
            conf = finding.get("confidence", "?")
            tc = finding.get("tool_calls", 0)
            cost = finding.get("estimated_cost_usd", 0)
            logger.info("  Lead %s done: %s (%s) — %d tools, $%.4f",
                        lead["id"], answered, conf, tc, cost)
            logger.info("  → %s", finding["finding"][:120] if finding.get("finding") else "(empty)")

        with ThreadPoolExecutor(max_workers=min(len(leads), 4)) as executor:
            futures = {
                executor.submit(_run_lead, i, lead): lead
                for i, lead in enumerate(leads)
            }
            # Wait for all to complete; propagate no exceptions (handled inside _run_lead)
            for future in as_completed(futures):
                future.result()  # raises if _run_lead raised (shouldn't, we catch above)

        return findings  # type: ignore[return-value]  # all slots filled

    def _investigate_all_sequential(
        self,
        leads: List[Dict[str, Any]],
        code: str,
        function_tree_file: str,
        current_function: Dict[str, str],
        all_functions: List[Dict[str, str]],
        db_path: str,
    ) -> List[Dict[str, Any]]:
        """Sequential fallback for investigate_all."""
        findings = []
        for lead in leads:
            try:
                finding = self.investigate_lead(
                    lead, code,
                    function_tree_file, current_function, all_functions, db_path,
                )
            except (LLMApiError, Exception) as e:
                logger.warning("Lead %s failed: %s", lead["id"], e)
                finding = {
                    "id": lead["id"],
                    "question": lead["question"],
                    "answered": False,
                    "finding": f"Investigation failed: {e}",
                    "confidence": "none",
                    "tool_calls": 0,
                    "retries": getattr(self, '_lead_retries', 0),
                    "status": "failed",
                }
            findings.append(finding)
            answered = "✓" if finding.get("answered") else "✗"
            conf = finding.get("confidence", "?")
            tc = finding.get("tool_calls", 0)
            cost = finding.get("estimated_cost_usd", 0)
            logger.info("  Lead %s done: %s (%s) — %d tools, $%.4f",
                        lead["id"], answered, conf, tc, cost)
            logger.info("  → %s", finding["finding"][:120] if finding.get("finding") else "(empty)")
        return findings

    def _format_tool_results(self, results: List[Dict[str, str]]) -> str:
        """Format tool results into readable text for the LLM."""
        parts = []
        for r in results:
            parts.append(f"### {r['tool']}({r['args']})\n```\n{r['result']}\n```")
        return "\n\n".join(parts)

    @staticmethod
    def _summarize_tool_result(result: str, max_len: int = 120) -> str:
        """Create a short summary of a tool result for the ledger."""
        if not result:
            return "(empty)"
        result = result.strip()
        # "not found" results
        if "not found" in result.lower():
            return "NOT FOUND"
        # Extract the first meaningful line (skip file: header, get the code)
        lines = result.split("\n")
        # Find file:path header for context
        file_header = ""
        first_code = ""
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("file:"):
                # Extract just the filename
                path = stripped[5:].strip()
                file_header = path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
                continue
            if stripped and not first_code:
                first_code = stripped
                break
        summary = ""
        if file_header:
            summary += f"{file_header}: "
        if first_code:
            summary += first_code
        else:
            summary = result[:max_len]
        if len(summary) > max_len:
            summary = summary[:max_len - 3] + "..."
        return summary

    @staticmethod
    def _count_consecutive_failures(messages: List[Dict[str, Any]]) -> int:
        """Count consecutive tool failures from the end of the message list.
        
        Returns the number of consecutive tool calls that failed at the end 
        of the conversation. Used for early termination logic.
        """
        consecutive = 0
        # Work backwards from the end, counting tool failures
        for msg in reversed(messages):
            if msg.get("role") == "tool":
                content = msg.get("content", "").lower()
                is_failure = (
                    "not found" in content or
                    "could it be a namespace" in content or
                    "error:" in content
                )
                if is_failure:
                    consecutive += 1
                else:
                    # Found a successful tool call, stop counting
                    break
        return consecutive

    @staticmethod
    def _extract_finding_text(parsed: Dict[str, Any]) -> str:
        """Convert structured evidence+conclusion into a finding string.

        Handles both old format ({finding: str}) and new format
        ({evidence: [...], conclusion: str}).  When evidence entries are
        present, any whose 'source' field contains an assert call are
        stripped and flagged before the conclusion is assembled.
        """
        # Old format — just return the string
        if "finding" in parsed and "evidence" not in parsed:
            return parsed["finding"]

        evidence = parsed.get("evidence", [])
        conclusion = parsed.get("conclusion", parsed.get("finding", ""))

        if not evidence:
            return conclusion

        import re
        _ASSERT_RE = re.compile(
            r'\b(core_assert|core_assert_index|core_assert_always|assert)\s*\(',
            re.IGNORECASE,
        )

        kept = []
        stripped = []
        for e in evidence:
            src = e.get("source", "")
            if _ASSERT_RE.search(src):
                stripped.append(e)
                logger.warning("  ASSERT-EVIDENCE STRIPPED: line %s — %s",
                               e.get('line', '?'), src.strip())
            else:
                kept.append(e)

        parts = []
        for e in kept:
            parts.append(f"  - Line {e.get('line', '?')}: `{e.get('source', '').strip()}` — {e.get('note', '')}")
        evidence_block = "\n".join(parts) if parts else "(no non-assert evidence)"

        if stripped:
            stripped_lines = ", ".join(str(e.get('line', '?')) for e in stripped)
            evidence_block += f"\n  [REMOVED {len(stripped)} assert-only line(s): {stripped_lines}]"

        return f"{conclusion}\n\nEvidence:\n{evidence_block}"

    def _parse_investigator_response(self, raw: str) -> Optional[Dict[str, Any]]:
        """Parse investigator JSON response, handling markdown fences."""
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()

        # Try direct parse
        try:
            obj = json.loads(cleaned)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

        # Try extracting JSON object from the response
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1:
            try:
                obj = json.loads(raw[start : end + 1])
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                pass

        return None

    # ==================================================================
    # Phase 3: SYNTHESIZE
    # ==================================================================

    def synthesize(
        self,
        prompt: str,
        leads: List[Dict[str, Any]],
        findings_for_summary: List[Dict[str, Any]],
    ) -> str:
        """
        Phase 3: Combine investigation findings into a security verdict.

        Args:
            prompt: Original issue + flagged code (same as planner received).
            leads: The plan leads (for question context).
            findings_for_summary: Per-lead findings (messages stripped).

        Returns:
            The synthesizer's response text (contains a status code).
        """
        # Build the user message with all findings
        findings_block = []
        for lead, finding in zip(leads, findings_for_summary):
            conf = finding.get("confidence", "unknown")
            answered = finding.get("answered", False)
            finding_text = finding.get("finding", "(no finding)")
            status = "answered" if answered else "unanswered"
            findings_block.append(
                f"### Lead {lead['id']}: {lead['question']}\n"
                f"**Status:** {status} | **Confidence:** {conf}\n\n"
                f"{finding_text}"
            )

        user_content = (
            f"## Static Analysis Alert and Flagged Code\n\n{prompt}\n\n"
            f"## Investigation Findings\n\n"
            + "\n\n---\n\n".join(findings_block)
        )

        messages = list(self._synthesize_messages) + [
            {"role": "user", "content": user_content},
        ]

        logger.info("─" * 60)
        logger.info("PHASE 3: SYNTHESIZE")
        logger.info("─" * 60)

        raw, _synth_stats, _ = self._llm_call(messages, label="SYNTHESIZE")

        logger.info("[SYNTHESIZE] tokens: prompt=%d, completion=%d",
                     _synth_stats.get("prompt_tokens", 0),
                     _synth_stats.get("completion_tokens", 0))

        return raw

    # ==================================================================
    # Run folder management
    # ==================================================================

    def _create_run_folder(self, base_folder: str) -> Path:
        """
        Create the next run_NNN subfolder under base_folder.
        Returns the Path to the new run folder.
        """
        base = Path(base_folder)
        base.mkdir(parents=True, exist_ok=True)
        existing = sorted(base.glob("run_*"))
        if existing:
            last_num = 0
            for d in existing:
                try:
                    n = int(d.name.split("_")[1])
                    last_num = max(last_num, n)
                except (IndexError, ValueError):
                    pass
            next_num = last_num + 1
        else:
            next_num = 1
        run_folder = base / f"run_{next_num:03d}"
        run_folder.mkdir(parents=True, exist_ok=True)
        return run_folder

    def _write_json(self, path: Path, data: Any) -> None:
        """Write JSON data to a file with UTF-8 encoding."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("Wrote %s", path)

    def _next_version(self, folder: Path, prefix: str, suffix: str) -> str:
        """
        Find the next version number for a file like 2_1_v2_final.json.
        If no versions exist, returns prefix + suffix (no version tag).
        If versions exist, returns prefix + _v{N+1} + suffix.
        """
        # Check for unversioned file first
        base_name = f"{prefix}{suffix}"
        if not (folder / base_name).exists():
            return base_name
        # Find highest existing version
        import re
        pattern = re.compile(rf"^{re.escape(prefix)}_v(\d+){re.escape(suffix)}$")
        max_v = 1  # The unversioned file counts as v1
        for f in folder.iterdir():
            m = pattern.match(f.name)
            if m:
                max_v = max(max_v, int(m.group(1)))
        return f"{prefix}_v{max_v + 1}{suffix}"

    # ==================================================================
    # File output: Phase 1
    # ==================================================================

    def _write_plan_output(
        self, run_folder: Path, prompt: str, leads: List[Dict[str, Any]],
        plan_stats: Dict[str, Any], duration: float,
    ) -> None:
        """Write 1_plan_raw, 1_plan_final, 1_plan_summary."""
        # Raw: the input prompt sent to the planner
        self._write_json(run_folder / "1_plan_raw.json", {
            "prompt": prompt,
            "system_messages": self._plan_messages,
        })
        # Final: the leads
        self._write_json(run_folder / "1_plan_final.json", leads)
        # Summary
        self._write_json(run_folder / "1_plan_summary.json", {
            "leads_count": len(leads),
            "prompt_tokens": plan_stats["prompt_tokens"],
            "completion_tokens": plan_stats["completion_tokens"],
            "total_tokens": plan_stats["total_tokens"],
            "estimated_cost_usd": round(plan_stats["cost"], 4),
            "duration_seconds": round(duration, 2),
            "llm_seconds": round(plan_stats.get("llm_seconds", 0), 2),
            "model": self.model or "unknown",
        })

    # ==================================================================
    # File output: Phase 2
    # ==================================================================

    def _write_lead_output(
        self, run_folder: Path, lead_id: str, lead: Dict[str, Any],
        finding: Dict[str, Any],
    ) -> None:
        """Write 2_{lead_id}_raw, 2_{lead_id}_final, 2_{lead_id}_summary."""
        prefix = f"2_{lead_id}"

        # Raw: the lead definition + seed tool results (everything the agent saw)
        raw_name = self._next_version(run_folder, prefix + "_raw", ".json")
        # Extract tool results from messages for the raw file
        raw_data = {
            "lead": lead,
            "tools_executed": finding.get("tools_executed", []),
        }
        self._write_json(run_folder / raw_name, raw_data)

        # Final: the finding + full conversation
        final_name = self._next_version(run_folder, prefix + "_final", ".json")
        # Exclude messages from the summary-level finding dict to avoid duplication
        final_data = {
            "id": finding["id"],
            "question": finding["question"],
            "why": finding.get("why", ""),
            "evaluate": finding.get("evaluate", ""),
            "lines": finding.get("lines", []),
            "answered": finding["answered"],
            "finding": finding["finding"],
            "confidence": finding["confidence"],
            "messages": finding.get("messages", []),
        }
        self._write_json(run_folder / final_name, final_data)

        # Summary: stats
        summary_name = self._next_version(run_folder, prefix + "_summary", ".json")
        summary_data = {
            "lead_id": finding["id"],
            "question": finding["question"],
            "lines": finding.get("lines", []),
            "answered": finding["answered"],
            "confidence": finding["confidence"],
            "prompt_tokens": finding.get("prompt_tokens", 0),
            "completion_tokens": finding.get("completion_tokens", 0),
            "total_tokens": finding.get("total_tokens", 0),
            "estimated_cost_usd": finding.get("estimated_cost_usd", 0),
            "duration_seconds": finding.get("duration_seconds", 0),
            "llm_seconds": finding.get("llm_seconds", 0),
            "tool_calls": finding.get("tool_calls", 0),
            "tool_calls_cached": finding.get("tool_calls_cached", 0),
            "follow_up_rounds": finding.get("follow_up_rounds", 0),
            "tools_executed": finding.get("tools_executed", []),
            "model": finding.get("model", self.model or "unknown"),
        }
        self._write_json(run_folder / summary_name, summary_data)

        # Audit log: garbage/oversized LLM responses (separate file to keep _final clean)
        audit_log = finding.get("audit_log", [])
        if audit_log:
            audit_name = self._next_version(run_folder, prefix + "_audit", ".json")
            self._write_json(run_folder / audit_name, {
                "lead_id": finding["id"],
                "entries": audit_log,
            })

    def _write_synthesize_output(
        self, run_folder: Path, raw_response: str,
        synth_stats: Dict[str, Any],
    ) -> None:
        """Write Phase 3 output files (versioned for replay support)."""
        prefix = "3_synthesize"

        # Raw
        raw_name = self._next_version(run_folder, prefix + "_raw", ".json")
        self._write_json(run_folder / raw_name, {
            "raw_response": raw_response,
        })
        logger.info("Wrote %s", run_folder / raw_name)

        # Final (the verdict text)
        final_name = self._next_version(run_folder, prefix + "_final", ".json")
        self._write_json(run_folder / final_name, {
            "verdict": raw_response,
            **synth_stats,
        })
        logger.info("Wrote %s", run_folder / final_name)

        # Summary (stats only)
        summary_name = self._next_version(run_folder, prefix + "_summary", ".json")
        self._write_json(run_folder / summary_name, synth_stats)
        logger.info("Wrote %s", run_folder / summary_name)

    # ==================================================================
    # Public entry point
    # ==================================================================

    def analyze(
        self,
        prompt: str,
        function_tree_file: str,
        current_function: Dict[str, str],
        functions: List[Dict[str, str]],
        db_path: str,
        results_folder: str = "",
        code: str = "",
        plan_file: str = "",
        replay_lead: str = "",
        replay_synthesize: bool = False,
        plan_only: bool = False,
    ) -> Tuple[List[Dict[str, Any]], str, Dict[str, Any]]:
        """
        Run the orchestrated analysis pipeline.

        Args:
            prompt: Full prompt (issue + code) -- used by the planner.
            code: Raw source code of the flagged function(s) -- used by the
                investigator instead of the full prompt, to keep it focused.
            results_folder: Base folder for output (e.g. output/results_orchestrated/c/15518).
                If provided, creates a run_NNN subfolder and writes per-phase output.
            plan_file: Path to an existing 1_plan_final.json. If provided, skips
                Phase 1 and loads leads from this file.
            replay_lead: Lead ID to re-run (e.g. "1"). Requires plan_file.
                Loads code from 2_initial_code.json in the same run folder.
                Writes versioned output (2_1_v2_final.json etc.) — never overwrites.
            replay_synthesize: If True (with plan_file), skip Phases 1+2 and
                re-run only Phase 3 using existing findings in the run folder.

        Returns the same signature as LLMAnalyzer.run_llm_security_analysis()
        for drop-in compatibility:
          (messages, final_content, finding_stats)
        """
        start_time = time.time()
        self._tokens = {"prompt": 0, "completion": 0, "total": 0, "cost": 0.0, "llm_seconds": 0.0}
        self._tool_cache.clear()

        # --- Replay single lead mode ---
        if replay_lead and plan_file:
            return self._replay_single_lead(
                plan_file, replay_lead, function_tree_file,
                current_function, functions, db_path,
            )

        # --- Replay synthesize mode ---
        if replay_synthesize and plan_file:
            return self._replay_synthesize(plan_file, prompt)

        # Create run folder if results_folder is provided
        run_folder: Optional[Path] = None
        if results_folder:
            run_folder = self._create_run_folder(results_folder)
            logger.info("Run folder: %s", run_folder)
        self._current_run_folder = run_folder

        # --- Phase 1: PLAN ---
        if plan_file:
            logger.info("=" * 60)
            logger.info("PHASE 1: PLAN (loaded from %s)", plan_file)
            logger.info("=" * 60)
            with open(plan_file, "r", encoding="utf-8") as f:
                leads = json.load(f)
            plan_duration = 0.0
            logger.info("Loaded %d leads from plan file", len(leads))
            for lead in leads:
                tool_summary = ", ".join(
                    f"{t['tool']}({t['args']})" for t in lead.get("tools", []))
                logger.info("  Lead %s: %s -> %s",
                            lead["id"], lead["question"][:80], tool_summary)
        else:
            logger.info("=" * 60)
            logger.info("PHASE 1: PLAN")
            logger.info("=" * 60)
            plan_start = time.time()
            leads = self.plan(prompt)
            plan_duration = time.time() - plan_start

        plan_llm_seconds = self._tokens["llm_seconds"]

        if run_folder and not plan_file:
            # Get the plan stats (tokens used during plan only)
            plan_stats = {
                "prompt_tokens": self._tokens["prompt"],
                "completion_tokens": self._tokens["completion"],
                "total_tokens": self._tokens["total"],
                "cost": self._tokens["cost"],
                "llm_seconds": self._tokens["llm_seconds"],
            }
            self._write_plan_output(run_folder, prompt, leads, plan_stats, plan_duration)

        if not leads:
            logger.warning("No leads produced -- returning 7331 (more data needed)")
            final_content = "**7331** -- Planner could not decompose this finding into leads."
            return ([], final_content, self._build_stats(start_time, 0, 0))

        # --- Plan-only early exit ---
        if plan_only:
            # Save initial code + runtime context for replay so leads can
            # be run later via replay_lead without re-scanning the DB.
            investigate_code = code if code else prompt
            if run_folder:
                self._write_json(run_folder / "2_initial_code.json", {
                    "code": investigate_code,
                    "prompt": prompt,
                    "current_function": current_function,
                    "functions": functions,
                    "function_tree_file": function_tree_file,
                    "db_path": db_path,
                })
            logger.info("plan_only=True — stopping after Phase 1 (%d leads)", len(leads))
            final_content = json.dumps(leads, indent=2)
            return ([], final_content, self._build_stats(start_time, 0, 0))

        # --- Lead cap guardrail ---
        _MAX_LEADS = 8
        if len(leads) > _MAX_LEADS:
            logger.warning(
                "Planner produced %d leads (max %d) — skipping issue. "
                "Leads: %s",
                len(leads), _MAX_LEADS,
                "; ".join(f"Lead {l.get('id','?')}: {l.get('question','')[:60]}" for l in leads),
            )
            final_content = (
                f"**7331** -- Planner produced {len(leads)} leads "
                f"(max {_MAX_LEADS}). Skipped to avoid runaway cost."
            )
            return ([], final_content, self._build_stats(start_time, 0, 0))

        # --- Phase 2: INVESTIGATE ---
        logger.info("=" * 60)
        logger.info("PHASE 2: INVESTIGATE (%d leads)", len(leads))
        logger.info("=" * 60)
        investigate_start = time.time()
        _llm_before_investigate = self._tokens["llm_seconds"]
        # Pass raw code to investigators; fall back to full prompt if code not provided
        investigate_code = code if code else prompt

        # Save initial code + runtime context for replay (allows replay without issues.csv)
        if run_folder:
            self._write_json(run_folder / "2_initial_code.json", {
                "code": investigate_code,
                "prompt": prompt,
                "current_function": current_function,
                "functions": functions,
                "function_tree_file": function_tree_file,
                "db_path": db_path,
            })

        findings = self.investigate_all(
            leads, investigate_code,
            function_tree_file, current_function, functions, db_path,
        )
        investigate_duration = time.time() - investigate_start
        investigate_llm_seconds = self._tokens["llm_seconds"] - _llm_before_investigate
        total_tool_calls = sum(f.get("tool_calls", 0) for f in findings)

        # Write per-lead output
        if run_folder:
            for lead, finding in zip(leads, findings):
                self._write_lead_output(run_folder, lead["id"], lead, finding)

        # --- Phase 3: SYNTHESIZE ---
        # Strip messages from findings for the summary (they're in the _final files)
        findings_for_summary = []
        for f in findings:
            summary_f = {k: v for k, v in f.items() if k != "messages"}
            findings_for_summary.append(summary_f)

        synth_start = time.time()
        _llm_before_synth = self._tokens["llm_seconds"]
        final_content = self.synthesize(prompt, leads, findings_for_summary)
        synth_duration = time.time() - synth_start
        synth_llm_seconds = self._tokens["llm_seconds"] - _llm_before_synth

        # Write Phase 3 output
        if run_folder:
            synth_stats = {
                "prompt_tokens": self._tokens["prompt"],
                "completion_tokens": self._tokens["completion"],
                "duration_seconds": round(synth_duration, 2),
                "llm_seconds": round(synth_llm_seconds, 2),
            }
            self._write_synthesize_output(run_folder, final_content, synth_stats)

        messages = [
            {"role": "system", "content": "[Orchestrated analysis -- Plan + Investigate + Synthesize]"},
            {"role": "assistant", "content": final_content},
        ]

        duration = time.time() - start_time
        stats = self._build_stats(
            start_time, 1 + len(leads) + 1, total_tool_calls,
            plan_seconds=plan_duration,
            plan_llm_seconds=plan_llm_seconds,
            investigate_seconds=investigate_duration,
            investigate_llm_seconds=investigate_llm_seconds,
            synthesize_seconds=synth_duration,
            synthesize_llm_seconds=synth_llm_seconds,
        )

        # Write run summary
        if run_folder:
            run_summary = {
                **stats,
                "run_folder": str(run_folder),
                "leads_count": len(leads),
                "findings": findings_for_summary,
                "verdict": final_content[:500],
            }
            self._write_json(run_folder / "run_summary.json", run_summary)
            self._write_run_report(run_folder, leads, findings_for_summary, final_content, stats)
            self._write_tool_calls_csv(run_folder, findings_for_summary)

        logger.info("SYNTHESIZE complete in %.1fs | Full pipeline: %.1fs, %d tool calls",
                    synth_duration, duration, total_tool_calls)
        logger.info("  LLM: %.1fs (%.0f%%) | Plan: %.1fs (LLM %.1fs) | "
                    "Investigate: %.1fs (LLM %.1fs) | Synthesize: %.1fs (LLM %.1fs)",
                    self._tokens["llm_seconds"],
                    (self._tokens["llm_seconds"] / duration * 100) if duration > 0 else 0,
                    plan_duration, plan_llm_seconds,
                    investigate_duration, investigate_llm_seconds,
                    synth_duration, synth_llm_seconds)
        return (messages, final_content, stats)

    def _write_tool_calls_csv(
        self,
        run_folder: Path,
        findings: List[Dict[str, Any]],
    ) -> None:
        """Write a tool_calls.csv listing every tool invocation across all leads."""
        import csv as csv_mod
        csv_path = run_folder / "tool_calls.csv"
        columns = [
            "lead_id", "call_index", "tool", "first_arg", "args",
            "phase", "cached", "found", "loc",
        ]
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv_mod.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            for finding in findings:
                lead_id = finding.get("id", "")
                for idx, te in enumerate(finding.get("tools_executed", []), start=1):
                    # Flatten args to a compact string for readability
                    args_clean = {k: v for k, v in te.get("args", {}).items()
                                  if k not in ("context", "reason")}
                    args_str = ", ".join(f"{k}={v}" for k, v in args_clean.items())
                    first_val = next(iter(args_clean.values()), "") if args_clean else ""
                    writer.writerow({
                        "lead_id": lead_id,
                        "call_index": idx,
                        "tool": te.get("tool", ""),
                        "first_arg": first_val,
                        "args": args_str,
                        "phase": te.get("phase", ""),
                        "cached": te.get("cached", False),
                        "found": te.get("found", ""),
                        "loc": te.get("loc", 0),
                    })
        logger.info("Wrote %s", csv_path)

    def _write_run_report(
        self,
        run_folder: Path,
        leads: List[Dict[str, Any]],
        findings: List[Dict[str, Any]],
        final_content: str,
        stats: Dict[str, Any],
    ) -> None:
        """Write a human-readable markdown report for the run."""
        lines: List[str] = []
        lines.append(f"# Run Report — {run_folder.name}")
        lines.append("")
        lines.append(f"**Tokens**: {stats.get('total_tokens', '?'):,} "
                      f"| **Cost**: ${stats.get('estimated_cost_usd', 0):.4f} "
                      f"| **Duration**: {stats.get('duration_seconds', 0):.0f}s "
                      f"| **Tool calls**: {stats.get('tool_calls', 0)}")
        lines.append(f"**Leads**: {len(leads)} | **Model**: {stats.get('model', '?')}")
        # Aggregate LOC from all leads
        total_loc = sum(f.get("loc", {}).get("total", 0) for f in findings)
        total_tool_loc = sum(f.get("loc", {}).get("tool_total", 0) for f in findings)
        lines.append(f"**LOC analyzed**: {total_loc:,} total ({total_tool_loc:,} from tools)")
        lines.append("")

        # --- Per-lead findings ---
        lines.append("---")
        lines.append("## Lead Findings")
        lines.append("")

        for lead, finding in zip(leads, findings):
            lid = lead.get("id", "?")
            q = lead.get("question", "")
            answered = finding.get("answered", False)
            confidence = finding.get("confidence", "?")
            rounds = finding.get("follow_up_rounds", "?")
            tc = finding.get("tool_calls", 0)
            cached = finding.get("tool_calls_cached", 0)
            ftokens = finding.get("total_tokens", 0)
            fcost = finding.get("estimated_cost_usd", 0)
            fdur = finding.get("duration_seconds", 0)

            outcome = f"answered ({confidence})" if answered else "budget-exhausted"
            loc = finding.get("loc", {})
            loc_total = loc.get("total", 0)
            loc_tool = loc.get("tool_total", 0)
            loc_avg = loc.get("avg_per_tool_call", 0)
            lines.append(f"### Lead {lid}")
            lines.append(f"**Question**: {q}")
            lines.append(f"**Rounds**: {rounds} | **Tools**: {tc} ({cached} cached) "
                          f"| **Tokens**: {ftokens:,} | **Cost**: ${fcost:.4f} "
                          f"| **Duration**: {fdur:.0f}s | **Outcome**: {outcome}")
            lines.append(f"**LOC**: {loc_total:,} total ({loc_tool:,} from tools, "
                          f"avg {loc_avg:.0f}/call)")
            lines.append("")

            finding_text = finding.get("finding", "(no finding)")
            lines.append(f"> {finding_text}")
            lines.append("")

        # --- Synthesize verdict ---
        lines.append("---")
        lines.append("## Synthesize Verdict")
        lines.append("")
        lines.append(final_content)
        lines.append("")

        report_path = run_folder / "run_report.md"
        report_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Wrote %s", report_path)

    def _build_stats(
        self, start_time: float, rounds: int, tool_calls: int,
        plan_seconds: float = 0.0, plan_llm_seconds: float = 0.0,
        investigate_seconds: float = 0.0, investigate_llm_seconds: float = 0.0,
        synthesize_seconds: float = 0.0, synthesize_llm_seconds: float = 0.0,
    ) -> Dict[str, Any]:
        """Build finding_stats dict matching LLMAnalyzer's format."""
        duration = time.time() - start_time
        return {
            "rounds": rounds,
            "tool_calls": tool_calls,
            "prompt_tokens": self._tokens["prompt"],
            "completion_tokens": self._tokens["completion"],
            "total_tokens": self._tokens["total"],
            "estimated_cost_usd": round(self._tokens["cost"], 4),
            "duration_seconds": round(duration, 2),
            "llm_seconds": round(self._tokens["llm_seconds"], 2),
            "plan_seconds": round(plan_seconds, 2),
            "plan_llm_seconds": round(plan_llm_seconds, 2),
            "investigate_seconds": round(investigate_seconds, 2),
            "investigate_llm_seconds": round(investigate_llm_seconds, 2),
            "synthesize_seconds": round(synthesize_seconds, 2),
            "synthesize_llm_seconds": round(synthesize_llm_seconds, 2),
            "model": self.model or "unknown",
            "engine": "orchestrator",
            "run_folder": str(self._current_run_folder) if self._current_run_folder else "",
        }

    def _replay_single_lead(
        self,
        plan_file: str,
        lead_id: str,
        function_tree_file: str,
        current_function: Dict[str, str],
        functions: List[Dict[str, str]],
        db_path: str,
    ) -> Tuple[List[Dict[str, Any]], str, Dict[str, Any]]:
        """
        Re-run a single lead from an existing run folder.

        Loads leads from plan_file, code from 2_initial_code.json in the
        same directory. Writes versioned output so nothing is overwritten.
        """
        start_time = time.time()
        self._tokens = {"prompt": 0, "completion": 0, "total": 0, "cost": 0.0, "llm_seconds": 0.0}
        self._tool_cache.clear()

        run_folder = Path(plan_file).parent
        self._current_run_folder = run_folder
        logger.info("=" * 60)
        logger.info("REPLAY Lead %s in %s", lead_id, run_folder)
        logger.info("=" * 60)

        # Load leads
        with open(plan_file, "r", encoding="utf-8") as f:
            leads = json.load(f)

        # Find the target lead
        target_lead = None
        for lead in leads:
            if str(lead["id"]) == str(lead_id):
                target_lead = lead
                break
        if target_lead is None:
            raise ValueError(f"Lead '{lead_id}' not found in {plan_file}. "
                             f"Available: {[l['id'] for l in leads]}")

        # Load code and runtime context from stored file
        code_file = run_folder / "2_initial_code.json"
        if not code_file.exists():
            raise FileNotFoundError(
                f"{code_file} not found. This run predates the replay feature — "
                "re-run the full pipeline once to generate it."
            )
        with open(code_file, "r", encoding="utf-8") as f:
            code_data = json.load(f)
        investigate_code = code_data["code"]

        # Use stored runtime context if caller didn't provide real values
        if "db_path" in code_data:
            if not function_tree_file:
                function_tree_file = code_data["function_tree_file"]
            if not current_function:
                current_function = code_data["current_function"]
            if not functions or functions == [current_function]:
                functions = code_data.get("functions", [current_function])
            if not db_path:
                db_path = code_data["db_path"]

        logger.info("Lead %s: %s", target_lead["id"], target_lead["question"][:80])
        tool_summary = ", ".join(
            f"{t['tool']}({t['args']})" for t in target_lead.get("tools", []))
        logger.info("  Tools: %s", tool_summary)

        # Run the single lead
        self._total_leads = len(leads)
        finding = self.investigate_lead(
            target_lead, investigate_code,
            function_tree_file, current_function, functions, db_path,
        )

        # Write versioned output (never overwrites)
        self._write_lead_output(run_folder, target_lead["id"], target_lead, finding)

        # Build return values
        finding_summary = {k: v for k, v in finding.items() if k != "messages"}
        final_content = (
            f"REPLAY Lead {lead_id}:\n\n"
            f"{json.dumps(finding_summary, indent=2)}"
        )
        messages = [
            {"role": "system", "content": f"[Orchestrated replay -- Lead {lead_id}]"},
            {"role": "assistant", "content": final_content},
        ]
        stats = self._build_stats(start_time, 1, finding.get("tool_calls", 0))
        stats["findings"] = [finding_summary]

        # Write tool_calls.csv for this replay
        self._write_tool_calls_csv(run_folder, [finding_summary])

        logger.info("Replay complete in %.1fs", time.time() - start_time)
        return (messages, final_content, stats)

    def _replay_synthesize(
        self,
        plan_file: str,
        prompt: str,
    ) -> Tuple[List[Dict[str, Any]], str, Dict[str, Any]]:
        """
        Re-run only Phase 3 (SYNTHESIZE) from an existing run folder.

        Loads leads from plan_file, findings from 2_{N}_final.json files.
        Writes versioned Phase 3 output.
        """
        start_time = time.time()
        run_folder = Path(plan_file).parent
        self._current_run_folder = run_folder
        logger.info("=" * 60)
        logger.info("REPLAY SYNTHESIZE in %s", run_folder)
        logger.info("=" * 60)

        # Load leads
        with open(plan_file, "r", encoding="utf-8") as f:
            leads = json.load(f)
        logger.info("Loaded %d leads from plan", len(leads))

        # Load findings from 2_{N}_final.json (prefer latest versioned replay if available)
        findings_for_summary = []
        for lead in leads:
            lid = lead["id"]
            # Find the highest-versioned final file for this lead
            final_path = run_folder / f"2_{lid}_final.json"
            # Check for versioned files (2_{lid}_final_v2.json, _v3, etc.)
            max_v = 0
            for candidate in run_folder.glob(f"2_{lid}_final_v*.json"):
                # Extract version number from filename like 2_4_final_v2.json
                stem = candidate.stem  # e.g. "2_4_final_v2"
                v_part = stem.rsplit("_v", 1)
                if len(v_part) == 2:
                    try:
                        v = int(v_part[1])
                        if v > max_v:
                            max_v = v
                            final_path = candidate
                    except ValueError:
                        pass
            if not final_path.exists():
                raise FileNotFoundError(
                    f"{final_path} not found. Run Phases 1+2 first."
                )
            with open(final_path, "r", encoding="utf-8") as f:
                finding_data = json.load(f)
            # Strip messages to keep context small
            summary = {k: v for k, v in finding_data.items() if k != "messages"}
            findings_for_summary.append(summary)
            conf = summary.get("confidence", "?")
            logger.info("  Lead %s: %s (confidence: %s)",
                        lid, summary.get("finding", "")[:80], conf)

        # Run Phase 3
        final_content = self.synthesize(prompt, leads, findings_for_summary)

        # Write versioned output
        synth_stats = {
            "prompt_tokens": self._tokens["prompt"],
            "completion_tokens": self._tokens["completion"],
            "duration_seconds": round(time.time() - start_time, 2),
            "llm_seconds": round(self._tokens["llm_seconds"], 2),
        }
        self._write_synthesize_output(run_folder, final_content, synth_stats)

        messages = [
            {"role": "system", "content": "[Orchestrated replay -- Synthesize]"},
            {"role": "assistant", "content": final_content},
        ]
        stats = self._build_stats(start_time, 1, 0)

        logger.info("Synthesize replay complete in %.1fs", time.time() - start_time)
        return (messages, final_content, stats)

    # Alias so vulnhalla.py call-site works without changes
    run_llm_security_analysis = analyze
