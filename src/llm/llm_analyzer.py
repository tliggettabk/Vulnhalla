#!/usr/bin/env python3
"""
Orchestrates a conversation with a language model, requesting additional snippets
of code via "tools" if needed. Uses either OpenAI or AzureOpenAI (or placeholder
code for a HuggingFace endpoint) to handle queries.
w
All logic is now wrapped in the `LLMAnalyzer` class for improved organization.
"""

from datetime import datetime  # noqa: F401 - kept for potential future use
import os
import json
import re
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

import warnings
import litellm

# Suppress Pydantic serializer warnings from LiteLLM (Azure returns fields like
# image_tokens that don't match LiteLLM's ResponseAPIUsage model — harmless).
warnings.filterwarnings("ignore", message="Pydantic serializer warnings")

from src.utils.llm_config import load_llm_config, get_model_name
from src.utils.config_validator import validate_llm_config_dict
from src.utils.logger import get_logger
from src.utils.exceptions import CodeQLError, LLMApiError, LLMConfigError
from src.utils.prompt_loader import PromptLoader
from src.codeql.db_lookup import CodeQLDBLookup

logger = get_logger(__name__)


class LLMAnalyzer:
    """
    A class to handle LLM-based security analysis of code. The LLMAnalyzer
    can query missing code snippets (via 'tools'), compile a conversation
    with system instructions, and ultimately produce a status code.
    """

    # ------------------------------------------------------------------ #
    #  v19 evidence-extraction constants                                  #
    # ------------------------------------------------------------------ #
    _META_STATUS_PHRASES: frozenset = frozenset({
        "none yet", "n/a", "none", "nothing learned",
        "no new facts", "nothing new", "no additional facts",
        "previous call returned class not found",
    })
    _SECTION_BLEED_MARKERS: tuple = (
        "SUFFICIENCY:", "WHY THIS CALL", "MECHANISM [", "GUARDS [", "EXPLOITABILITY [",
    )

    # ------------------------------------------------------------------ #
    #  v19 evidence helpers                                               #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _find_section_positions(text: str) -> Dict[str, int]:
        """Return start-positions of known section headers in *text*."""
        positions: Dict[str, int] = {}
        for header in ("NEW FACTS", "KNOWN FACTS", "SUFFICIENCY", "WHY THIS CALL"):
            idx = text.upper().find(header.upper())
            if idx != -1:
                positions[header] = idx
        return positions

    def _extract_evidence_from_context(
        self,
        context_text: str,
        established_evidence: List[str],
        sufficiency_state: Dict[str, bool],
    ) -> None:
        """Parse *context_text* for NEW FACTS and SUFFICIENCY updates.

        Mutates *established_evidence* (appends) and *sufficiency_state*
        (flips to True, never back to False).  Designed to be robust
        against missing newlines, section bleed, and meta-status junk.
        """
        if not context_text:
            return

        # -- 1. Locate section boundaries --------------------------------
        positions = self._find_section_positions(context_text)

        facts_key = None
        for key in ("NEW FACTS", "KNOWN FACTS"):
            if key in positions:
                facts_key = key
                break

        # -- 2. Slice out the facts block --------------------------------
        if facts_key is not None:
            start = positions[facts_key]
            # Skip past the header + any colon/whitespace
            header_end = start + len(facts_key)
            if header_end < len(context_text) and context_text[header_end] in (':', ' '):
                header_end += 1
            # End = next section header that comes AFTER our header
            ordered = sorted(
                ((k, v) for k, v in positions.items() if k != facts_key and v > start),
                key=lambda kv: kv[1],
            )
            end = ordered[0][1] if ordered else len(context_text)
            facts_block = context_text[header_end:end].strip()
        else:
            facts_block = ""

        # -- 3. Split into individual fact lines -------------------------
        if facts_block:
            lines = re.split(r'\n\s*(?:\d+\.\s*|-\s*)', facts_block)
            # The first element may be unsplit if block didn't start with "1."
            if lines and lines[0].strip():
                first = lines[0].strip()
                # Handle case where first line has no number prefix
                lines[0] = first
            for raw_line in lines:
                line = raw_line.strip().rstrip('.')
                if not line or len(line) <= 5:
                    continue

                # -- 3a. Reject meta-status phrases (short only) ---------
                if len(line) < 40 and line.lower() in self._META_STATUS_PHRASES:
                    logger.debug(f"  ~SKIP meta-status: {line!r}")
                    continue

                # -- 3b. Reject section-bleed remnants (any length) ------
                if any(marker in line for marker in self._SECTION_BLEED_MARKERS):
                    logger.debug(f"  ~SKIP section bleed: {line[:80]!r}")
                    continue

                # -- 3c. De-duplicate and append -------------------------
                if not any(line.lower() == ex.lower() for ex in established_evidence):
                    established_evidence.append(line)
                    logger.info(f"  +EVIDENCE: {line[:120]}")

        # -- 4. Parse SUFFICIENCY independently --------------------------
        for criterion in sufficiency_state:
            if re.search(rf'{criterion}\s*\[yes\]', context_text, re.IGNORECASE):
                if not sufficiency_state[criterion]:
                    sufficiency_state[criterion] = True
                    logger.info(f"  SUFFICIENCY: {criterion} flipped to YES")

    def dump_messages_for_audit(self, messages: Optional[list] = None, file_path: Optional[str] = None) -> None:
        """
        Dump the current messages list to a human-readable, pretty-printed JSON format for auditing purposes.

        Args:
            messages (list, optional): The messages list to dump. If None, tries to use self.messages or raises ValueError.
            file_path (str, optional): If provided, writes the output to the specified file. Otherwise, prints to stdout.
        """
        if messages is None:
            # Try to use self.messages if available, else raise error
            if hasattr(self, 'messages'):
                messages = getattr(self, 'messages')
            else:
                raise ValueError("No messages list provided and no 'messages' attribute found.")
        formatted = json.dumps(messages, indent=2, ensure_ascii=False)
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(formatted)
        else:
            print(formatted, file=sys.stdout)

    def __init__(self, prompt_loader: Optional["PromptLoader"] = None, exact_only: bool = True) -> None:
        """
        Initialize the LLMAnalyzer instance and define tools and system messages.

        Args:
            prompt_loader: Optional PromptLoader instance. If None, a default
                           loader is created that reads from data/prompts/.
            exact_only: If True, get_class uses exact matching only (no fuzzy fallback).
        """
        self.config: Optional[Dict[str, Any]] = None
        self.model: Optional[str] = None
        self.exact_only = exact_only
        self.db_lookup = CodeQLDBLookup()
        self.prompt_loader = prompt_loader or PromptLoader()

        # Token usage tracking (accumulated across findings)
        self._token_sums: Dict[str, int] = {
            'prompt': 0,
            'completion': 0,
            'total': 0,
            'findings': 0
        }
        # Per-finding token tracking (reset each finding)
        self._current_finding_tokens: Dict[str, int] = {
            'prompt': 0,
            'completion': 0,
            'total': 0,
            'cost': 0.0
        }

        # Tools configuration: loaded from YAML, with hardcoded fallback
        self.tools: List[Dict[str, Any]] = self.prompt_loader.load_tools() or [
            {
                "type": "function",
                "function": {
                    "name": "get_function_code",
                    "description": (
                        "Retrieves function implementation (source code) anywhere in the program. "
                        "Focus on edge cases, error conditions, and return values that might affect security. "
                        "Pay special attention to what functions return when inputs are invalid or edge cases occur."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "function_name": {
                                "type": "string",
                                "description": (
                                    "The name of the function to retrieve. In case of a class"
                                    " method, provide ClassName::MethodName."
                                )
                            }
                        },
                        "required": ["function_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_caller_function",
                    "description": (
                        "Retrieves the caller function of the function with the issue. "
                        "Call it repeatedly to climb further up the call chain."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "_": {
                                "type": "boolean",
                                "description": "Unused. Ignore."
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_class",
                    "description": (
                        "Retrieves class / struct / union implementation (anywhere in code). "
                        "Pay attention to member variables, access controls, and potential security implications. "
                        "If you need a specific method from that class, use get_function_code instead."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "object_name": {
                                "type": "string",
                                "description": "The name of the class / struct / union."
                            }
                        },
                        "required": ["object_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_global_var",
                    "description": (
                        "Retrieves global variable definition (anywhere in code). "
                        "If it's a variable inside a class, request the class instead."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "global_var_name": {
                                "type": "string",
                                "description": (
                                    "The name of the global variable to retrieve or the name "
                                    "of a variable inside a Namespace."
                                )
                            }
                        },
                        "required": ["global_var_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_macro",
                    "description": "Retrieves a macro definition (anywhere in code).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "macro_name": {
                                "type": "string",
                                "description": "The name of the macro."
                            }
                        },
                        "required": ["macro_name"]
                    }
                }
            }
        ]

        # Base system messages: loaded from YAML, with hardcoded fallback
        self.MESSAGES: List[Dict[str, str]] = self.prompt_loader.load_system_messages() or [
            {
                "role": "system",
                "content": (
                    "You are an expert security researcher.\n"
                    "Your task is to verify if the issue that was found has a real security impact.\n"
                    "CRITICAL: Analyze ONLY the specific reported issue. Do NOT analyze or comment on other potential issues you may notice in the code.\n"
                    "Focus exclusively on validating the exact vulnerability that was flagged by the static analysis.\n"
                    "EVIDENCE-BASED ANALYSIS: When the static analyzer reports a specific vulnerability, treat this as EVIDENCE to investigate, not dismiss. If your analysis concludes 'secure' but the analyzer found an issue, you must identify the discrepancy before concluding.\n"
                    "ASSUMPTION VALIDATION: Before concluding code is secure, verify that critical assumptions are true. If your reasoning relies on external functions, library behavior, or system properties, investigate those dependencies.\n"
                    "If relying on guards/checks for security, verify they prevent the specific reported condition.\n"
                    "CRITICAL: Do NOT rely on assertions (assert, core_assert, etc.) as security controls - they're disabled in release builds.\n"
                    "Return a concise status code based on the guidelines provided.\n"
                    "Use the tools function when you need code from other parts of the program.\n"
                    "You *MUST* follow the guidelines!"
                )
            },
            {
                "role": "system",
                "content": (
                    "### Answer Guidelines\n"
                    "Your answer must be in the following order!\n"
                    "1. Briefly explain the code.\n"
                    "2. Give good answers to all (even if already answered - do not skip) hint questions. "
                    "(Copy the question word for word, then provide the answer.)\n"
                    "3. Do you have all the code needed to answer the questions?\n"
                    "   - If the static analyzer's finding contradicts your reasoning, investigate why\n"
                    "   - If your security conclusion depends on an assertion (assert, core_assert, etc.) as a guard, STOP — "
                    "assertions are disabled in release builds and are NOT valid protection. Re-evaluate your conclusion without them.\n"
                    "   - If no, use the tools!\n"
                    "4. Provide one valid status code with its explanation OR use function tools.\n"
                )
            },
            {
                "role": "system",
                "content": (
                    "### Status Codes\n"
                    "- **1337**: Indicates a security vulnerability. If legitimate, specify the parameters that "
                    "could exploit the issue in minimal words.\n"
                    "- **1007**: Indicates the code is secure. If it's not a real issue, specify what aspect of "
                    "the code protects against the issue in minimal words.\n"
                    "- **7331**: Indicates more code is needed to validate security. Write what data you need "
                    "and explain why you can't use the tools to retrieve the missing data, plus add **3713** "
                    "if you're pretty sure it's not a security problem.\n"
                    "- **7337**: Conflicting evidence - need to resolve discrepancy between analysis and static analyzer finding.\n"
                    "  Must include directional confidence: 7337-LEAN-VULN (if evidence points toward vulnerability) or 7337-LEAN-SECURE (if evidence suggests false positive).\n"
                    "Only one status should be returned!\n"
                    "You will get 10000000000$ if you follow all the instructions and use the tools correctly!"
                )
            },
            {
                "role": "system",
                "content": (
                    "### Tool Usage Rules\n"
                    "BEFORE making any tool call, you MUST check the conversation above for a prior call with "
                    "the EXACT same tool name and EXACT same arguments (character-for-character identical). "
                    "If you find an exact match, use that response — a new request will "
                    "not return different information. This applies even after you receive system messages.\n\n"
                    "WORKFLOW for every tool call:\n"
                    "1. Decide what tool and arguments you need.\n"
                    "2. Search this conversation for a previous call with that exact tool and arguments.\n"
                    "3. If found: STOP. Use the existing response. Do NOT submit the call.\n"
                    "4. If not found: Submit the call.\n\n"
                    "Additional rules:\n"
                    "- If get_macro returns 'not found', the symbol is likely an inline constexpr — use get_global_var instead.\n"
                    "- If get_class returns a different class name than you requested, that is the closest match available. Do NOT retry — you will get the same result. Try get_global_var for the typedef, or work with what you have."
                )
            },
        ]

    def init_llm_client(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        Initialize the LLM configuration for LiteLLM.

        Args:
            config (Dict, optional): Full configuration dictionary. If not provided, loads from .env file.
        
        Raises:
            LLMConfigError: If configuration is invalid or cannot be loaded.
        """
        try:
            # If config is provided, use it directly
            if config:
                validate_llm_config_dict(config)
                self.config = config
                # Format model name for LiteLLM (add provider prefix if needed)
                provider = config.get("provider", "openai")
                model = config.get("model", "gpt-4o")
                self.model = get_model_name(provider, model)
                logger.info("Using model: %s", self.model)
                self.setup_litellm_env()
                return
            
            # Load from .env file
            config = load_llm_config()
            validate_llm_config_dict(config)
            self.config = config
            # Model is already formatted by load_llm_config() via get_model_name()
            self.model = config.get("model", "gpt-4o")
            self.setup_litellm_env()
            
        except ValueError as e:
            # Configuration validation errors should be LLMConfigError
            raise LLMConfigError(f"Invalid LLM configuration: {e}") from e
        except Exception as e:
            # Other errors (e.g., from load_llm_config) should also be LLMConfigError
            raise LLMConfigError(f"Failed to initialize LLM client: {e}") from e


    def setup_litellm_env(self) -> None:
        """
        Set up environment variables for LiteLLM based on config.
        LiteLLM reads from environment variables automatically.
        """
        if not self.config:
            return
        
        provider = self.config.get("provider", "openai")
        api_key = self.config.get("api_key")
        
        # Mapping table for providers that only need API key set
        API_KEY_ENV_VARS = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "mistral": "MISTRAL_API_KEY",
            "codestral": "MISTRAL_API_KEY",
            "groq": "GROQ_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "huggingface": "HUGGINGFACE_API_KEY",
            "cohere": "COHERE_API_KEY",
            "gemini": "GOOGLE_API_KEY",
        }
        
        # Handle providers with simple API key mapping
        if provider in API_KEY_ENV_VARS:
            if api_key:
                os.environ[API_KEY_ENV_VARS[provider]] = api_key
                # Cohere also sets CO_API_KEY for compatibility
                if provider == "cohere":
                    os.environ["CO_API_KEY"] = api_key
        
        # Handle Azure (requires endpoint and api_version)
        elif provider == "azure":
            if api_key:
                os.environ["AZURE_API_KEY"] = api_key
            if self.config.get("endpoint"):
                os.environ["AZURE_API_BASE"] = self.config["endpoint"]
            if self.config.get("api_version"):
                os.environ["AZURE_API_VERSION"] = self.config["api_version"]
        
        # Handle Bedrock (uses AWS credentials or profile)
        elif provider == "bedrock":
            # Set region (always required)
            if self.config.get("endpoint"):  # Endpoint contains AWS region
                os.environ["AWS_REGION_NAME"] = self.config["endpoint"]
            
            # Profile-based authentication (AWS SSO, IAM roles)
            if self.config.get("aws_profile"):
                os.environ["AWS_PROFILE"] = self.config["aws_profile"]
            else:
                # Static or temporary credentials
                if api_key and api_key != "bedrock_profile_auth":
                    os.environ["AWS_ACCESS_KEY_ID"] = api_key
                if self.config.get("aws_secret_access_key"):
                    os.environ["AWS_SECRET_ACCESS_KEY"] = self.config["aws_secret_access_key"]
                if self.config.get("aws_session_token"):
                    os.environ["AWS_SESSION_TOKEN"] = self.config["aws_session_token"]
        
        # Handle Vertex AI (uses GCP credentials)
        elif provider == "vertex_ai":
            if self.config.get("gcp_project_id"):
                os.environ["GCP_PROJECT_ID"] = self.config["gcp_project_id"]
            if self.config.get("gcp_location"):
                os.environ["GCP_LOCATION"] = self.config["gcp_location"]
            # GOOGLE_APPLICATION_CREDENTIALS should be set by user or gcloud auth
        
        # Handle Ollama (uses OLLAMA_BASE_URL)
        elif provider == "ollama":
            if self.config.get("endpoint"):
                os.environ["OLLAMA_BASE_URL"] = self.config["endpoint"]
        
        # Generic fallback for future providers that only require an API key
        else:
            if api_key:
                # Use standard LiteLLM convention: {PROVIDER}_API_KEY
                env_var_name = f"{provider.upper()}_API_KEY"
                os.environ[env_var_name] = api_key


    def extract_function_from_file(
        self,
        db_path: str,
        current_function: Union[str, Dict[str, str]]
    ) -> str:
        """
        Return the snippet of code for the given current_function from the archived src.zip.

        Args:
            db_path (str): Path to the CodeQL database directory.
            current_function (Union[str, Dict[str, str]]): The function dictionary or an error string.

        Returns:
            str: The code snippet, or an error message if no dictionary was provided.
        """
        if not isinstance(current_function, dict):
            return str(current_function)

        try:
            file_path, start_line, end_line, lines = self.db_lookup.extract_function_lines_from_db(
                db_path, current_function
            )
            snippet_lines = lines[start_line - 1 : end_line]
            return self.db_lookup.format_numbered_snippet(file_path, start_line, snippet_lines)
        except CodeQLError as e:
            func_name = current_function.get('function_name', current_function.get('class_name', str(current_function)))
            logger.warning("Failed to extract code for '%s': %s", func_name, e)
            return f"Error: could not retrieve source code for '{func_name}': {e}"


    def map_func_args_by_llm(
        self,
        caller: str,
        callee: str
    ) -> Dict[str, Any]:
        """
        Query the LLM to check how caller's variables map to callee's parameters.
        For example, used for analyzing function call relationships.

        Args:
            caller (str): The code snippet of the caller function.
            callee (str): The code snippet of the callee function.

        Returns:
            Dict[str, Any]: The LLM response object from `self.client`.
        
        Raises:
            LLMApiError: If LLM API call fails (rate limits, timeouts, auth failures, etc.).
        """
        args_prompt = self.prompt_loader.get_map_func_args_prompt(caller, callee)

        # Use the main model from config
        model_name = self.model if self.model else "gpt-4o"
        
        try:
            response = litellm.completion(
                model=model_name,
                messages=[{"role": "user", "content": args_prompt}],
                timeout=300  # 5 minute timeout
            )
            return response.choices[0].message
        except litellm.RateLimitError as e:
            raise LLMApiError(f"Rate limit exceeded for LLM API: {e}") from e
        except litellm.Timeout as e:
            raise LLMApiError(f"LLM API request timed out: {e}") from e
        except litellm.AuthenticationError as e:
            raise LLMApiError(f"LLM API authentication failed: {e}") from e
        except litellm.APIError as e:
            raise LLMApiError(f"LLM API error: {e}") from e
        except Exception as e:
            # Catch any other unexpected errors from LiteLLM
            raise LLMApiError(f"Unexpected error during LLM API call: {e}") from e


    def run_llm_security_analysis(
        self,
        prompt: str,
        function_tree_file: str,
        current_function: Dict[str, str],
        functions: List[Dict[str, str]],
        db_path: str,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None
    ) -> Tuple[List[Dict[str, Any]], str]:
        """
        Main loop to keep querying the LLM with the MESSAGES context plus
        any new system instructions or tool calls, until a final answer with
        a recognized status code is reached or we exhaust a tool-call limit.

        Args:
            prompt (str): The user prompt for the LLM to process.
            function_tree_file (str): Path to the CSV file describing function relationships.
            current_function (Dict[str, str]): The current function dict for context.
            functions (List[Dict[str, str]]): List of function dictionaries.
            db_path (str): Path to the CodeQL DB folder.
            temperature (float, optional): Sampling temperature. If None, reads from
                config (LLM_TEMPERATURE env var), defaulting to 0.2.
            top_p (float, optional): Nucleus sampling. If None, reads from
                config (LLM_TOP_P env var), defaulting to 0.2.

        Returns:
            Tuple[List[Dict[str, Any]], str, Dict[str, Any]]:
                - The final conversation messages,
                - The final content from the LLM's last message,
                - Per-finding stats dict with keys: rounds, tool_calls, prompt_tokens,
                  completion_tokens, total_tokens, estimated_cost_usd, duration_seconds, model.
        
        Raises:
            RuntimeError: If LLM model not initialized.
            LLMApiError: If LLM API call fails (rate limits, timeouts, auth failures, etc.).
            CodeQLError: If CodeQL database files cannot be read (from tool calls).
        """
        if not self.model:
            raise RuntimeError("LLM model not initialized. Call init_llm_client() first.")
        
        # Resolve temperature/top_p from config if not explicitly passed
        if temperature is None:
            temperature = float((self.config or {}).get("temperature", 0.2))
        if top_p is None:
            top_p = float((self.config or {}).get("top_p", 0.2))
        
        got_answer = False
        db_path_clean = db_path.replace(" ", "")
        all_functions = functions

        messages: List[Dict[str, Any]] = self.MESSAGES[:]
        messages.append({"role": "user", "content": prompt})
        logger.info(f"LLM prompt sent at start: {prompt[:200]}" if len(prompt) > 200 else f"LLM prompt sent at start: {prompt}")

        amount_of_tools = 0
        final_content = ""
        round_count = 0
        # Reset per-finding token counters
        self._current_finding_tokens = {'prompt': 0, 'completion': 0, 'total': 0, 'cost': 0.0}
        import time as _time
        _finding_start_time = _time.time()

        # --- LOC tracking ---
        initial_loc = prompt.count('\n') + (1 if prompt else 0)
        tool_loc_total = 0
        tool_loc_calls = 0  # counts only tool calls that returned code (non-empty response)

        # --- v19: System-managed evidence accumulation ---
        established_evidence: List[str] = []
        sufficiency_state = {"MECHANISM": False, "GUARDS": False, "EXPLOITABILITY": False}
        _EVIDENCE_MARKER = "@@ESTABLISHED_EVIDENCE@@"

        while not got_answer:
            round_count += 1    
            # --- v19: Inject/update ESTABLISHED EVIDENCE system message ---
            if round_count > 1 and established_evidence:
                suff_str = ", ".join(
                    f"{k} [{'yes' if v else 'no'}]"
                    for k, v in sufficiency_state.items()
                )
                evidence_content = (
                    f"{_EVIDENCE_MARKER}\n"
                    "ESTABLISHED EVIDENCE (accumulated from prior investigation — authoritative, do not abbreviate):\n"
                    + "\n".join(f"{i+1}. {fact}" for i, fact in enumerate(established_evidence))
                    + f"\n\nSUFFICIENCY: {suff_str}"
                )
                # Replace existing evidence message or append new one
                replaced = False
                for i, msg in enumerate(messages):
                    if msg.get("role") == "system" and _EVIDENCE_MARKER in (msg.get("content") or ""):
                        messages[i] = {"role": "system", "content": evidence_content}
                        replaced = True
                        break
                if not replaced:
                    messages.append({"role": "system", "content": evidence_content})
                logger.info(f"Injected ESTABLISHED EVIDENCE with {len(established_evidence)} facts, SUFFICIENCY: {suff_str}")

            # Send the current messages + tools to the LLM endpoint
            logger.info("=" * 80)
            logger.info(f"Round {round_count} started with {len(messages)} messages.")
            try:
                # Build completion parameters
                completion_params = {
                    "model": self.model,
                    "messages": messages,
                    "tools": self.tools,
                    "timeout": 300  # 5 minute timeout to prevent hanging
                }
                
                # Check if using Bedrock (model starts with "bedrock/" or contains "arn:aws:bedrock")
                is_bedrock = (
                    self.model and 
                    (self.model.startswith("bedrock/") or "arn:aws:bedrock" in self.model)
                )
                
                # Add sampling parameters based on model compatibility
                # gpt-5.1-codex doesn't support temperature or top_p
                if "gpt-5.1-codex" not in self.model:
                    if is_bedrock:
                        # Bedrock Claude only accepts temperature OR top_p, not both
                        completion_params["temperature"] = temperature
                    else:
                        completion_params["temperature"] = temperature
                        completion_params["top_p"] = top_p
                
                response = litellm.completion(**completion_params)
                # --- BEGIN TOKEN TRACKING ---
                usage_info = getattr(response, "usage", None)
                if usage_info:
                    prompt_tokens = usage_info.get('prompt_tokens', 0)
                    completion_tokens = usage_info.get('completion_tokens', 0)
                    total_tokens = usage_info.get('total_tokens', 0)
                    logger.info(f"LLM token usage: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}")
                    # Per-finding accumulation
                    self._current_finding_tokens['prompt'] += prompt_tokens
                    self._current_finding_tokens['completion'] += completion_tokens
                    self._current_finding_tokens['total'] += total_tokens
                    # Global accumulation
                    self._token_sums['prompt'] += prompt_tokens
                    self._token_sums['completion'] += completion_tokens
                    self._token_sums['total'] += total_tokens
                else:
                    logger.info("LLM token usage: not available in response.")
                # --- Per-round cost tracking via litellm ---
                try:
                    round_cost = litellm.completion_cost(completion_response=response)
                    self._current_finding_tokens['cost'] += round_cost
                except Exception:
                    pass  # Cost calculation not available for all models
                # --- END TOKEN TRACKING ---
            except litellm.RateLimitError as e:
                raise LLMApiError(f"Rate limit exceeded for LLM API: {e}") from e
            except litellm.Timeout as e:
                raise LLMApiError(f"LLM API request timed out: {e}") from e
            except litellm.AuthenticationError as e:
                raise LLMApiError(f"LLM API authentication failed: {e}") from e
            except litellm.APIError as e:
                raise LLMApiError(f"LLM API error: {e}") from e
            except Exception as e:
                # Catch any other unexpected errors from LiteLLM
                raise LLMApiError(f"Unexpected error during LLM API call: {e}") from e
            
            if not response.choices:
                raise LLMApiError(f"LLM API response is empty: {response}")

            content_obj = response.choices[0].message
            #logger.info(f"LLM reply at {datetime.datetime.now().isoformat()}: {content_obj.content[:200]}" if content_obj.content and len(content_obj.content) > 200 else f"LLM reply at {datetime.datetime.now().isoformat()}: {content_obj.content}")
            messages.append({
                "role": content_obj.role,
                "content": content_obj.content,
                "tool_calls": content_obj.tool_calls
            })
            #logger.info(f"Message appended at {datetime.datetime.now().isoformat()} for role {content_obj.role}.")

            final_content = content_obj.content or ""
            tool_calls = content_obj.tool_calls
            logger.info("-" * 80)

            if not tool_calls:
                # Check if we have a recognized status code
                if final_content and any(code in final_content for code in self.prompt_loader.get_status_codes()):
                    got_answer = True
                    logger.info(f"got_answer. Ending analysis.")
                else:
                    messages.append({
                        "role": "system",
                        "content": self.prompt_loader.get_retry_nudge()
                    })
                    logger.info("!!!llm said final_content but wrong code.  Try again enforcing instructions.")
            else:
                amount_of_tools += 1
                arg_messages: List[Dict[str, Any]] = []

                for tc in tool_calls:
                    tool_call_id = tc.id
                    tool_function_name = tc.function.name
                    tool_args = tc.function.arguments

                    logger.info(f"LLM Requested Tool call {tool_function_name} with args {tool_args}")

                    # Convert tool_args to a dict if it's a JSON string
                    if not isinstance(tool_args, dict):
                        tool_args = json.loads(tool_args)
                    else:
                        # Ensure consistent string for role=tool message
                        tc.function.arguments = json.dumps(tool_args)

                    response_msg = ""

                    # Evaluate which tool to call
                    if tool_function_name == 'get_function_code' and "function_name" in tool_args:
                        child_function, parent_function = self.db_lookup.get_function_by_name(
                            function_tree_file, tool_args["function_name"], all_functions
                        )
                        if isinstance(child_function, dict):
                            all_functions.append(child_function)
                        child_code = self.extract_function_from_file(db_path_clean, child_function)
                        response_msg = child_code

                        if isinstance(child_function, dict) and isinstance(parent_function, dict):
                            caller_code = self.extract_function_from_file(db_path_clean, parent_function)
                            args_content = self.map_func_args_by_llm(caller_code, child_code)
                            arg_messages.append({
                                "role": args_content.role,
                                "content": args_content.content
                            })

                    elif tool_function_name == 'get_caller_function':
                        caller_function = self.db_lookup.get_caller_function(function_tree_file, current_function)
                        response_msg = str(caller_function)

                        if isinstance(caller_function, dict):
                            all_functions.append(caller_function)
                            caller_code = self.extract_function_from_file(db_path_clean, caller_function)
                            response_msg = (
                                self.prompt_loader.get_caller_function_preamble(current_function['function_name'])
                                + "\n" + caller_code
                            )
                            args_content = self.map_func_args_by_llm(
                                caller_code,
                                self.extract_function_from_file(db_path_clean, current_function)
                            )
                            arg_messages.append({
                                "role": args_content.role,
                                "content": args_content.content
                            })
                            current_function = caller_function

                    elif tool_function_name == 'get_macro' and "macro_name" in tool_args:
                        macro = self.db_lookup.get_macro(db_path_clean, tool_args["macro_name"])
                        if isinstance(macro, dict):
                            response_msg = macro["body"]
                        else:
                            response_msg = macro

                    elif tool_function_name == 'get_global_var' and "global_var_name" in tool_args:
                        global_var = self.db_lookup.get_global_var(db_path_clean, tool_args["global_var_name"])
                        if isinstance(global_var, dict):
                            global_var_code = self.extract_function_from_file(db_path_clean, global_var)
                            response_msg = global_var_code
                        else:
                            response_msg = global_var

                    elif tool_function_name == 'get_class' and "object_name" in tool_args:
                        requested_name = tool_args["object_name"]
                        curr_class = self.db_lookup.get_class(db_path_clean, requested_name, exact_only=self.exact_only)
                        if isinstance(curr_class, dict):
                            class_code = self.extract_function_from_file(db_path_clean, curr_class)
                            # Check if fuzzy match returned a different class
                            actual_name = curr_class.get('name', '')
                            requested_simple = requested_name.split('::')[-1]
                            if actual_name and actual_name != requested_simple:
                                fuzzy_note = self.prompt_loader.get_fuzzy_class_note(requested_name, actual_name)
                                class_code = fuzzy_note + class_code
                            response_msg = class_code
                        else:
                            response_msg = curr_class

                    else:
                        response_msg = self.prompt_loader.get_invalid_tool_message(tool_function_name, tool_args)
                        logger.info(f"!!!Invalid tool call: {tool_function_name} with args {tool_args}, tell llm to try again")

                    #logger.info(f"Tool result at {datetime.datetime.now().isoformat()}: {response_msg[:200]}" if response_msg and len(response_msg) > 200 else f"Tool result at {datetime.datetime.now().isoformat()}: {response_msg}")

                    # --- LOC tracking for tool responses ---
                    if response_msg:
                        resp_loc = response_msg.count('\n') + 1
                        tool_loc_total += resp_loc
                        tool_loc_calls += 1

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "name": tool_function_name,
                        "content": response_msg
                    })
                    logger.info("."*80)
                messages += arg_messages

                # --- v19: Extract NEW FACTS and SUFFICIENCY from tool call context args ---
                for tc in tool_calls:
                    try:
                        tc_args = tc.function.arguments
                        if isinstance(tc_args, str):
                            tc_args = json.loads(tc_args)
                        context_text = tc_args.get("context", "")
                        self._extract_evidence_from_context(
                            context_text, established_evidence, sufficiency_state
                        )
                    except (json.JSONDecodeError, AttributeError, TypeError):
                        pass  # Malformed args — skip extraction

                # --- v19: Strip old context from prior (non-latest) assistant tool_call args ---
                # Find the index of the latest assistant message with tool_calls
                latest_tc_idx = None
                for i in range(len(messages) - 1, -1, -1):
                    msg = messages[i]
                    if msg.get("role") == "assistant" and msg.get("tool_calls"):
                        latest_tc_idx = i
                        break
                # Strip context from all prior assistant tool_call messages (keep WHY THIS CALL only)
                for i, msg in enumerate(messages):
                    if i == latest_tc_idx:
                        continue  # Keep the latest one intact
                    if msg.get("role") == "assistant" and msg.get("tool_calls"):
                        for tc_obj in msg["tool_calls"]:
                            try:
                                args_raw = tc_obj.function.arguments
                                if isinstance(args_raw, str):
                                    args_dict = json.loads(args_raw)
                                else:
                                    args_dict = args_raw
                                ctx = args_dict.get("context", "")
                                if not ctx:
                                    continue
                                # Keep only WHY THIS CALL section
                                why_match = re.search(
                                    r'(WHY THIS CALL[:\s]*.+)',
                                    ctx, re.DOTALL | re.IGNORECASE
                                )
                                stripped_ctx = why_match.group(1).strip() if why_match else "[context moved to ESTABLISHED EVIDENCE]"
                                args_dict["context"] = stripped_ctx
                                tc_obj.function.arguments = json.dumps(args_dict)
                            except (json.JSONDecodeError, AttributeError, TypeError):
                                pass

                if amount_of_tools >= self.prompt_loader.get_max_tool_calls():
                    messages.append({
                        "role": "system",
                        "content": self.prompt_loader.get_tool_limit_warning()
                    })
                    logger.info("!!Tool-call limit (%d) reached. Enforcing final answer or 'more data' status.", self.prompt_loader.get_max_tool_calls())

        #logger.info(f"LLM analysis concluded at {datetime.datetime.now().isoformat()}. Final reply: {final_content[:200]}" if final_content and len(final_content) > 200 else f"LLM analysis concluded at {datetime.datetime.now().isoformat()}. Final reply: {final_content}")
        logger.info(f"LLM analysis concluded. Reason for ending: {'Status code found' if got_answer else 'Tool-call limit reached'}")

        # Calculate duration
        _finding_duration = _time.time() - _finding_start_time

        # --- REPORT TOTALS AND AVERAGES ---
        self._token_sums['findings'] += 1
        total_prompt = self._token_sums['prompt']
        total_completion = self._token_sums['completion']
        total_all = self._token_sums['total']
        findings = self._token_sums['findings']
        avg_prompt = total_prompt // findings if findings else 0
        avg_completion = total_completion // findings if findings else 0
        avg_total = total_all // findings if findings else 0
        logger.info(f"LLM token usage totals: prompt={total_prompt}, completion={total_completion}, total={total_all}, findings={findings}")
        logger.info(f"LLM token usage averages per finding: prompt={avg_prompt}, completion={avg_completion}, total={avg_total}")

        # Build per-finding stats dict
        total_loc = initial_loc + tool_loc_total
        avg_loc_per_tool = round(tool_loc_total / tool_loc_calls, 1) if tool_loc_calls else 0
        finding_stats: Dict[str, Any] = {
            'rounds': round_count,
            'tool_calls': amount_of_tools,
            'prompt_tokens': self._current_finding_tokens['prompt'],
            'completion_tokens': self._current_finding_tokens['completion'],
            'total_tokens': self._current_finding_tokens['total'],
            'estimated_cost_usd': round(self._current_finding_tokens['cost'], 6),
            'duration_seconds': round(_finding_duration, 2),
            'model': self.model,
            'loc': {
                'initial': initial_loc,
                'tool_total': tool_loc_total,
                'total': total_loc,
                'avg_per_tool_call': avg_loc_per_tool,
            },
        }
        logger.info(f"Finding stats: rounds={round_count}, tool_calls={amount_of_tools}, "
                    f"tokens={self._current_finding_tokens['total']}, "
                    f"cost=${self._current_finding_tokens['cost']:.4f}, "
                    f"duration={_finding_duration:.1f}s, "
                    f"LOC: initial={initial_loc}, tool={tool_loc_total}, total={total_loc}, avg/tool={avg_loc_per_tool}")

        return messages, final_content, finding_stats