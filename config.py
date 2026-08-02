import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent


def _resolve_env_path() -> Optional[Path]:
    candidates = [
        Path.cwd() / ".env",
        Path.cwd() / ".env.local",
        ROOT_DIR / ".env",
        ROOT_DIR / ".env.local",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _load_environment() -> None:
    env_path = _resolve_env_path()
    if env_path is not None:
        load_dotenv(dotenv_path=env_path, override=False)
    else:
        load_dotenv(override=False)


_load_environment()

def get_api_key():
    """Fetch OpenAI API key from environment."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in environment. Did you create a .env file?")
    return api_key
#def get_openai_key():
 #   return os.getenv("OPENAI_API_KEY")

def get_serpapi_key():
        """Return the SerpAPI key (supports both SERPAPI_API_KEY and SERPAPI_KEY).
        Priority order:
            1. SERPAPI_API_KEY
            2. SERPAPI_KEY (alternate naming)
        Returns None if neither set.
        """
        return os.getenv("SERPAPI_API_KEY") or os.getenv("SERPAPI_KEY")

def get_chroma_persist_path():
    return os.getenv("CHROMA_PERSIST_PATH", "./chroma_fcc_storage")

def get_collection_name():
    return os.getenv("CHROMA_COLLECTION_NAME", "fcc_documents")
