# Requirements Document

## Introduction

yaml-diff is a minimal, production-grade CLI tool that compares two YAML files semantically — ignoring key ordering, comments, and non-significant formatting — and computes a meaningful diff showing keys added, removed, or changed, including nested diffs in maps, lists, and primitives. The tool outputs either a human-friendly unified diff (colorized) or a JSON-patch format. This tool targets developers working with configuration files, Kubernetes manifests, CI configs, and similar YAML-based workflows.

## Glossary

- **yaml-diff**: The CLI tool being developed for semantic YAML comparison
- **Semantic Diff**: A comparison that ignores superficial differences (ordering, comments, whitespace) and focuses on actual data changes
- **JSON-patch**: A standardized format (RFC 6902) for describing changes to a JSON document
- **Canonicalization**: The process of converting YAML to a normalized form with sorted keys for consistent comparison
- **Primitive**: Basic YAML values including strings, numbers, booleans, and null
- **Map**: A YAML mapping/dictionary structure with key-value pairs
- **List**: A YAML sequence/array structure

## Requirements

### Requirement 1

**User Story:** As a developer, I want to compare two YAML files semantically, so that I can identify actual data differences without being distracted by formatting or ordering changes.

#### Acceptance Criteria

1. WHEN a user provides two YAML file paths as arguments THEN yaml-diff SHALL parse both files and compute their semantic differences
2. WHEN a user pipes YAML content via stdin and provides one file path THEN yaml-diff SHALL compare the stdin content against the file content
3. WHEN comparing YAML maps THEN yaml-diff SHALL ignore key ordering and compare by key identity
4. WHEN comparing YAML content THEN yaml-diff SHALL ignore comments and non-significant whitespace
5. WHEN YAML parsing fails THEN yaml-diff SHALL display a clear error message indicating the file and parse error location

### Requirement 2

**User Story:** As a developer, I want to see differences in maps clearly, so that I can understand which keys were added, removed, or modified.

#### Acceptance Criteria

1. WHEN a key exists in the second file but not the first THEN yaml-diff SHALL report the key as added
2. WHEN a key exists in the first file but not the second THEN yaml-diff SHALL report the key as removed
3. WHEN a key exists in both files with different values THEN yaml-diff SHALL report the key as changed and show both values
4. WHEN a key exists in both files with identical values THEN yaml-diff SHALL not report any difference for that key
5. WHEN maps are nested THEN yaml-diff SHALL recursively compute differences at each nesting level

### Requirement 3

**User Story:** As a developer, I want to see differences in lists clearly, so that I can understand what items were added, removed, or changed.

#### Acceptance Criteria

1. WHEN comparing lists THEN yaml-diff SHALL compare elements by position (index-based comparison)
2. WHEN the second list has more elements than the first THEN yaml-diff SHALL report additional elements as added
3. WHEN the first list has more elements than the second THEN yaml-diff SHALL report missing elements as removed
4. WHEN list elements at the same index differ THEN yaml-diff SHALL report the element as changed
5. WHEN list elements contain nested structures THEN yaml-diff SHALL recursively compute differences

### Requirement 4

**User Story:** As a developer, I want human-readable output by default, so that I can quickly understand the differences in my terminal.

#### Acceptance Criteria

1. WHEN yaml-diff runs without output format flags THEN yaml-diff SHALL produce human-readable unified diff output
2. WHEN outputting to a terminal that supports colors THEN yaml-diff SHALL colorize additions in green and removals in red
3. WHEN outputting to a non-terminal (pipe or redirect) THEN yaml-diff SHALL omit color codes
4. WHEN displaying nested differences THEN yaml-diff SHALL use indentation to show the path hierarchy
5. WHEN no differences exist THEN yaml-diff SHALL output nothing and exit with code 0

### Requirement 5

**User Story:** As a developer, I want JSON-patch output, so that I can programmatically process the differences or apply them to other files.

