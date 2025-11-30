"""
Tests for yaml-diff tool.

Includes both unit tests and property-based tests using Hypothesis.
"""

import pytest
from hypothesis import given, strategies as st, settings

from yaml_diff import (
    YamlDiffError,
    DiffOp,
    load_yaml,
    check_unsupported_features,
    compute_diff,
    canonicalize,
    path_to_json_pointer,
    format_json_patch,
    format_human,
    should_use_color,
    compute_exit_code,
)


# =============================================================================
# Hypothesis Strategies for YAML values
# =============================================================================

# Primitive values that are valid in YAML
yaml_primitives = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-1000000, max_value=1000000),
    st.floats(allow_nan=False, allow_infinity=False, min_value=-1e10, max_value=1e10),
    st.text(
        alphabet=st.characters(blacklist_categories=('Cs',), blacklist_characters='&*!'),
        min_size=0,
        max_size=50
    )
)

# Recursive YAML structure (maps and lists containing primitives or nested structures)
yaml_values = st.recursive(
    yaml_primitives,
    lambda children: st.one_of(
        st.lists(children, max_size=5),
        st.dictionaries(
            st.text(
                alphabet=st.characters(blacklist_categories=('Cs',), blacklist_characters='&*!:'),
                min_size=1,
                max_size=20
            ),
            children,
            max_size=5
        )
    ),
    max_leaves=20
)


# =============================================================================
# Property-Based Tests
# =============================================================================

# **Feature: yaml-diff, Property 5: Identity Property**
# **Validates: Requirements 2.4, 4.5, 6.2**
@given(value=yaml_values)
@settings(max_examples=100)
def test_identity_property(value):
    """
    Property 5: Identity Property
    
    For any valid YAML value (map, list, or primitive), computing the diff
    of that value against itself SHALL produce an empty diff list.
    """
    diffs = compute_diff(value, value)
    assert diffs == [], f"Expected empty diff for identical values, got {diffs}"


# Maps with at least 2 keys for meaningful shuffle testing
yaml_maps = st.dictionaries(
    st.text(
        alphabet=st.characters(blacklist_categories=('Cs',), blacklist_characters='&*!:'),
        min_size=1,
        max_size=20
    ),
    yaml_values,
    min_size=2,
    max_size=10
)


def shuffle_keys(d: dict) -> dict:
    """Return a new dict with keys in reversed order."""
    return dict(reversed(list(d.items())))


# **Feature: yaml-diff, Property 1: Key Ordering Invariance**
# **Validates: Requirements 1.3**
@given(original=yaml_maps)
@settings(max_examples=100)
def test_key_ordering_invariance(original):
    """
    Property 1: Key Ordering Invariance
    
    For any two YAML maps containing identical keys and values but with
    different key orderings, computing the diff SHALL produce an empty result.
    """
    shuffled = shuffle_keys(original)
    
    # Canonicalize both to ensure consistent comparison
    canon_original = canonicalize(original)
    canon_shuffled = canonicalize(shuffled)
    
    # After canonicalization, they should be equal
    assert canon_original == canon_shuffled, \
        f"Canonicalized maps should be equal regardless of key order"
    
    # Diff of canonicalized versions should be empty
    diffs = compute_diff(canon_original, canon_shuffled)
    assert diffs == [], \
        f"Expected empty diff for same map with different key order, got {diffs}"


