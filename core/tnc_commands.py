"""
Loads TNC command definitions from JSON files in resources/tnc_commands/.
Maps TNC model names (from settings) to their JSON file, and provides
search and lookup functions.
"""

import os
import json

# Maps TNC model name (as used in settings) to JSON filename (without extension)
MODEL_FILE_MAP = {
    "Generic / TNC-2 Compatible": "generic_tnc2",
    "Kantronics KPC-3 / KPC-3+": "kantronics_kpc3",
    "Kantronics KAM / KAM+": "kantronics_kam",
    "Kantronics KAM-XL": "kantronics_kamxl",
    "AEA / Timewave PK-232": "aea_pk232",
    "AEA PK-88": "aea_pk88",
    "MFJ-1270 / MFJ-1274": "mfj_1270",
    "MFJ-1278 / MFJ-1278B": "mfj_1278",
    "SCS PTC-II / IIe / IIpro": "scs_ptc2",
    "SCS PTC-III": "scs_ptc3",
    "SCS Tracker / DSP TNC": "scs_tracker",
    "TNC-Pi": "tnc_pi",
    "Other": "other",
}

# Cached data: model_name -> parsed JSON dict
_cache = {}


def _get_commands_dir():
    """
    Returns: str - absolute path to resources/tnc_commands/ directory
    """
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "resources", "tnc_commands")


def load_commands(model_name):
    """
    Loads the command definitions for a given TNC model.

    Args:
        model_name: str - TNC model name as stored in config (e.g., "Kantronics KAM / KAM+")

    Returns: dict - parsed JSON with keys "model" and "categories",
             or empty dict if file not found
    """
    if model_name in _cache:
        return _cache[model_name]

    filename = MODEL_FILE_MAP.get(model_name, "generic_tnc2")
    filepath = os.path.join(_get_commands_dir(), f"{filename}.json")

    if not os.path.exists(filepath):
        # Fallback to generic
        filepath = os.path.join(_get_commands_dir(), "generic_tnc2.json")

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        _cache[model_name] = data
        return data
    except Exception:
        return {"model": model_name, "categories": {}}


def get_categories(model_name):
    """
    Returns the category names for a TNC model.

    Args:
        model_name: str - TNC model name

    Returns: list of str - category names (e.g., ["Connection", "Mode Switching", ...])
    """
    data = load_commands(model_name)
    return list(data.get("categories", {}).keys())


def get_commands(model_name, category):
    """
    Returns the commands in a specific category for a TNC model.

    Args:
        model_name: str - TNC model name
        category: str - category name

    Returns: list of dict - command entries, each with keys:
             cmd, type, desc, syntax/key/steps
    """
    data = load_commands(model_name)
    return data.get("categories", {}).get(category, [])


def search_commands(model_name, query):
    """
    Searches all commands for a TNC model by name or description.

    Args:
        model_name: str - TNC model name
        query: str - search text (case-insensitive, matches cmd or desc)

    Returns: list of (category: str, command: dict) tuples
    """
    data = load_commands(model_name)
    query_lower = query.lower()
    results = []
    for cat_name, commands in data.get("categories", {}).items():
        for cmd in commands:
            if (query_lower in cmd.get("cmd", "").lower()
                    or query_lower in cmd.get("desc", "").lower()
                    or query_lower in cmd.get("syntax", "").lower()):
                results.append((cat_name, cmd))
    return results


def clear_cache():
    """Clears the command cache (call after changing TNC model in settings)."""
    _cache.clear()
