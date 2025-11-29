"""
yaml-diff: A minimal CLI tool for semantic YAML comparison.

Compares two YAML files semantically — ignoring key ordering, comments, and
non-significant formatting — and computes a meaningful diff showing keys added,
removed, or changed, including nested diffs in maps, lists, and primitives.

Outputs either human-readable unified diff (colorized) or JSON-patch format.

Usage:
    yaml-diff file1.yaml file2.yaml          # Human-readable diff
    yaml-diff file1.yaml file2.yaml -j       # JSON-patch output
    yaml-diff - file2.yaml < file1.yaml      # Read first file from stdin

Exit codes:
    0 - Files are identical
    1 - Files differ
    2 - Error (parse failure, file not found, invalid args)
"""

import sys
import json
import argparse
from dataclasses import dataclass
from typing import Any, List, Optional

import yaml


class YamlDiffError(Exception):
    """Custom exception for yaml-diff specific errors."""
    pass


@dataclass
class DiffOp:
    """Represents a single diff operation."""
    op: str  # 'add', 'remove', 'replace'
    path: List[str]  # JSON pointer path segments
    old_value: Any = None  # Previous value (for remove/replace)
    new_value: Any = None  # New value (for add/replace)


def check_unsupported_features(content: str, source_name: str) -> None:
    """
    Check for unsupported YAML features before parsing.
    
    Args:
        content: Raw YAML content string
        source_name: Name of the source for error messages
        
    Raises:
        YamlDiffError: If anchors, aliases, or custom tags are detected
    """
    import re
    
    # Check for anchors (&name) - but not & in strings
    # Look for & followed by word characters at start of value position
    if re.search(r'(?:^|[\s\[\{,])&\w+', content, re.MULTILINE):
        raise YamlDiffError(
            f"Anchors are not supported: {source_name}\n"
            "  yaml-diff does not support YAML anchors (&) and aliases (*)"
        )
    
    # Check for aliases (*name) - but not * in strings
    if re.search(r'(?:^|[\s\[\{,])\*\w+', content, re.MULTILINE):
        raise YamlDiffError(
            f"Aliases are not supported: {source_name}\n"
            "  yaml-diff does not support YAML anchors (&) and aliases (*)"
        )
    
    # Check for custom tags (!tag) - but not !! (standard tags are ok)
    # Custom tags start with single ! followed by non-! character
    if re.search(r'(?:^|[\s\[\{,])![^!\s]', content, re.MULTILINE):
        raise YamlDiffError(
            f"Custom tags are not supported: {source_name}\n"
            "  yaml-diff does not support custom YAML tags (!)"
        )


def load_yaml(source: str) -> Any:
    """
    Load YAML from file path or stdin.
    
    Args:
        source: File path or '-' for stdin
        
    Returns:
        Parsed YAML as Python object (dict, list, or primitive)
        
    Raises:
        YamlDiffError: On file not found, read error, or parse failure
    """
    try:
        if source == '-':
            content = sys.stdin.read()
        else:
            with open(source, 'r', encoding='utf-8') as f:
                content = f.read()
    except FileNotFoundError:
        raise YamlDiffError(f"File not found: {source}")
    except PermissionError:
        raise YamlDiffError(f"Permission denied: {source}")
    except IOError as e:
        raise YamlDiffError(f"Cannot read file '{source}': {e}")
    
    # Check for unsupported features before parsing
    check_unsupported_features(content, source)
    
    try:
        return yaml.safe_load(content)
    except yaml.YAMLError as e:
        raise YamlDiffError(f"YAML parse error in '{source}': {e}")


def canonicalize(data: Any) -> Any:
    """
    Recursively sort dict keys and normalize types for consistent comparison.
    
    Args:
        data: YAML value (dict, list, or primitive)
        
    Returns:
        Canonicalized value with sorted dict keys
    """
    if isinstance(data, dict):
        return {k: canonicalize(v) for k, v in sorted(data.items())}
    if isinstance(data, list):
        return [canonicalize(item) for item in data]
    return data


def diff_primitives(old: Any, new: Any, path: List[str]) -> List[DiffOp]:
    """
    Compare primitive values (str, int, float, bool, None).
    
    Args:
        old: First primitive value
        new: Second primitive value
        path: Current path
        
    Returns:
        List with single replace operation if different, empty if equal
    """
    if old == new:
        return []
    return [DiffOp('replace', path, old, new)]


def diff_maps(old: dict, new: dict, path: List[str]) -> List[DiffOp]:
    """
    Compare two dicts, finding added/removed/changed keys.
    
    Args:
        old: First dict
        new: Second dict
        path: Current path
        
    Returns:
        List of DiffOp objects for all differences
    """
    diffs = []
    all_keys = set(old.keys()) | set(new.keys())
    
    for key in sorted(all_keys, key=str):
        key_path = path + [str(key)]
        
        if key not in old:
            # Key added in new
            diffs.append(DiffOp('add', key_path, None, new[key]))
        elif key not in new:
            # Key removed from old
            diffs.append(DiffOp('remove', key_path, old[key], None))
        elif old[key] != new[key]:
            # Key exists in both but values differ - recurse
            diffs.extend(compute_diff(old[key], new[key], key_path))
    
    return diffs


def diff_lists(old: list, new: list, path: List[str]) -> List[DiffOp]:
    """
    Compare two lists by index position.
    
    Args:
        old: First list
        new: Second list
        path: Current path
        
    Returns:
        List of DiffOp objects for all differences
    """
    diffs = []
    max_len = max(len(old), len(new))
    
    for i in range(max_len):
        idx_path = path + [str(i)]
        
        if i >= len(old):
            # Element added in new
            diffs.append(DiffOp('add', idx_path, None, new[i]))
        elif i >= len(new):
            # Element removed from old
            diffs.append(DiffOp('remove', idx_path, old[i], None))
        elif old[i] != new[i]:
            # Element exists in both but values differ - recurse
            diffs.extend(compute_diff(old[i], new[i], idx_path))
    
    return diffs


def compute_diff(old: Any, new: Any, path: Optional[List[str]] = None) -> List[DiffOp]:
    """
    Recursively compute differences between two YAML structures.
    
    Dispatches to appropriate diff function based on types.
    Handles type mismatches by returning a replace operation.
    
    Args:
        old: First YAML value
        new: Second YAML value
        path: Current path (for recursive calls)
        
    Returns:
        List of DiffOp objects representing the differences
    """
    if path is None:
        path = []
    
    # If values are equal, no diff
    if old == new:
        return []
    
    # Handle type mismatches - replace the entire value
    old_type = type(old)
    new_type = type(new)
    
    if old_type != new_type:
        return [DiffOp('replace', path, old, new)]
    
    # Dispatch to appropriate diff function based on type
    if isinstance(old, dict):
        return diff_maps(old, new, path)
    elif isinstance(old, list):
        return diff_lists(old, new, path)
    else:
        return diff_primitives(old, new, path)