# **Feature: yaml-diff, Property 2: Map Diff Correctness**
# **Validates: Requirements 2.1, 2.2, 2.3, 2.4**
@given(
    base_map=yaml_maps,
    keys_to_add=st.dictionaries(
        st.text(min_size=1, max_size=10, alphabet='abcdefghij'),
        yaml_primitives,
        min_size=0,
        max_size=3
    ),
    keys_to_remove=st.integers(min_value=0, max_value=2)
)
@settings(max_examples=100)
def test_map_diff_correctness(base_map, keys_to_add, keys_to_remove):
    """
    Property 2: Map Diff Correctness
    
    For any two YAML maps old and new:
    - For each key in new but not in old, the diff SHALL contain exactly one 'add' operation
    - For each key in old but not in new, the diff SHALL contain exactly one 'remove' operation
    - For each key in both with different values, the diff SHALL contain operations reflecting the change
    - For each key in both with identical values, the diff SHALL contain no operations for that key
    """
    old = dict(base_map)
    new = dict(base_map)
    
    # Add new keys
    for k, v in keys_to_add.items():
        if k not in old:
            new[k] = v
    
    # Remove some keys from new
    keys_list = list(old.keys())
    for i in range(min(keys_to_remove, len(keys_list))):
        key_to_remove = keys_list[i]
        if key_to_remove in new:
            del new[key_to_remove]
    
    diffs = compute_diff(old, new)
    
    # Verify add operations
    added_keys = set(new.keys()) - set(old.keys())
    for key in added_keys:
        add_ops = [d for d in diffs if d.op == 'add' and d.path == [str(key)]]
        assert len(add_ops) == 1, f"Expected exactly one add op for key '{key}'"
        assert add_ops[0].new_value == new[key]
    
    # Verify remove operations
    removed_keys = set(old.keys()) - set(new.keys())
    for key in removed_keys:
        remove_ops = [d for d in diffs if d.op == 'remove' and d.path == [str(key)]]
        assert len(remove_ops) == 1, f"Expected exactly one remove op for key '{key}'"
        assert remove_ops[0].old_value == old[key]
    
    # Verify unchanged keys have no operations
    unchanged_keys = set(old.keys()) & set(new.keys())
    for key in unchanged_keys:
        if old[key] == new[key]:
            key_ops = [d for d in diffs if d.path and d.path[0] == str(key)]
            assert len(key_ops) == 0, f"Expected no ops for unchanged key '{key}'"


# **Feature: yaml-diff, Property 4: List Diff Correctness**
# **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
@given(
    base_list=st.lists(yaml_primitives, min_size=1, max_size=5),
    items_to_add=st.lists(yaml_primitives, min_size=0, max_size=3),
    items_to_remove=st.integers(min_value=0, max_value=2)
)
@settings(max_examples=100)
def test_list_diff_correctness(base_list, items_to_add, items_to_remove):
    """
    Property 4: List Diff Correctness
    
    For any two YAML lists old and new:
    - For each index i where i >= len(old) and i < len(new), the diff SHALL contain an 'add' operation
    - For each index i where i < len(old) and i >= len(new), the diff SHALL contain a 'remove' operation
    - For each index i where both lists have elements but they differ, the diff SHALL contain operations
    """
    old = list(base_list)
    new = list(base_list)
    
    # Add items to new
    new.extend(items_to_add)
    
    # Remove items from new (from the end)
    for _ in range(min(items_to_remove, len(new))):
        if new:
            new.pop()
    
    diffs = compute_diff(old, new)
    
    # Verify additions (indices that exist in new but not old)
    for i in range(len(old), len(new)):
        add_ops = [d for d in diffs if d.op == 'add' and d.path == [str(i)]]
        assert len(add_ops) == 1, f"Expected add op at index {i}"
        assert add_ops[0].new_value == new[i]
    
    # Verify removals (indices that exist in old but not new)
    for i in range(len(new), len(old)):
        remove_ops = [d for d in diffs if d.op == 'remove' and d.path == [str(i)]]
        assert len(remove_ops) == 1, f"Expected remove op at index {i}"
        assert remove_ops[0].old_value == old[i]


# Nested structures for recursive diff testing
nested_yaml = st.recursive(
    yaml_primitives,
    lambda children: st.one_of(
        st.lists(children, min_size=1, max_size=3),
        st.dictionaries(
            st.text(min_size=1, max_size=10, alphabet='abcdefghij'),
            children,
            min_size=1,
            max_size=3
        )
    ),
    max_leaves=10
)


