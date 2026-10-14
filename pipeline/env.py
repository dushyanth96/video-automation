"""Robust .env loader — resolves .env from project root explicitly.
Bare load_dotenv() relies on find_dotenv(), which fails in some shells
(e.g. folder paths with spaces), silently leaving all keys empty.
"""
import os

def load_project_env() -> str:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return ""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, ".env")
    if os.path.isfile(path):
        load_dotenv(dotenv_path=path, override=False)
        return path
    return ""
