# yaml-diff

[![Build Status](https://github.com/0xWhisp/yaml-diff/actions/workflows/test.yml/badge.svg)](https://github.com/0xWhisp/yaml-diff/actions)
[![Coverage Status](https://coveralls.io/repos/github/0xWhisp/yaml-diff/badge.svg?branch=main)](https://coveralls.io/github/0xWhisp/yaml-diff?branch=main)
[![Code Quality](https://app.codacy.com/project/badge/Grade/0xWhisp/yaml-diff)](https://app.codacy.com/gh/0xWhisp/yaml-diff/dashboard)
[![CodeFactor](https://www.codefactor.io/repository/github/0xwhisp/yaml-diff/badge)](https://www.codefactor.io/repository/github/0xwhisp/yaml-diff)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)

Semantic YAML comparison tool. Compares two YAML files ignoring key ordering, comments, and formatting — outputs only actual data differences.

## Why yaml-diff?

Standard `diff` tools compare files line-by-line, flagging irrelevant changes like key reordering or whitespace. yaml-diff parses YAML semantically, so you see what actually changed.

```bash
# These are semantically identical:
# file1.yaml          # file2.yaml
# name: app           # port: 8080
# port: 8080          # name: app

$ yaml-diff file1.yaml file2.yaml
# No output - files are identical
```

## Installation

Requires Python 3.7+ and PyYAML.

```bash
pip install pyyaml
```

Clone and run:

```bash
git clone https://github.com/0xWhisp/yaml-diff.git
cd yaml-diff
python yaml_diff.py --help
```

## Usage

```bash
# Compare two files
python yaml_diff.py old.yaml new.yaml

# JSON-patch output (RFC 6902)
python yaml_diff.py old.yaml new.yaml -j

# Read from stdin
cat old.yaml | python yaml_diff.py - new.yaml

# Disable colors
python yaml_diff.py old.yaml new.yaml --no-color
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Files identical |
| 1 | Files differ |
| 2 | Error |

### Output Examples

Human-readable (default):

```
/server/port:
  - 8080
  + 9090

/database/host:
  - localhost
  + db.example.com
```

JSON-patch (`-j`):

```json
[
  {"op": "replace", "path": "/server/port", "value": 9090},
  {"op": "replace", "path": "/database/host", "value": "db.example.com"}
]
```

## Limitations

- **No anchors/aliases** — YAML anchors (`&`) and aliases (`*`) are rejected with a clear error
- **No custom tags** — Custom YAML tags (`!tag`) are not supported
- **Index-based list comparison** — Lists compare by position, not content. Inserting at the start shifts all indices

## Testing

```bash
pip install pytest hypothesis pytest-cov
pytest test_yaml_diff.py -v
```

60 tests including property-based tests via Hypothesis. 93% code coverage.

## Contributing

1. Fork the repo
2. Create a feature branch
3. Write tests for new functionality
4. Submit a PR

## License

MIT — see [LICENSE](LICENSE)