# **Feature: yaml-diff, Property 3: Recursive Diff Correctness**
# **Validates: Requirements 2.5, 3.5**
@given(structure=nested_yaml, new_value=yaml_primitives)
@settings(max_examples=100)
def test_recursive_diff_correctness(structure, new_value):
    """
    Property 3: Recursive Diff Correctness
    
    For any nested YAML structure, changes at any nesting depth SHALL be
    detected and reported with the correct path.
    """
    # Skip primitives - we need nested structures
    if not isinstance(structure, (dict, list)):
        return
    
    # Find a path to a leaf value and modify it
    def find_leaf_path(data, path=[]):
        if isinstance(data, dict) and data:
            key = list(data.keys())[0]
            return find_leaf_path(data[key], path + [str(key)])
        elif isinstance(data, list) and data:
            return find_leaf_path(data[0], path + ['0'])
        else:
            return path
    
    def set_at_path(data, path, value):
        """Set value at path, returning a modified copy."""
        import copy
        result = copy.deepcopy(data)
        current = result
        for key in path[:-1]:
            if isinstance(current, dict):
                current = current[key]
            else:
                current = current[int(key)]
        if path:
            last_key = path[-1]
            if isinstance(current, dict):
                current[last_key] = value
            else:
                current[int(last_key)] = value
        return result
    
    path = find_leaf_path(structure)
    if not path:
        return
    
    modified = set_at_path(structure, path, new_value)
    
    # Get original value at path
    def get_at_path(data, path):
        current = data
        for key in path:
            if isinstance(current, dict):
                current = current[key]
            else:
                current = current[int(key)]
        return current
    
    original_value = get_at_path(structure, path)
    
    # If values are the same, no diff expected
    if original_value == new_value:
        diffs = compute_diff(structure, modified)
        assert diffs == []
        return
    
    diffs = compute_diff(structure, modified)
    
    # Should have exactly one diff at the correct path
    assert len(diffs) == 1, f"Expected 1 diff, got {len(diffs)}: {diffs}"
    assert diffs[0].path == path, f"Expected path {path}, got {diffs[0].path}"
    assert diffs[0].op == 'replace'
    assert diffs[0].old_value == original_value
    assert diffs[0].new_value == new_value


# **Feature: yaml-diff, Property 8: Type Change Detection**
# **Validates: Requirements 7.3**
@given(
    value1=yaml_values,
    value2=yaml_values
)
@settings(max_examples=100)
def test_type_change_detection(value1, value2):
    """
    Property 8: Type Change Detection
    
    For any two YAML values at the same path where the types differ,
    the diff SHALL report a type change or replacement operation.
    """
    # Only test when types actually differ
    if type(value1) == type(value2):
        return
    
    diffs = compute_diff(value1, value2)
    
    # Should have exactly one replace operation at root
    assert len(diffs) == 1, f"Expected 1 diff for type change, got {len(diffs)}"
    assert diffs[0].op == 'replace', f"Expected 'replace' op, got '{diffs[0].op}'"
    assert diffs[0].path == [], f"Expected root path, got {diffs[0].path}"
    assert diffs[0].old_value == value1
    assert diffs[0].new_value == value2


# **Feature: yaml-diff, Property 6: Exit Code Correctness**
# **Validates: Requirements 6.3**
@given(
    value1=yaml_values,
    value2=yaml_values
)
@settings(max_examples=100)
def test_exit_code_correctness(value1, value2):
    """
    Property 6: Exit Code Correctness
    
    For any two YAML values that are not identical, the tool SHALL exit with code 1.
    For identical values, the tool SHALL exit with code 0.
    """
    exit_code = compute_exit_code(value1, value2)
    
    # Canonicalize both values for comparison
    canon1 = canonicalize(value1)
    canon2 = canonicalize(value2)
    
    if canon1 == canon2:
        assert exit_code == 0, f"Expected exit code 0 for identical values, got {exit_code}"
    else:
        assert exit_code == 1, f"Expected exit code 1 for different values, got {exit_code}"


