# Design Document

## Overview

yaml-diff is a minimal CLI tool for semantic YAML comparison. It parses two YAML inputs, canonicalizes them (sorting keys, stripping comments), computes a structural diff, and outputs either human-readable unified diff or JSON-patch format.

**Technology Choice: Python**

Python is chosen over Go for this project because:
- PyYAML provides safe, well-tested YAML parsing with minimal code
- Single-file implementation is achievable (~300-400 lines)
- No compilation step needed; easy to install via pip or run directly
- Standard library provides everything else needed (argparse, json, sys)

**Single Dependency:** PyYAML (safe_load only, no unsafe features)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         CLI Layer                           │
│  (argparse: --help, --json-patch, file args, stdin detect)  │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                      Input Layer                            │
│  (file reading, stdin detection, YAML parsing via PyYAML)   │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                   Canonicalization                          │
│  (recursive key sorting, type normalization)                │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                      Diff Engine                            │
│  (map diff, list diff, primitive diff, recursive descent)   │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                    Output Formatter                         │
│  (human-readable with colors OR JSON-patch)                 │
└─────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. CLI Module (`main()`)

```python
def main() -> int:
    """Entry point. Parses args, orchestrates diff, returns exit code."""
```

**Arguments:**
- `file1`: First YAML file path (or `-` for stdin)
- `file2`: Second YAML file path
- `--json-patch, -j`: Output in JSON-patch format
- `--no-color`: Disable colorized output
- `--help, -h`: Show usage

**Exit Codes:**
- `0`: Files are identical
- `1`: Files differ
- `2`: Error (parse failure, file not found, invalid args)

### 2. Input/Parsing Module

```python
def load_yaml(source: str) -> Any:
    """
    Load YAML from file path or stdin.
    Args:
        source: File path or '-' for stdin
    Returns:
        Parsed YAML as Python object (dict, list, or primitive)
    Raises:
        YamlDiffError: On parse failure or unsupported features
    """

def validate_yaml(data: Any, source_name: str) -> None:
    """
    Check for unsupported YAML features (anchors, aliases, tags).
    Note: PyYAML's safe_load already rejects most unsafe constructs.
    """
```

### 3. Canonicalization Module

```python
def canonicalize(data: Any) -> Any:
    """
    Recursively sort dict keys and normalize types.
    - Dicts: sort by key (string comparison)
    - Lists: preserve order (no sorting)
    - Primitives: normalize (e.g., ensure consistent None representation)
    """
```

### 4. Diff Engine

```python
@dataclass
class DiffOp:
    """Represents a single diff operation."""
    op: str          # 'add', 'remove', 'replace', 'type_change'
    path: List[str]  # JSON pointer path segments
    old_value: Any   # Previous value (for remove/replace)
    new_value: Any   # New value (for add/replace)

def compute_diff(old: Any, new: Any, path: List[str] = None) -> List[DiffOp]:
    """
    Recursively compute differences between two YAML structures.
    Returns list of DiffOp objects.
    """

def diff_maps(old: dict, new: dict, path: List[str]) -> List[DiffOp]:
    """Compare two dicts, finding added/removed/changed keys."""

def diff_lists(old: list, new: list, path: List[str]) -> List[DiffOp]:
    """Compare two lists by index position."""

def diff_primitives(old: Any, new: Any, path: List[str]) -> List[DiffOp]:
    """Compare primitive values (str, int, float, bool, None)."""
```

### 5. Output Formatters

```python
def format_human(diffs: List[DiffOp], use_color: bool) -> str:
    """
    Format diffs as human-readable unified diff style.
    - Additions: green (if color enabled)
    - Removals: red (if color enabled)
    - Shows path hierarchy with indentation
    """

def format_json_patch(diffs: List[DiffOp]) -> str:
    """
    Format diffs as JSON-patch (RFC 6902).
    Returns valid JSON array of operations.
    """

def path_to_json_pointer(path: List[str]) -> str:
    """Convert path segments to JSON pointer format (e.g., /foo/bar/0)."""
```

## Data Models

### DiffOp (Diff Operation)

