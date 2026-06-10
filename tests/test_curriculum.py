from dubai.curriculum import (
    canonical_curriculum,
    matching_raw_curriculum_types,
    normalize_curriculum_field,
    normalize_curriculum_list,
    split_curriculum_value,
)


def test_international_baccalaureate_maps_to_ib():
    assert canonical_curriculum("International Baccalaureate") == "IB"
    assert canonical_curriculum("ib") == "IB"


def test_composite_curriculum_splits_to_canonical_tags():
    assert split_curriculum_value("UK - International Baccalaureate") == ["UK", "IB"]


def test_normalize_curriculum_field_dedupes_ib_aliases():
    assert normalize_curriculum_field("IB, International Baccalaureate") == ["IB"]


def test_matching_raw_types_includes_ib_variants():
    raw = [
        "IB",
        "International Baccalaureate",
        "UK - International Baccalaureate",
        "UK",
    ]
    matched = matching_raw_curriculum_types(raw, "IB")
    assert "IB" in matched
    assert "International Baccalaureate" in matched
    assert "UK - International Baccalaureate" in matched
    assert "UK" not in matched


def test_normalize_curriculum_list_sorts_unique():
    assert normalize_curriculum_list(["International Baccalaureate", "UK", "IB"]) == [
        "IB",
        "UK",
    ]