import json as json_module


# **Feature: yaml-diff, Property 7: JSON-Patch Validity**
# **Validates: Requirements 5.2**
@given(
    old_value=yaml_values,
    new_value=yaml_values
)
@settings(max_examples=100)
def test_json_patch_validity(old_value, new_value):
    """
    Property 7: JSON-Patch Validity
    
    For any diff result, the JSON-patch output SHALL be valid JSON conforming
    to RFC 6902 schema (array of objects with 'op', 'path', and optionally 'value' fields).
    """
    diffs = compute_diff(old_value, new_value)
    json_output = format_json_patch(diffs)
    
    # Must be valid JSON
    parsed = json_module.loads(json_output)
    
    # Must be an array
    assert isinstance(parsed, list), f"JSON-patch must be an array, got {type(parsed)}"
    
    # Each operation must conform to RFC 6902
    valid_ops = {'add', 'remove', 'replace', 'move', 'copy', 'test'}
    
    for op in parsed:
        # Must be an object
        assert isinstance(op, dict), f"Each operation must be an object, got {type(op)}"
        
        # Must have 'op' field
        assert 'op' in op, "Operation must have 'op' field"
        assert op['op'] in valid_ops, f"Invalid op: {op['op']}"
        
        # Must have 'path' field
        assert 'path' in op, "Operation must have 'path' field"
        assert isinstance(op['path'], str), "Path must be a string"
        
        # 'add' and 'replace' must have 'value' field
        if op['op'] in ('add', 'replace'):
            assert 'value' in op, f"'{op['op']}' operation must have 'value' field"
        
        # 'remove' should not have 'value' field (per RFC 6902)
        if op['op'] == 'remove':
            assert 'value' not in op, "'remove' operation should not have 'value' field"


# =============================================================================
# Unit Tests for check_unsupported_features
# =============================================================================

class TestCheckUnsupportedFeatures:
    """Unit tests for unsupported YAML feature detection."""
    
    def test_rejects_anchors(self):
        """Anchors (&name) should be rejected."""
        content = "key: &anchor value"
        with pytest.raises(YamlDiffError) as exc_info:
            check_unsupported_features(content, "test.yaml")
        assert "Anchors are not supported" in str(exc_info.value)
    
    def test_rejects_aliases(self):
        """Aliases (*name) should be rejected."""
        content = "key: *alias"
        with pytest.raises(YamlDiffError) as exc_info:
            check_unsupported_features(content, "test.yaml")
        assert "Aliases are not supported" in str(exc_info.value)
    
    def test_rejects_custom_tags(self):
        """Custom tags (!tag) should be rejected."""
        content = "key: !custom value"
        with pytest.raises(YamlDiffError) as exc_info:
            check_unsupported_features(content, "test.yaml")
        assert "Custom tags are not supported" in str(exc_info.value)
    
    def test_allows_standard_yaml(self):
        """Standard YAML without anchors/aliases/tags should pass."""
        content = """
name: test
items:
  - one
  - two
nested:
  key: value
"""
        # Should not raise
        check_unsupported_features(content, "test.yaml")
    
    def test_allows_ampersand_in_string(self):
        """Ampersand in quoted strings should be allowed."""
        content = 'key: "Tom & Jerry"'
        # Should not raise
        check_unsupported_features(content, "test.yaml")


# =============================================================================
# Unit Tests for load_yaml
# =============================================================================

