# Implementation Plan

- [x] 1. Set up project structure and dependencies





  - [x] 1.1 Create `yaml_diff.py` with module docstring and imports


    - Import sys, json, argparse, dataclasses
    - Import yaml from PyYAML
    - Add module-level docstring explaining the tool
    - _Requirements: 9.1, 9.2_

  - [x] 1.2 Create `requirements.txt` with dependencies

    - Add pyyaml for YAML parsing
    - Add hypothesis for property-based testing (dev dependency)
    - _Requirements: 9.2_
  - [x] 1.3 Create `.gitignore` file


    - Add Python-specific patterns (__pycache__, *.pyc, .pytest_cache)
    - Add IDE patterns (.vscode, .idea)
    - Add OS patterns (.DS_Store, Thumbs.db)
    - _Requirements: 10.1_

  - [x] 1.4 Create `LICENSE` file with MIT license

    - _Requirements: 10.2_

- [x] 2. Implement core data structures and error handling






  - [x] 2.1 Implement `YamlDiffError` exception class

    - Custom exception for yaml-diff specific errors
    - _Requirements: 1.5, 6.4_

  - [x] 2.2 Implement `DiffOp` dataclass





    - Fields: op, path, old_value, new_value
    - Support for 'add', 'remove', 'replace' operations
    - _Requirements: 2.1, 2.2, 2.3_

- [x] 3. Implement YAML loading and validation




  - [x] 3.1 Implement `load_yaml()` function


    - Load from file path or stdin (when path is '-')
    - Use yaml.safe_load for parsing
    - Handle file not found and read errors
    - _Requirements: 1.1, 1.2, 7.5_
  - [x] 3.2 Implement `check_unsupported_features()` function


    - Detect anchors (&) and aliases (*) in raw YAML content
    - Detect custom tags (!)
    - Raise YamlDiffError with clear message
    - _Requirements: 7.4, 8.1, 8.2_
  - [x] 3.3 Write property test for YAML loading


    - **Property 5: Identity Property** - any valid YAML loaded and compared to itself produces empty diff
    - **Validates: Requirements 2.4, 4.5, 6.2**

- [x] 4. Implement canonicalization






  - [x] 4.1 Implement `canonicalize()` function

    - Recursively sort dict keys
    - Preserve list order
    - Normalize primitives
    - _Requirements: 1.3_

  - [x] 4.2 Write property test for key ordering invariance

    - **Property 1: Key Ordering Invariance** - shuffled keys produce empty diff
    - **Validates: Requirements 1.3**

- [x] 5. Implement diff engine






  - [x] 5.1 Implement `compute_diff()` main function

    - Dispatch to appropriate diff function based on types
    - Handle type mismatches (map vs list vs primitive)
    - _Requirements: 7.3_

  - [x] 5.2 Implement `diff_maps()` function

    - Find added keys (in new but not old)
    - Find removed keys (in old but not new)
    - Find changed keys (in both but different values)
    - Recurse for nested structures

    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 5.3 Implement `diff_lists()` function
    - Index-based comparison
    - Handle different lengths (additions/removals)
    - Recurse for nested structures
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_
  - [x] 5.4 Implement `diff_primitives()` function
    - Compare primitive values (str, int, float, bool, None)
    - Return replace operation if different
    - _Requirements: 2.3_
  - [x] 5.5 Write property test for map diff correctness


    - **Property 2: Map Diff Correctness** - add/remove/replace operations are correct

    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4**

  - [x] 5.6 Write property test for list diff correctness

    - **Property 4: List Diff Correctness** - index-based operations are correct

    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4**

  - [x] 5.7 Write property test for recursive diff
    - **Property 3: Recursive Diff Correctness** - nested changes detected at correct paths
    - **Validates: Requirements 2.5, 3.5**
  - [x] 5.8 Write property test for type change detection
    - **Property 8: Type Change Detection** - type mismatches produce replace operations
    - **Validates: Requirements 7.3**

- [x] 6. Checkpoint - Ensure all tests pass





  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Implement output formatters
  - [ ] 7.1 Implement `path_to_json_pointer()` function
    - Convert path list to JSON pointer format (/foo/bar/0)
    - Escape special characters per RFC 6901
    - _Requirements: 5.2_
  - [ ] 7.2 Implement `format_json_patch()` function
    - Convert DiffOp list to JSON-patch array
    - Output valid JSON conforming to RFC 6902
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_
  - [ ] 7.3 Implement `format_human()` function
    - Format diffs as human-readable output
    - Show path, old value (with -), new value (with +)
    - Support colorization (green for add, red for remove)
    - _Requirements: 4.1, 4.2, 4.4_
  - [ ] 7.4 Implement color detection
    - Check if stdout is a TTY
    - Respect --no-color flag
    - _Requirements: 4.2, 4.3_
  - [ ] 7.5 Write property test for JSON-patch validity
    - **Property 7: JSON-Patch Validity** - output is valid JSON with correct schema
    - **Validates: Requirements 5.2**

- [ ] 8. Implement CLI interface
  - [ ] 8.1 Implement argument parser
    - Positional args: file1, file2
    - Optional flags: --json-patch/-j, --no-color, --help/-h
    - _Requirements: 6.1, 6.5_
  - [ ] 8.2 Implement `main()` function
    - Parse arguments
    - Load and validate both YAML inputs
    - Compute diff
    - Format and output results
    - Return appropriate exit code
    - _Requirements: 6.2, 6.3, 6.4_
  - [ ] 8.3 Add entry point (`if __name__ == '__main__'`)
    - Call main() and sys.exit with return code
    - _Requirements: 6.2, 6.3_
  - [ ] 8.4 Write property test for exit code correctness
    - **Property 6: Exit Code Correctness** - different values produce exit code 1
    - **Validates: Requirements 6.3**

- [ ] 9. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Handle edge cases
  - [ ] 10.1 Handle empty files
    - Treat empty file as null value
    - _Requirements: 7.1_
  - [ ] 10.2 Handle comment-only files
    - Treat as empty document (null)
    - _Requirements: 7.2_
  - [ ] 10.3 Write unit tests for edge cases
    - Test empty files, comment-only files, deeply nested structures
    - _Requirements: 7.1, 7.2_

- [ ] 11. Create documentation
  - [ ] 11.1 Create `README.md`
    - Overview section explaining what yaml-diff does
    - Installation instructions (pip install, or run directly)
    - Usage examples with sample commands
    - Limitations section (no anchors/aliases, index-based list diff)
    - Contributing guidelines
    - License reference
    - _Requirements: 8.3, 8.4, 10.3, 10.4_

- [ ] 12. Final Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.
