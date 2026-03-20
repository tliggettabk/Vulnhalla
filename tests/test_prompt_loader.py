"""Tests for the PromptLoader and prompt externalization."""

import os
import sys
from pathlib import Path

import pytest
import yaml

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.prompt_loader import PromptLoader


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def loader():
    """PromptLoader pointing at the real data/prompts/ directory."""
    return PromptLoader()


@pytest.fixture
def empty_loader(tmp_path):
    """PromptLoader pointing at an empty directory (forces fallback defaults)."""
    return PromptLoader(prompts_dir=str(tmp_path))


# ---------------------------------------------------------------------------
# YAML files exist and parse correctly
# ---------------------------------------------------------------------------

class TestYamlFilesExist:
    """Verify that the YAML prompt files are present and well-formed."""

    PROMPTS_DIR = PROJECT_ROOT / "data" / "prompts"

    def test_system_messages_yaml_exists(self):
        assert (self.PROMPTS_DIR / "system_messages.yaml").exists()

    def test_tools_yaml_exists(self):
        assert (self.PROMPTS_DIR / "tools.yaml").exists()

    def test_conversation_control_yaml_exists(self):
        assert (self.PROMPTS_DIR / "conversation_control.yaml").exists()

    def test_system_messages_yaml_parses(self):
        with (self.PROMPTS_DIR / "system_messages.yaml").open() as f:
            data = yaml.safe_load(f)
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_tools_yaml_parses(self):
        with (self.PROMPTS_DIR / "tools.yaml").open() as f:
            data = yaml.safe_load(f)
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_conversation_control_yaml_parses(self):
        with (self.PROMPTS_DIR / "conversation_control.yaml").open() as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# PromptLoader: loading from YAML
# ---------------------------------------------------------------------------

class TestPromptLoaderFromYaml:
    """PromptLoader correctly loads and structures data from YAML."""

    def test_load_system_messages_returns_list(self, loader):
        msgs = loader.load_system_messages()
        assert msgs is not None
        assert isinstance(msgs, list)
        assert all(isinstance(m, dict) for m in msgs)
        assert all("role" in m and "content" in m for m in msgs)

    def test_system_messages_have_expected_count(self, loader):
        msgs = loader.load_system_messages()
        # Current YAML has 4 system messages
        assert len(msgs) == 4

    def test_system_messages_all_role_system(self, loader):
        msgs = loader.load_system_messages()
        for m in msgs:
            assert m["role"] == "system"

    def test_load_tools_returns_openai_format(self, loader):
        tools = loader.load_tools()
        assert tools is not None
        assert isinstance(tools, list)
        for tool in tools:
            assert tool["type"] == "function"
            assert "name" in tool["function"]
            assert "description" in tool["function"]
            assert "parameters" in tool["function"]

    def test_tools_have_expected_names(self, loader):
        tools = loader.load_tools()
        names = {t["function"]["name"] for t in tools}
        expected = {"get_function_code", "get_caller_function", "get_class", "get_global_var", "get_macro"}
        assert names == expected

    def test_load_conversation_control_returns_dict(self, loader):
        cc = loader.load_conversation_control()
        assert cc is not None
        assert isinstance(cc, dict)

    def test_conversation_control_has_required_keys(self, loader):
        cc = loader.load_conversation_control()
        required_keys = [
            "retry_nudge", "tool_limit_warning", "caller_function_preamble",
            "fuzzy_class_note", "map_func_args_prompt", "invalid_tool_message",
            "status_codes", "max_tool_calls",
        ]
        for key in required_keys:
            assert key in cc, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# PromptLoader: convenience accessors with formatting
# ---------------------------------------------------------------------------

class TestPromptLoaderAccessors:
    """Convenience methods produce correctly-formatted strings."""

    def test_get_retry_nudge(self, loader):
        result = loader.get_retry_nudge()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_tool_limit_warning(self, loader):
        result = loader.get_tool_limit_warning()
        assert "too many tools" in result.lower()

    def test_get_caller_function_preamble_formats_name(self, loader):
        result = loader.get_caller_function_preamble("myFunc")
        assert "myFunc" in result

    def test_get_fuzzy_class_note_formats_names(self, loader):
        result = loader.get_fuzzy_class_note("RequestedClass", "ActualClass")
        assert "RequestedClass" in result
        assert "ActualClass" in result

    def test_get_map_func_args_prompt_formats_code(self, loader):
        result = loader.get_map_func_args_prompt("void caller(){}", "void callee(){}")
        assert "void caller(){}" in result
        assert "void callee(){}" in result

    def test_get_invalid_tool_message_formats(self, loader):
        result = loader.get_invalid_tool_message("bad_tool", {"x": 1})
        assert "bad_tool" in result

    def test_get_status_codes_returns_list(self, loader):
        codes = loader.get_status_codes()
        assert isinstance(codes, list)
        assert "1337" in codes
        assert "1007" in codes

    def test_get_max_tool_calls_returns_int(self, loader):
        result = loader.get_max_tool_calls()
        assert isinstance(result, int)
        assert result > 0