class TestLoadYaml:
    """Unit tests for YAML loading."""
    
    def test_file_not_found(self):
        """Should raise YamlDiffError for missing files."""
        with pytest.raises(YamlDiffError) as exc_info:
            load_yaml("nonexistent_file.yaml")
        assert "File not found" in str(exc_info.value)
    
    def test_invalid_yaml(self, tmp_path):
        """Should raise YamlDiffError for invalid YAML."""
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("key: [unclosed")
        with pytest.raises(YamlDiffError) as exc_info:
            load_yaml(str(bad_yaml))
        assert "YAML parse error" in str(exc_info.value)
    
    def test_valid_yaml(self, tmp_path):
        """Should parse valid YAML correctly."""
        good_yaml = tmp_path / "good.yaml"
        good_yaml.write_text("key: value\nlist:\n  - item1\n  - item2")
        result = load_yaml(str(good_yaml))
        assert result == {"key": "value", "list": ["item1", "item2"]}
    
    def test_empty_file(self, tmp_path):
        """Empty file should return None."""
        empty_yaml = tmp_path / "empty.yaml"
        empty_yaml.write_text("")
        result = load_yaml(str(empty_yaml))
        assert result is None


# =============================================================================
# Unit Tests for Edge Cases (Requirements 7.1, 7.2)
# =============================================================================

class TestEdgeCases:
    """Unit tests for edge case handling."""
    
    def test_empty_file_returns_none(self, tmp_path):
        """Empty file should be treated as null value (Requirements 7.1)."""
        empty_file = tmp_path / "empty.yaml"
        empty_file.write_text("")
        result = load_yaml(str(empty_file))
        assert result is None
    
    def test_comment_only_file_returns_none(self, tmp_path):
        """Comment-only file should be treated as empty document (Requirements 7.2)."""
        comment_file = tmp_path / "comments.yaml"
        comment_file.write_text("# This is a comment\n# Another comment\n")
        result = load_yaml(str(comment_file))
        assert result is None
    
    def test_empty_vs_empty_no_diff(self, tmp_path):
        """Two empty files should produce no diff."""
        diffs = compute_diff(None, None)
        assert diffs == []
    
    def test_empty_vs_content_produces_diff(self, tmp_path):
        """Empty file vs file with content should produce diff."""
        diffs = compute_diff(None, {"key": "value"})
        assert len(diffs) == 1
        assert diffs[0].op == "replace"
        assert diffs[0].old_value is None
        assert diffs[0].new_value == {"key": "value"}
    
    def test_content_vs_empty_produces_diff(self, tmp_path):
        """File with content vs empty file should produce diff."""
        diffs = compute_diff({"key": "value"}, None)
        assert len(diffs) == 1
        assert diffs[0].op == "replace"
        assert diffs[0].old_value == {"key": "value"}
        assert diffs[0].new_value is None
    
    def test_deeply_nested_structure(self):
        """Deeply nested structures (5+ levels) should be handled correctly."""
        deep = {
            "level1": {
                "level2": {
                    "level3": {
                        "level4": {
                            "level5": {
                                "level6": "deep_value"
                            }
                        }
                    }
                }
            }
        }
        
        # Same structure should produce no diff
        diffs = compute_diff(deep, deep)
        assert diffs == []
        
        # Modified deep value should be detected
        import copy
        modified = copy.deepcopy(deep)
        modified["level1"]["level2"]["level3"]["level4"]["level5"]["level6"] = "changed"
        
        diffs = compute_diff(deep, modified)
        assert len(diffs) == 1
        assert diffs[0].op == "replace"
        assert diffs[0].path == ["level1", "level2", "level3", "level4", "level5", "level6"]
        assert diffs[0].old_value == "deep_value"
        assert diffs[0].new_value == "changed"
    
    def test_deeply_nested_list(self):
        """Deeply nested lists should be handled correctly."""
        deep = [[[[["deep_item"]]]]]
        
        # Same structure should produce no diff
        diffs = compute_diff(deep, deep)
        assert diffs == []
        
        # Modified deep value should be detected
        import copy
        modified = copy.deepcopy(deep)
        modified[0][0][0][0][0] = "changed"
        
        diffs = compute_diff(deep, modified)
        assert len(diffs) == 1
        assert diffs[0].op == "replace"
        assert diffs[0].path == ["0", "0", "0", "0", "0"]
    
    def test_mixed_deep_nesting(self):
        """Mixed maps and lists at deep nesting should work."""
        deep = {
            "items": [
                {
                    "nested": [
                        {"value": 42}
                    ]
                }
            ]
        }
        
        import copy
        modified = copy.deepcopy(deep)
        modified["items"][0]["nested"][0]["value"] = 100
        
        diffs = compute_diff(deep, modified)
        assert len(diffs) == 1
        assert diffs[0].path == ["items", "0", "nested", "0", "value"]
        assert diffs[0].old_value == 42
        assert diffs[0].new_value == 100
    
    def test_whitespace_only_file(self, tmp_path):
        """File with only whitespace (spaces/newlines) should be treated as empty."""
        ws_file = tmp_path / "whitespace.yaml"
        ws_file.write_text("   \n\n   ")
        result = load_yaml(str(ws_file))
        assert result is None
    
    def test_comment_with_whitespace(self, tmp_path):
        """File with comments and whitespace should be treated as empty."""
        file = tmp_path / "mixed.yaml"
        file.write_text("   \n# comment\n   \n# another\n")
        result = load_yaml(str(file))
        assert result is None