```python
@dataclass
class DiffOp:
    op: str              # Operation type: 'add', 'remove', 'replace', 'type_change'
    path: List[str]      # Path to the changed element
    old_value: Any       # Value in first file (None for 'add')
    new_value: Any       # Value in second file (None for 'remove')
    old_type: str = None # Type name for type_change operations
    new_type: str = None # Type name for type_change operations
```

### JSON-Patch Output Schema

```json
[
  {"op": "add", "path": "/new/key", "value": "new_value"},
  {"op": "remove", "path": "/old/key"},
  {"op": "replace", "path": "/changed/key", "value": "new_value"}
]
```

### Human-Readable Output Format

```
/path/to/key:
  - old_value
  + new_value

/another/path:
  + added_value

/removed/path:
  - removed_value
```

## Algorithms

### Canonicalization Algorithm

```
function canonicalize(data):
    if data is dict:
        return {k: canonicalize(v) for k, v in sorted(data.items())}
    if data is list:
        return [canonicalize(item) for item in data]
    return data  # primitives unchanged
```

### Map Diff Algorithm

```
function diff_maps(old, new, path):
    diffs = []
    all_keys = set(old.keys()) | set(new.keys())
    
    for key in sorted(all_keys):
        key_path = path + [key]
        
        if key not in old:
            diffs.append(DiffOp('add', key_path, None, new[key]))
        elif key not in new:
            diffs.append(DiffOp('remove', key_path, old[key], None))
        elif old[key] != new[key]:
            diffs.extend(compute_diff(old[key], new[key], key_path))
    
    return diffs
```

### List Diff Algorithm (Index-Based)

```
function diff_lists(old, new, path):
    diffs = []
    max_len = max(len(old), len(new))
    
    for i in range(max_len):
        idx_path = path + [str(i)]
        
        if i >= len(old):
            diffs.append(DiffOp('add', idx_path, None, new[i]))
        elif i >= len(new):
            diffs.append(DiffOp('remove', idx_path, old[i], None))
        elif old[i] != new[i]:
            diffs.extend(compute_diff(old[i], new[i], idx_path))
    
    return diffs
```



## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

Based on the acceptance criteria analysis, the following correctness properties must hold:

### Property 1: Key Ordering Invariance

*For any* two YAML maps containing identical keys and values but with different key orderings, computing the diff SHALL produce an empty result.

**Validates: Requirements 1.3**

### Property 2: Map Diff Correctness

*For any* two YAML maps `old` and `new`:
- For each key in `new` but not in `old`, the diff SHALL contain exactly one 'add' operation for that key with the correct value
- For each key in `old` but not in `new`, the diff SHALL contain exactly one 'remove' operation for that key
- For each key in both with different values, the diff SHALL contain operations reflecting the value change
- For each key in both with identical values, the diff SHALL contain no operations for that key

**Validates: Requirements 2.1, 2.2, 2.3, 2.4**

### Property 3: Recursive Diff Correctness

*For any* nested YAML structure (maps containing maps, maps containing lists, lists containing maps), changes at any nesting depth SHALL be detected and reported with the correct path.

**Validates: Requirements 2.5, 3.5**

### Property 4: List Diff Correctness

*For any* two YAML lists `old` and `new`:
- For each index `i` where `i >= len(old)` and `i < len(new)`, the diff SHALL contain an 'add' operation at index `i`
- For each index `i` where `i < len(old)` and `i >= len(new)`, the diff SHALL contain a 'remove' operation at index `i`
- For each index `i` where both lists have elements but they differ, the diff SHALL contain operations reflecting the change at index `i`

**Validates: Requirements 3.1, 3.2, 3.3, 3.4**

### Property 5: Identity Property

*For any* valid YAML value (map, list, or primitive), computing the diff of that value against itself SHALL produce an empty diff list.

**Validates: Requirements 2.4, 4.5, 6.2**

### Property 6: Exit Code Correctness

*For any* two YAML values that are not identical, the tool SHALL exit with code 1.

**Validates: Requirements 6.3**

### Property 7: JSON-Patch Validity

*For any* diff result, the JSON-patch output SHALL be valid JSON conforming to RFC 6902 schema (array of objects with 'op', 'path', and optionally 'value' fields).

**Validates: Requirements 5.2**

### Property 8: Type Change Detection