# ---------------------------------------------------------------------------
# PromptLoader: fallback when YAML files are missing
# ---------------------------------------------------------------------------

class TestPromptLoaderFallback:
    """When YAML files are absent, hardcoded defaults are used."""

    def test_load_system_messages_returns_none(self, empty_loader):
        assert empty_loader.load_system_messages() is None

    def test_load_tools_returns_none(self, empty_loader):
        assert empty_loader.load_tools() is None

    def test_load_conversation_control_returns_none(self, empty_loader):
        assert empty_loader.load_conversation_control() is None

    def test_fallback_retry_nudge(self, empty_loader):
        assert empty_loader.get_retry_nudge() == "Please follow all the instructions!"

    def test_fallback_status_codes(self, empty_loader):
        codes = empty_loader.get_status_codes()
        assert "1337" in codes and "1007" in codes

    def test_fallback_max_tool_calls(self, empty_loader):
        assert empty_loader.get_max_tool_calls() == 10

    def test_fallback_caller_preamble(self, empty_loader):
        result = empty_loader.get_caller_function_preamble("foo")
        assert "foo" in result

    def test_fallback_fuzzy_class_note(self, empty_loader):
        result = empty_loader.get_fuzzy_class_note("A", "B")
        assert "A" in result and "B" in result


# ---------------------------------------------------------------------------
# PromptLoader: version selection
# ---------------------------------------------------------------------------

class TestPromptLoaderVersioning:
    """PROMPT_VERSION env var or constructor arg selects alternate directory."""

    def test_version_constructor_arg(self, tmp_path):
        v2_dir = tmp_path / "v2"
        v2_dir.mkdir()
        # Write a minimal system_messages.yaml with 1 message
        (v2_dir / "system_messages.yaml").write_text(
            "- role: system\n  content: v2 system prompt\n",
            encoding="utf-8",
        )
        loader = PromptLoader(prompts_dir=str(v2_dir))
        msgs = loader.load_system_messages()
        assert msgs is not None
        assert len(msgs) == 1
        assert msgs[0]["content"] == "v2 system prompt"

    def test_version_env_var(self, tmp_path, monkeypatch):
        v3_dir = tmp_path / "v3"
        v3_dir.mkdir()
        (v3_dir / "conversation_control.yaml").write_text(
            'retry_nudge: "Custom retry"\nstatus_codes:\n  - "1337"\nmax_tool_calls: 5\n',
            encoding="utf-8",
        )
        # Patch _DEFAULT_PROMPTS_DIR so the env-var based version resolves to our tmp dir
        import src.utils.prompt_loader as pl_module
        monkeypatch.setattr(pl_module, "_DEFAULT_PROMPTS_DIR", tmp_path)
        monkeypatch.setenv("PROMPT_VERSION", "v3")

        loader = PromptLoader()
        assert loader.get_retry_nudge() == "Custom retry"
        assert loader.get_max_tool_calls() == 5


# ---------------------------------------------------------------------------
# LLMAnalyzer integration: it initializes with PromptLoader
# ---------------------------------------------------------------------------

class TestLLMAnalyzerIntegration:
    """LLMAnalyzer uses PromptLoader for its prompts."""

    def test_llm_analyzer_has_prompt_loader(self):
        from src.llm.llm_analyzer import LLMAnalyzer
        analyzer = LLMAnalyzer()
        assert hasattr(analyzer, "prompt_loader")
        assert isinstance(analyzer.prompt_loader, PromptLoader)

    def test_llm_analyzer_accepts_custom_loader(self):
        from src.llm.llm_analyzer import LLMAnalyzer
        custom_loader = PromptLoader()
        analyzer = LLMAnalyzer(prompt_loader=custom_loader)
        assert analyzer.prompt_loader is custom_loader

    def test_llm_analyzer_messages_match_yaml(self):
        from src.llm.llm_analyzer import LLMAnalyzer
        analyzer = LLMAnalyzer()
        loader = PromptLoader()
        yaml_msgs = loader.load_system_messages()
        assert yaml_msgs is not None
        assert len(analyzer.MESSAGES) == len(yaml_msgs)
        for a, b in zip(analyzer.MESSAGES, yaml_msgs):
            assert a["role"] == b["role"]
            assert a["content"] == b["content"]

    def test_llm_analyzer_tools_match_yaml(self):
        from src.llm.llm_analyzer import LLMAnalyzer
        analyzer = LLMAnalyzer()
        loader = PromptLoader()
        yaml_tools = loader.load_tools()
        assert yaml_tools is not None
        assert len(analyzer.tools) == len(yaml_tools)
        for a, b in zip(analyzer.tools, yaml_tools):
            assert a["function"]["name"] == b["function"]["name"]