# =============================================================================
# Unit Tests for Output Formatters
# =============================================================================

class TestPathToJsonPointer:
    """Unit tests for JSON pointer conversion."""
    
    def test_empty_path(self):
        """Empty path should return empty string."""
        assert path_to_json_pointer([]) == ''
    
    def test_simple_path(self):
        """Simple path should be converted correctly."""
        assert path_to_json_pointer(['foo', 'bar']) == '/foo/bar'
    
    def test_path_with_index(self):
        """Path with numeric index should work."""
        assert path_to_json_pointer(['items', '0', 'name']) == '/items/0/name'
    
    def test_escape_tilde(self):
        """Tilde should be escaped as ~0."""
        assert path_to_json_pointer(['key~name']) == '/key~0name'
    
    def test_escape_slash(self):
        """Slash should be escaped as ~1."""
        assert path_to_json_pointer(['key/name']) == '/key~1name'
    
    def test_escape_both(self):
        """Both tilde and slash should be escaped correctly."""
        assert path_to_json_pointer(['a~b/c']) == '/a~0b~1c'


class TestFormatHuman:
    """Unit tests for human-readable output formatting."""
    
    def test_empty_diffs(self):
        """Empty diff list should return empty string."""
        assert format_human([]) == ''
    
    def test_add_operation(self):
        """Add operation should show + prefix."""
        diffs = [DiffOp('add', ['key'], None, 'value')]
        output = format_human(diffs, use_color=False)
        assert '/key:' in output
        assert '+ value' in output
    
    def test_remove_operation(self):
        """Remove operation should show - prefix."""
        diffs = [DiffOp('remove', ['key'], 'old_value', None)]
        output = format_human(diffs, use_color=False)
        assert '/key:' in output
        assert '- old_value' in output
    
    def test_replace_operation(self):
        """Replace operation should show both - and +."""
        diffs = [DiffOp('replace', ['key'], 'old', 'new')]
        output = format_human(diffs, use_color=False)
        assert '/key:' in output
        assert '- old' in output
        assert '+ new' in output
    
    def test_with_color(self):
        """Color codes should be included when use_color=True."""
        diffs = [DiffOp('add', ['key'], None, 'value')]
        output = format_human(diffs, use_color=True)
        assert '\033[32m' in output  # green
        assert '\033[0m' in output   # reset
    
    def test_null_value(self):
        """None should be formatted as 'null'."""
        diffs = [DiffOp('replace', ['key'], None, 'value')]
        output = format_human(diffs, use_color=False)
        assert '- null' in output
    
    def test_bool_value(self):
        """Booleans should be formatted as 'true'/'false'."""
        diffs = [DiffOp('replace', ['key'], True, False)]
        output = format_human(diffs, use_color=False)
        assert '- true' in output
        assert '+ false' in output
    
    def test_dict_value(self):
        """Dict values should be JSON formatted."""
        diffs = [DiffOp('add', ['key'], None, {'nested': 'value'})]
        output = format_human(diffs, use_color=False)
        assert 'nested' in output
        assert 'value' in output
    
    def test_root_path(self):
        """Empty path should show as '/'."""
        diffs = [DiffOp('replace', [], 'old', 'new')]
        output = format_human(diffs, use_color=False)
        assert '/:' in output