#### Acceptance Criteria

1. WHEN the user specifies `--json-patch` or `-j` flag THEN yaml-diff SHALL output differences in JSON-patch format (RFC 6902)
2. WHEN generating JSON-patch THEN yaml-diff SHALL produce valid JSON that conforms to the JSON-patch schema
3. WHEN a key is added THEN yaml-diff SHALL generate an "add" operation with the correct path and value
4. WHEN a key is removed THEN yaml-diff SHALL generate a "remove" operation with the correct path
5. WHEN a value is changed THEN yaml-diff SHALL generate a "replace" operation with the correct path and new value

### Requirement 6

**User Story:** As a developer, I want standard CLI behavior, so that the tool integrates well with my existing workflows and scripts.

#### Acceptance Criteria

1. WHEN the user runs `yaml-diff --help` or `yaml-diff -h` THEN yaml-diff SHALL display usage information, available flags, and examples
2. WHEN files are identical THEN yaml-diff SHALL exit with code 0
3. WHEN files differ THEN yaml-diff SHALL exit with code 1
4. WHEN an error occurs (invalid input, file not found, parse error) THEN yaml-diff SHALL exit with code 2 and display an error message to stderr
5. WHEN the user provides invalid arguments THEN yaml-diff SHALL display a helpful error message and usage hint

### Requirement 7

**User Story:** As a developer, I want the tool to handle edge cases gracefully, so that I can trust it with various YAML inputs.

#### Acceptance Criteria

1. WHEN a YAML file is empty THEN yaml-diff SHALL treat it as an empty document (null) and compare accordingly
2. WHEN a YAML file contains only comments THEN yaml-diff SHALL treat it as an empty document
3. WHEN comparing different YAML types at the same path (e.g., map vs list) THEN yaml-diff SHALL report a type change
4. WHEN YAML contains unsupported features (anchors, aliases, custom tags) THEN yaml-diff SHALL report a clear error explaining the limitation
5. WHEN file paths are invalid or files are unreadable THEN yaml-diff SHALL report a specific error message

### Requirement 8

**User Story:** As a developer, I want clear documentation of limitations, so that I understand what the tool does and does not support.

#### Acceptance Criteria

1. WHEN yaml-diff encounters YAML anchors or aliases THEN yaml-diff SHALL reject the input with a clear error message stating this feature is unsupported
2. WHEN yaml-diff encounters custom YAML tags THEN yaml-diff SHALL reject the input with a clear error message stating this feature is unsupported
3. WHEN the README is generated THEN the README SHALL include a Limitations section documenting unsupported YAML features
4. WHEN the README is generated THEN the README SHALL document that list comparison is index-based, not content-based

### Requirement 9

**User Story:** As a developer, I want the codebase to be minimal and maintainable, so that I can understand and contribute to it easily.

#### Acceptance Criteria

1. WHEN the project is structured THEN the project SHALL use a flat directory structure with minimal nesting
2. WHEN external dependencies are chosen THEN the project SHALL use only a safe YAML parsing library and standard library components
3. WHEN the implementation language is chosen THEN the project SHALL use either Go (single binary) or Python (single script), whichever yields smaller codebase
4. WHEN code is written THEN the code SHALL include clear comments explaining non-obvious logic

### Requirement 10

**User Story:** As a developer, I want proper repository hygiene, so that the project is community-ready and professional.

#### Acceptance Criteria

1. WHEN the repository is set up THEN the repository SHALL include a `.gitignore` file ignoring language-specific and OS/IDE artifacts
2. WHEN the repository is set up THEN the repository SHALL include a `LICENSE` file with MIT license
3. WHEN the repository is set up THEN the repository SHALL include a `README.md` with Overview, Installation, Usage, Limitations, and Contributing sections
4. WHEN documentation is written THEN the documentation SHALL use a developer-friendly tone, avoiding overly formal or AI-generated-sounding text