*For any* two YAML values at the same path where the types differ (e.g., map vs list, string vs number), the diff SHALL report a type change or replacement operation.

**Validates: Requirements 7.3**

## Error Handling

### Error Categories and Exit Codes

| Error Type | Exit Code | Behavior |
|------------|-----------|----------|
| Files identical | 0 | No output, silent success |
| Files differ | 1 | Output diff to stdout |
| File not found | 2 | Error message to stderr |
| File unreadable | 2 | Error message to stderr |
| YAML parse error | 2 | Error message with location to stderr |
| Unsupported YAML feature | 2 | Error message explaining limitation to stderr |
| Invalid arguments | 2 | Error message + usage hint to stderr |

### Error Message Format

```
yaml-diff: error: <description>
  File: <filename>
  <additional context if available>
```

### Unsupported Feature Detection

PyYAML's `safe_load` already rejects most unsafe constructs. For explicit detection:

```python
class YamlDiffError(Exception):
    """Custom exception for yaml-diff errors."""
    pass

def check_unsupported(yaml_content: str, filename: str) -> None:
    """
    Check for unsupported YAML features before parsing.
    Raises YamlDiffError if anchors (&), aliases (*), or tags (!) are found.
    """
    if '&' in yaml_content or '*' in yaml_content:
        raise YamlDiffError(f"Anchors and aliases are not supported: {filename}")
    # Note: Tags starting with ! are checked separately
```

## Testing Strategy

### Property-Based Testing Framework

**Library:** [Hypothesis](https://hypothesis.readthedocs.io/) - Python's premier property-based testing library

**Configuration:** Each property test will run a minimum of 100 iterations.

### Test File Structure

```
yaml_diff.py          # Main implementation (single file)
test_yaml_diff.py     # All tests (unit + property-based)
```

### Property-Based Tests

Each correctness property from the design document will be implemented as a Hypothesis property test:

1. **Property 1 Test:** Generate random maps, shuffle keys, verify empty diff
2. **Property 2 Test:** Generate two maps with known differences, verify correct operations
3. **Property 3 Test:** Generate nested structures with changes at various depths
4. **Property 4 Test:** Generate two lists with known differences, verify index-based operations
5. **Property 5 Test:** Generate any YAML value, diff against itself, verify empty result
6. **Property 6 Test:** Generate two different values, verify exit code 1
7. **Property 7 Test:** Generate diffs, verify JSON-patch output is valid JSON with correct schema
8. **Property 8 Test:** Generate pairs of values with different types, verify type change detection

### Test Annotation Format

Each property-based test will be annotated with:
```python
# **Feature: yaml-diff, Property {number}: {property_text}**
# **Validates: Requirements X.Y**
```

### Unit Tests

Unit tests will cover specific examples and edge cases:

- Empty file handling
- Comment-only file handling
- Deeply nested structures (5+ levels)
- Large files (1000+ keys)
- Special characters in keys/values
- Unicode content
- Numeric edge cases (0, -0, infinity representations)

### Test Data Generators (Hypothesis Strategies)

```python
from hypothesis import strategies as st

# Primitive values
yaml_primitives = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(),
    st.floats(allow_nan=False),
    st.text(min_size=0, max_size=100)
)

# Recursive YAML structure
yaml_values = st.recursive(
    yaml_primitives,
    lambda children: st.one_of(
        st.lists(children, max_size=10),
        st.dictionaries(st.text(min_size=1, max_size=20), children, max_size=10)
    ),
    max_leaves=50
)

# Maps specifically
yaml_maps = st.dictionaries(
    st.text(min_size=1, max_size=20),
    yaml_values,
    min_size=1,
    max_size=10
)
```

## Project Structure

```
yaml-diff/
├── yaml_diff.py       # Main implementation (CLI + all logic)
├── test_yaml_diff.py  # Tests (unit + property-based)
├── requirements.txt   # Dependencies (pyyaml, hypothesis for dev)
├── README.md          # Documentation
├── LICENSE            # MIT license
├── .gitignore         # Git ignore patterns
└── .kiro/
    └── specs/
        └── yaml-diff/
            ├── requirements.md
            ├── design.md
            └── tasks.md
```
