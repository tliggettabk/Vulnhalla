"""
Prompt Loader — loads LLM prompts from YAML files under data/prompts/.

Supports an optional ``PROMPT_VERSION`` environment variable (or constructor
arg) that selects an alternate directory, e.g. ``data/prompts/v2/``.
Falls back to the hardcoded defaults baked into ``LLMAnalyzer`` when the
YAML files are missing so existing deployments keep working.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Resolve project root (two levels up from src/utils/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_PROMPTS_DIR = _PROJECT_ROOT / "data" / "prompts"


class PromptLoader:
    """Load and validate prompt configuration from YAML files."""

    def __init__(self, prompts_dir: Optional[str] = None, version: Optional[str] = None, system_messages_file: Optional[str] = None) -> None:
        """
        Args:
            prompts_dir: Explicit path to the prompts directory.  When *None*
                         the loader checks ``PROMPT_VERSION`` env-var first,
                         then falls back to ``data/prompts/``.
            version:     Sub-directory name inside ``data/prompts/`` to use
                         (e.g. ``"v2"``).  Overridden by *prompts_dir*.
            system_messages_file: Override filename for system messages YAML
                         (e.g. ``"system_messages.v12-exact-only.yaml"``).
                         Defaults to ``"system_messages.yaml"``.
        """
        if prompts_dir:
            self._dir = Path(prompts_dir)
        else:
            version = version or os.environ.get("PROMPT_VERSION", "")
            if version:
                self._dir = _DEFAULT_PROMPTS_DIR / version
            else:
                self._dir = _DEFAULT_PROMPTS_DIR

        self._system_messages_file = system_messages_file or "system_messages.yaml"
        self._cache: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_yaml(self, filename: str) -> Any:
        """Load and cache a single YAML file.  Returns *None* on any error."""
        if filename in self._cache:
            return self._cache[filename]

        path = self._dir / filename
        if not path.exists():
            logger.debug("Prompt file not found, will use hardcoded defaults: %s", path)
            self._cache[filename] = None
            return None

        try:
            with path.open("r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
            self._cache[filename] = data
            logger.debug("Loaded prompt file: %s", path)
            return data
        except Exception as exc:
            logger.warning("Failed to parse prompt file %s: %s — using defaults", path, exc)
            self._cache[filename] = None
            return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def system_messages_file(self) -> str:
        """Return the system messages filename in use."""
        return self._system_messages_file

    def load_system_messages(self) -> Optional[List[Dict[str, str]]]:
        """Return the system-message list or *None* to fall back to hardcoded."""
        data = self._load_yaml(self._system_messages_file)
        if data is None:
            return None
        if not isinstance(data, list):
            logger.warning("%s: expected a list, got %s — using defaults", self._system_messages_file, type(data).__name__)
            return None
        messages: List[Dict[str, str]] = []
        for entry in data:
            role = entry.get("role", "system")
            content = entry.get("content", "")
            if not content:
                continue
            messages.append({"role": role, "content": content})
        return messages if messages else None

    def load_tools(self) -> Optional[List[Dict[str, Any]]]:
        """Return the tools list in OpenAI function-calling format, or *None*."""
        data = self._load_yaml("tools.yaml")
        if data is None:
            return None
        if not isinstance(data, list):
            logger.warning("tools.yaml: expected a list, got %s — using defaults", type(data).__name__)
            return None

        tools: List[Dict[str, Any]] = []
        for entry in data:
            tool: Dict[str, Any] = {
                "type": "function",
                "function": {
                    "name": entry["name"],
                    "description": entry.get("description", ""),
                    "parameters": entry.get("parameters", {"type": "object", "properties": {}, "required": []}),
                },
            }
            tools.append(tool)
        return tools if tools else None

    def load_conversation_control(self) -> Optional[Dict[str, Any]]:
        """Return the conversation-control dict, or *None*."""
        data = self._load_yaml("conversation_control.yaml")
        if data is None:
            return None
        if not isinstance(data, dict):
            logger.warning("conversation_control.yaml: expected a dict, got %s — using defaults", type(data).__name__)
            return None
        return data

    # Convenience accessors with fallback defaults ---------------------------

    def get_retry_nudge(self) -> str:
        cc = self.load_conversation_control()
        if cc and "retry_nudge" in cc:
            return cc["retry_nudge"]
        return "Please follow all the instructions!"

    def get_tool_limit_warning(self) -> str:
        cc = self.load_conversation_control()
        if cc and "tool_limit_warning" in cc:
            return cc["tool_limit_warning"]
        return "You called too many tools! If you still can't give a clear answer, return the 'more data' status."

    def get_caller_function_preamble(self, function_name: str) -> str:
        cc = self.load_conversation_control()
        template = "Here is the caller function for '{function_name}':"
        if cc and "caller_function_preamble" in cc:
            template = cc["caller_function_preamble"]
        return template.format(function_name=function_name)

    def get_fuzzy_class_note(self, requested_name: str, actual_name: str) -> str:
        cc = self.load_conversation_control()
        template = (
            "\n\n[NOTE: Exact match for '{requested_name}' was not found. "
            "The above is the closest match ('{actual_name}'). "
            "'{requested_name}' may be a typedef or template alias. "
            "Do NOT retry get_class with the same name — the result will be identical. "
            "Work with the information you already have.]"
        )
        if cc and "fuzzy_class_note" in cc:
            template = "\n\n" + cc["fuzzy_class_note"]
        return template.format(requested_name=requested_name, actual_name=actual_name)

    def get_map_func_args_prompt(self, caller: str, callee: str) -> str:
        cc = self.load_conversation_control()
        template = (
            "Given caller function and callee function.\n"
            "Write only what are the names of the vars in the caller that were sent to the callee "
            "and what are their names in the callee.\n"
            "Format: caller_var (caller_name) -> callee_var (callee_name)\n\n"
            "Caller function:\n{caller}\nCallee function:\n{callee}"
        )
        if cc and "map_func_args_prompt" in cc:
            template = cc["map_func_args_prompt"]
        return template.format(caller=caller, callee=callee)

    def get_invalid_tool_message(self, tool_name: str, tool_args: Any) -> str:
        cc = self.load_conversation_control()
        template = "No matching tool '{tool_name}' or invalid args {tool_args}. Try again."
        if cc and "invalid_tool_message" in cc:
            template = cc["invalid_tool_message"]
        return template.format(tool_name=tool_name, tool_args=tool_args)

    def get_status_codes(self) -> List[str]:
        cc = self.load_conversation_control()
        if cc and "status_codes" in cc:
            return cc["status_codes"]
        return ["1337", "1007", "7331", "7337", "7337-LEAN-VULN", "7337-LEAN-SECURE", "3713"]

    def get_max_tool_calls(self) -> int:
        cc = self.load_conversation_control()
        if cc and "max_tool_calls" in cc:
            return int(cc["max_tool_calls"])
        return 10
