"""
config.py — Environment configuration and settings loader.
Reads all API keys, model names, and runtime options from environment variables.
"""

import os
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class AgentConfig:
    """Configuration for a single worker agent."""
    agent_id: str
    provider: str          # "anthropic" | "openai" | "openai_compat" | "local"
    model: str
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    max_tokens: int = 2048
    temperature: float = 0.7
    timeout: int = 60
    max_retries: int = 3


@dataclass
class ControllerConfig:
    """Configuration for the main controller LLM."""
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    max_tokens: int = 4096
    temperature: float = 0.3   # Lower temp for deterministic task decomposition
    timeout: int = 120
    max_retries: int = 3


@dataclass
class AppConfig:
    """Top-level application configuration."""
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    upload_dir: str = "./uploads"
    chunk_size: int = 3000       # characters per document chunk
    chunk_overlap: int = 200     # overlap between chunks
    max_concurrent_agents: int = 5
    controller: ControllerConfig = field(default_factory=ControllerConfig)
    agents: list[AgentConfig] = field(default_factory=list)


def load_config() -> AppConfig:
    """
    Build the full AppConfig from environment variables.

    Agent definitions are read from numbered env vars, e.g.:
        AGENT_1_ID, AGENT_1_PROVIDER, AGENT_1_MODEL, AGENT_1_BASE_URL, AGENT_1_API_KEY
        AGENT_2_ID, ...

    At least one agent must be defined; the system falls back to a single
    Anthropic agent when no AGENT_* variables are present.
    """
    controller = ControllerConfig(
        provider=os.getenv("CONTROLLER_PROVIDER", "anthropic"),
        model=os.getenv("CONTROLLER_MODEL", "claude-sonnet-4-20250514"),
        base_url=os.getenv("CONTROLLER_BASE_URL"),
        api_key=os.getenv("ANTHROPIC_API_KEY") if os.getenv("CONTROLLER_PROVIDER", "anthropic") == "anthropic"
                else os.getenv("CONTROLLER_API_KEY"),
        max_tokens=int(os.getenv("CONTROLLER_MAX_TOKENS", "4096")),
        temperature=float(os.getenv("CONTROLLER_TEMPERATURE", "0.3")),
        timeout=int(os.getenv("CONTROLLER_TIMEOUT", "120")),
        max_retries=int(os.getenv("CONTROLLER_MAX_RETRIES", "3")),
    )

    # --- Discover numbered agent configs ---
    agents: list[AgentConfig] = []
    idx = 1
    while True:
        prefix = f"AGENT_{idx}_"
        agent_id = os.getenv(f"{prefix}ID")
        if not agent_id:
            break
        provider = os.getenv(f"{prefix}PROVIDER", "anthropic")
        # Resolve API key: prefer explicit per-agent key, else shared provider key
        api_key = os.getenv(f"{prefix}API_KEY") or _default_api_key(provider)
        agents.append(AgentConfig(
            agent_id=agent_id,
            provider=provider,
            model=os.getenv(f"{prefix}MODEL", "gpt-4o-mini"),
            base_url=os.getenv(f"{prefix}BASE_URL"),
            api_key=api_key,
            max_tokens=int(os.getenv(f"{prefix}MAX_TOKENS", "2048")),
            temperature=float(os.getenv(f"{prefix}TEMPERATURE", "0.7")),
            timeout=int(os.getenv(f"{prefix}TIMEOUT", "60")),
            max_retries=int(os.getenv(f"{prefix}MAX_RETRIES", "3")),
        ))
        idx += 1

    # Fallback: one default Anthropic agent so the system boots without extra config
    if not agents:
        agents.append(AgentConfig(
            agent_id="default-agent",
            provider="anthropic",
            model=os.getenv("AGENT_MODEL", "claude-haiku-4-5-20251001"),
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            max_tokens=2048,
        ))

    return AppConfig(
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        upload_dir=os.getenv("UPLOAD_DIR", "./uploads"),
        chunk_size=int(os.getenv("CHUNK_SIZE", "3000")),
        chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "200")),
        max_concurrent_agents=int(os.getenv("MAX_CONCURRENT_AGENTS", "5")),
        controller=controller,
        agents=agents,
    )


def _default_api_key(provider: str) -> Optional[str]:
    """Return the shared API key for a given provider name."""
    mapping = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "openai_compat": "OPENAI_COMPAT_API_KEY",
        "local": None,
    }
    env_var = mapping.get(provider)
    return os.getenv(env_var) if env_var else None
