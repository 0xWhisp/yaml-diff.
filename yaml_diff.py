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


def path_to_json_pointer(path: List[str]) -> str:
    """
    Convert path segments to JSON pointer format (RFC 6901).
    
    Args:
        path: List of path segments
        
    Returns:
        JSON pointer string (e.g., '/foo/bar/0')
    """
    if not path:
        return ''
    
    # RFC 6901: escape ~ as ~0, then / as ~1
    def escape(segment: str) -> str:
        return segment.replace('~', '~0').replace('/', '~1')
    
    return '/' + '/'.join(escape(str(seg)) for seg in path)


def format_json_patch(diffs: List[DiffOp]) -> str:
    """
    Format diffs as JSON-patch (RFC 6902).
    
    Args:
        diffs: List of DiffOp objects
        
    Returns:
        Valid JSON array of operations
    """
    operations = []
    
    for diff in diffs:
        path = path_to_json_pointer(diff.path)
        
        if diff.op == 'add':
            operations.append({'op': 'add', 'path': path, 'value': diff.new_value})
        elif diff.op == 'remove':
            operations.append({'op': 'remove', 'path': path})
        elif diff.op == 'replace':
            operations.append({'op': 'replace', 'path': path, 'value': diff.new_value})
    
    return json.dumps(operations, indent=2)


# ANSI color codes
COLOR_RED = '\033[31m'
COLOR_GREEN = '\033[32m'
COLOR_RESET = '\033[0m'


def format_human(diffs: List[DiffOp], use_color: bool = False) -> str:
    """
    Format diffs as human-readable unified diff style.
    
    Args:
        diffs: List of DiffOp objects
        use_color: Whether to colorize output (green for add, red for remove)
        
    Returns:
        Human-readable diff string
    """
    if not diffs:
        return ''
    
    lines = []
    
    for diff in diffs:
        path = path_to_json_pointer(diff.path) or '/'
        
        if diff.op == 'add':
            lines.append(f'{path}:')
            value_str = _format_value(diff.new_value)
            if use_color:
                lines.append(f'  {COLOR_GREEN}+ {value_str}{COLOR_RESET}')
            else:
                lines.append(f'  + {value_str}')
        
        elif diff.op == 'remove':
            lines.append(f'{path}:')
            value_str = _format_value(diff.old_value)
            if use_color:
                lines.append(f'  {COLOR_RED}- {value_str}{COLOR_RESET}')
            else:
                lines.append(f'  - {value_str}')
        
        elif diff.op == 'replace':
            lines.append(f'{path}:')
            old_str = _format_value(diff.old_value)
            new_str = _format_value(diff.new_value)
            if use_color:
                lines.append(f'  {COLOR_RED}- {old_str}{COLOR_RESET}')
                lines.append(f'  {COLOR_GREEN}+ {new_str}{COLOR_RESET}')
            else:
                lines.append(f'  - {old_str}')
                lines.append(f'  + {new_str}')
        
        lines.append('')  # blank line between diffs
    
    return '\n'.join(lines).rstrip('\n')


def _format_value(value: Any) -> str:
    """Format a value for human-readable output."""
    if value is None:
        return 'null'
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2).replace('\n', '\n  ')
    return str(value)


def should_use_color(no_color_flag: bool = False) -> bool:
    """
    Determine if output should be colorized.
    
    Args:
        no_color_flag: Whether --no-color flag was passed
        
    Returns:
        True if colors should be used
    """
    # Respect --no-color flag
    if no_color_flag:
        return False
    
    # Check if stdout is a TTY
    return sys.stdout.isatty()


def compute_exit_code(old_data: Any, new_data: Any) -> int:
    """
    Compute the exit code for comparing two YAML values.
    
    Args:
        old_data: First YAML value (already parsed)
        new_data: Second YAML value (already parsed)
        
    Returns:
        0 if identical, 1 if different
    """
    old_canon = canonicalize(old_data)
    new_canon = canonicalize(new_data)
    diffs = compute_diff(old_canon, new_canon)
    return 0 if not diffs else 1


def create_argument_parser() -> argparse.ArgumentParser:
    """
    Create and configure the argument parser for yaml-diff CLI.
    
    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        prog='yaml-diff',
        description='Compare two YAML files semantically and show differences.',
        epilog='Examples:\n'
               '  yaml-diff file1.yaml file2.yaml          # Human-readable diff\n'
               '  yaml-diff file1.yaml file2.yaml -j       # JSON-patch output\n'
               '  yaml-diff - file2.yaml < file1.yaml      # Read first file from stdin',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        'file1',
        help="First YAML file (use '-' for stdin)"
    )
    parser.add_argument(
        'file2',
        help='Second YAML file'
    )
    parser.add_argument(
        '-j', '--json-patch',
        action='store_true',
        help='Output in JSON-patch format (RFC 6902)'
    )
    parser.add_argument(
        '--no-color',
        action='store_true',
        help='Disable colorized output'
    )
    
    return parser


def main() -> int:
    """
    Entry point for yaml-diff CLI.
    
    Parses arguments, loads YAML files, computes diff, and outputs results.
    
    Returns:
        Exit code: 0 if identical, 1 if different, 2 on error
    """
    parser = create_argument_parser()
    args = parser.parse_args()
    
    try:
        # Load and validate both YAML inputs
        old_data = load_yaml(args.file1)
        new_data = load_yaml(args.file2)
        
        # Canonicalize for consistent comparison
        old_canon = canonicalize(old_data)
        new_canon = canonicalize(new_data)
        
        # Compute diff
        diffs = compute_diff(old_canon, new_canon)
        
        # If no differences, exit with code 0
        if not diffs:
            return 0
        
        # Format and output results
        if args.json_patch:
            output = format_json_patch(diffs)
        else:
            use_color = should_use_color(args.no_color)
            output = format_human(diffs, use_color)
        
        print(output)
        return 1
        
    except YamlDiffError as e:
        print(f"yaml-diff: error: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"yaml-diff: error: {e}", file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