class TestFormatJsonPatch:
    """Unit tests for JSON-patch output formatting."""
    
    def test_empty_diffs(self):
        """Empty diff list should return empty JSON array."""
        output = format_json_patch([])
        assert json_module.loads(output) == []
    
    def test_add_operation(self):
        """Add operation should have correct structure."""
        diffs = [DiffOp('add', ['key'], None, 'value')]
        output = format_json_patch(diffs)
        parsed = json_module.loads(output)
        assert len(parsed) == 1
        assert parsed[0]['op'] == 'add'
        assert parsed[0]['path'] == '/key'
        assert parsed[0]['value'] == 'value'
    
    def test_remove_operation(self):
        """Remove operation should not have value field."""
        diffs = [DiffOp('remove', ['key'], 'old', None)]
        output = format_json_patch(diffs)
        parsed = json_module.loads(output)
        assert len(parsed) == 1
        assert parsed[0]['op'] == 'remove'
        assert parsed[0]['path'] == '/key'
        assert 'value' not in parsed[0]
    
    def test_replace_operation(self):
        """Replace operation should have new value."""
        diffs = [DiffOp('replace', ['key'], 'old', 'new')]
        output = format_json_patch(diffs)
        parsed = json_module.loads(output)
        assert len(parsed) == 1
        assert parsed[0]['op'] == 'replace'
        assert parsed[0]['path'] == '/key'
        assert parsed[0]['value'] == 'new'


class TestShouldUseColor:
    """Unit tests for color detection."""
    
    def test_no_color_flag(self):
        """--no-color flag should disable colors."""
        assert should_use_color(no_color_flag=True) == False
    
    def test_default_checks_tty(self):
        """Without flag, should check if stdout is TTY."""
        # In test environment, stdout is usually not a TTY
        result = should_use_color(no_color_flag=False)
        assert isinstance(result, bool)


# =============================================================================
# Unit Tests for CLI (main function)
# =============================================================================

