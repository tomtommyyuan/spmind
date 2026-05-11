"""
SP-Mind Configuration Management

Simple configuration class for centralizing common settings.
"""

import os
from dataclasses import dataclass


@dataclass
class SPMindConfig:
    """Central configuration for SP-Mind agent.

    All settings are optional and have sensible defaults.
    API keys are still read from environment variables.

    Usage:
        config = SPMindConfig()
        config = SPMindConfig(llm="gpt-4", timeout_seconds=1200)
        config.path = "./custom_data"
    """

    # Data and execution settings
    path: str = "./data"
    timeout_seconds: int = 1800

    # LLM settings
    llm: str = "claude-sonnet-4-20250514"
    temperature: float = 0.7

    # Tool settings
    use_tool_retriever: bool = True

    # Conversation memory settings
    memory_window_turns: int | None = 6

    # Custom model settings
    base_url: str | None = None
    api_key: str | None = None

    # LLM source (auto-detected if None)
    source: str | None = None

    def __post_init__(self):
        """Load any environment variable overrides if they exist."""
        if os.getenv("SPMIND_PATH") or os.getenv("SPMIND_DATA_PATH"):
            self.path = os.getenv("SPMIND_PATH") or os.getenv("SPMIND_DATA_PATH")
        if os.getenv("SPMIND_TIMEOUT_SECONDS"):
            self.timeout_seconds = int(os.getenv("SPMIND_TIMEOUT_SECONDS"))
        if os.getenv("SPMIND_LLM") or os.getenv("SPMIND_LLM_MODEL"):
            self.llm = os.getenv("SPMIND_LLM") or os.getenv("SPMIND_LLM_MODEL")
        if os.getenv("SPMIND_USE_TOOL_RETRIEVER"):
            self.use_tool_retriever = os.getenv("SPMIND_USE_TOOL_RETRIEVER").lower() == "true"
        if os.getenv("SPMIND_TEMPERATURE"):
            self.temperature = float(os.getenv("SPMIND_TEMPERATURE"))
        if os.getenv("SPMIND_MEMORY_WINDOW_TURNS"):
            try:
                turns = int(os.getenv("SPMIND_MEMORY_WINDOW_TURNS"))
                self.memory_window_turns = turns if turns > 0 else None
            except ValueError:
                pass
        if os.getenv("SPMIND_CUSTOM_BASE_URL"):
            self.base_url = os.getenv("SPMIND_CUSTOM_BASE_URL")
        if os.getenv("SPMIND_CUSTOM_API_KEY"):
            self.api_key = os.getenv("SPMIND_CUSTOM_API_KEY")
        if os.getenv("SPMIND_SOURCE"):
            self.source = os.getenv("SPMIND_SOURCE")

    def to_dict(self) -> dict:
        """Convert config to dictionary for easy access."""
        return {
            "path": self.path,
            "timeout_seconds": self.timeout_seconds,
            "llm": self.llm,
            "temperature": self.temperature,
            "use_tool_retriever": self.use_tool_retriever,
            "memory_window_turns": self.memory_window_turns,
            "base_url": self.base_url,
            "api_key": self.api_key,
            "source": self.source,
        }


default_config = SPMindConfig()
