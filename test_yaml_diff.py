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