class TestCLI:
    """Unit tests for CLI functionality."""
    
    def test_identical_files_exit_0(self, tmp_path):
        """Identical files should exit with code 0."""
        file1 = tmp_path / "file1.yaml"
        file2 = tmp_path / "file2.yaml"
        file1.write_text("key: value")
        file2.write_text("key: value")
        
        import subprocess
        result = subprocess.run(
            ['python', 'yaml_diff.py', str(file1), str(file2)],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert result.stdout == ''
    
    def test_different_files_exit_1(self, tmp_path):
        """Different files should exit with code 1."""
        file1 = tmp_path / "file1.yaml"
        file2 = tmp_path / "file2.yaml"
        file1.write_text("key: old")
        file2.write_text("key: new")
        
        import subprocess
        result = subprocess.run(
            ['python', 'yaml_diff.py', str(file1), str(file2)],
            capture_output=True,
            text=True
        )
        assert result.returncode == 1
        assert '/key:' in result.stdout
    
    def test_file_not_found_exit_2(self, tmp_path):
        """Missing file should exit with code 2."""
        file1 = tmp_path / "exists.yaml"
        file1.write_text("key: value")
        
        import subprocess
        result = subprocess.run(
            ['python', 'yaml_diff.py', str(file1), 'nonexistent.yaml'],
            capture_output=True,
            text=True
        )
        assert result.returncode == 2
        assert 'error' in result.stderr.lower()
    
    def test_json_patch_flag(self, tmp_path):
        """--json-patch flag should output JSON format."""
        file1 = tmp_path / "file1.yaml"
        file2 = tmp_path / "file2.yaml"
        file1.write_text("key: old")
        file2.write_text("key: new")
        
        import subprocess
        result = subprocess.run(
            ['python', 'yaml_diff.py', str(file1), str(file2), '--json-patch'],
            capture_output=True,
            text=True
        )
        assert result.returncode == 1
        parsed = json_module.loads(result.stdout)
        assert isinstance(parsed, list)
        assert parsed[0]['op'] == 'replace'
    
    def test_short_json_flag(self, tmp_path):
        """-j flag should work same as --json-patch."""
        file1 = tmp_path / "file1.yaml"
        file2 = tmp_path / "file2.yaml"
        file1.write_text("key: old")
        file2.write_text("key: new")
        
        import subprocess
        result = subprocess.run(
            ['python', 'yaml_diff.py', str(file1), str(file2), '-j'],
            capture_output=True,
            text=True
        )
        assert result.returncode == 1
        parsed = json_module.loads(result.stdout)
        assert isinstance(parsed, list)
    
    def test_help_flag(self):
        """--help should show usage information."""
        import subprocess
        result = subprocess.run(
            ['python', 'yaml_diff.py', '--help'],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert 'usage' in result.stdout.lower()
        assert 'yaml-diff' in result.stdout.lower()
    
    def test_invalid_yaml_exit_2(self, tmp_path):
        """Invalid YAML should exit with code 2."""
        file1 = tmp_path / "valid.yaml"
        file2 = tmp_path / "invalid.yaml"
        file1.write_text("key: value")
        file2.write_text("key: [unclosed")
        
        import subprocess
        result = subprocess.run(
            ['python', 'yaml_diff.py', str(file1), str(file2)],
            capture_output=True,
            text=True
        )
        assert result.returncode == 2
        assert 'error' in result.stderr.lower()
    
    def test_anchor_rejected_exit_2(self, tmp_path):
        """YAML with anchors should exit with code 2."""
        file1 = tmp_path / "normal.yaml"
        file2 = tmp_path / "anchor.yaml"
        file1.write_text("key: value")
        file2.write_text("key: &anchor value")
        
        import subprocess
        result = subprocess.run(
            ['python', 'yaml_diff.py', str(file1), str(file2)],
            capture_output=True,
            text=True
        )
        assert result.returncode == 2
        assert 'anchor' in result.stderr.lower()


class TestCanonicalizeFunction:
    """Unit tests for canonicalize function."""
    
    def test_sorts_dict_keys(self):
        """Dict keys should be sorted."""
        data = {'z': 1, 'a': 2, 'm': 3}
        result = canonicalize(data)
        assert list(result.keys()) == ['a', 'm', 'z']
    
    def test_preserves_list_order(self):
        """List order should be preserved."""
        data = [3, 1, 2]
        result = canonicalize(data)
        assert result == [3, 1, 2]
    
    def test_recursive_sort(self):
        """Nested dicts should also be sorted."""
        data = {'b': {'z': 1, 'a': 2}, 'a': 1}
        result = canonicalize(data)
        assert list(result.keys()) == ['a', 'b']
        assert list(result['b'].keys()) == ['a', 'z']
    
    def test_primitives_unchanged(self):
        """Primitives should pass through unchanged."""
        assert canonicalize(42) == 42
        assert canonicalize('hello') == 'hello'
        assert canonicalize(None) is None
        assert canonicalize(True) is True
