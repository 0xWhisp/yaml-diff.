# yaml-diff

A minimal CLI tool for semantic YAML comparison. Compares two YAML files ignoring key ordering, comments, and formatting — showing only actual data differences.

## Overview

yaml-diff parses two YAML files, canonicalizes them (sorting keys, stripping comments), and computes a structural diff. Output is either human-readable (with optional colors) or JSON-patch format (RFC 6902).

Perfect for:
- Comparing Kubernetes manifests
- Reviewing CI/CD config changes
- Diffing any YAML configuration files

## Installation

**Requirements:** Python 3.7+ and PyYAML

```bash
# Install dependencies
pip install pyyaml

# Run directly
python yaml_diff.py file1.yaml file2.yaml
```

Or clone and use:

```bash
git clone <repo-url>
cd yaml-diff
pip install -r requirements.txt
python yaml_diff.py --help
```

## Usage

```bash
# Basic comparison (human-readable output)
python yaml_diff.py old.yaml new.yaml

# JSON-patch output (RFC 6902)
python yaml_diff.py old.yaml new.yaml --json-patch
python yaml_diff.py old.yaml new.yaml -j

# Read from stdin
cat old.yaml | python yaml_diff.py - new.yaml

# Disable colors
python yaml_diff.py old.yaml new.yaml --no-color
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Files are identical |
| 1 | Files differ |
| 2 | Error (parse failure, file not found, invalid args) |

### Example Output

**Human-readable (default):**

```
/server/port:
  - 8080
  + 9090

/database/host:
  - localhost
  + db.example.com

/features/new_feature:
  + true
```

**JSON-patch (`-j` flag):**

```json
[
  {"op": "replace", "path": "/server/port", "value": 9090},
  {"op": "replace", "path": "/database/host", "value": "db.example.com"},
  {"op": "add", "path": "/features/new_feature", "value": true}
]
```

## Limitations

- **No anchors/aliases:** YAML anchors (`&name`) and aliases (`*name`) are not supported. The tool will reject files containing these features with a clear error message.

- **No custom tags:** Custom YAML tags (`!tag`) are not supported.

- **Index-based list comparison:** Lists are compared by position (index), not by content matching. If you insert an element at the beginning of a list, all subsequent elements will show as changed.

  ```yaml
  # old.yaml          # new.yaml
  items:              items:
    - apple             - banana    # shows as: [0] apple -> banana
    - cherry            - apple     # shows as: [1] cherry -> apple
                        - cherry    # shows as: [2] added
  ```

- **Single-file implementation:** Designed for simplicity, not extensibility.

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Submit a pull request

Run tests with:

```bash
pip install hypothesis pytest
pytest test_yaml_diff.py -v
```

## License

MIT License. See [LICENSE](LICENSE) for details.
