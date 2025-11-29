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
