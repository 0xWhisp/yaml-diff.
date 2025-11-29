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
