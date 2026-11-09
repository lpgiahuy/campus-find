"""Unit tests cho Fuzzy String Matching Engine (Task #9)."""

import pytest

from app.modules.matching.engine.aliases import COLOR_ALIASES, ITEM_ALIASES
from app.modules.matching.engine.fuzzy import (
    composite_similarity,
    detailed_fuzzy_match,
    fuzzy_match,
    levenshtein_similarity,
    token_similarity,
)
from app.modules.matching.schemas import FuzzySimilarityResult


@pytest.mark.parametrize(
    ("typo", "standard", "min_score"),
    [
        ("bluetoth", "bluetooth", 90.0),
        ("tai nge", "tai nghe", 90.0),
        ("bal0", "balo", 70.0),
        ("iphn", "iphone", 75.0),
        ("móc khoa", "móc khóa", 90.0),
        ("laptop dell inspironn", "laptop dell inspiron", 95.0),
        ("sac du phog", "sac du phong", 90.0),
    ],
)
def test_fuzzy_match_typo_tolerance(typo: str, standard: str, min_score: float):
    score = fuzzy_match(typo, standard)
    assert score >= min_score, (
        f"Lỗi chính tả {typo!r} vs {standard!r} có điểm {score} < {min_score}"
    )


@pytest.mark.parametrize(
    ("raw_a", "raw_b"),
    [
        ("vi da", "ví da"),
        ("khoa", "khóa"),
        ("the sinh vien", "thẻ sinh viên"),
        ("vi da bo", "ví da bò"),
        ("dong ho deo tay", "đồng hồ đeo tay"),
        ("chum chia khoa", "chùm chìa khóa"),
    ],
)
def test_fuzzy_match_vietnamese_diacritics_equivalence(raw_a: str, raw_b: str):
    assert fuzzy_match(raw_a, raw_b) == 100.0


@pytest.mark.parametrize(
    ("str_a", "str_b"),
    [
        ("tai nghe bluetooth", "bluetooth tai nghe"),
        ("ví da nam", "nam ví da"),
        ("cáp sạc type c", "type c cáp sạc"),
        ("chuột không dây logitech", "logitech chuột không dây"),
    ],
)
def test_fuzzy_match_word_reordering(str_a: str, str_b: str):
    assert fuzzy_match(str_a, str_b) == 100.0


@pytest.mark.parametrize(
    ("short_desc", "long_desc", "min_score", "max_score"),
    [
        ("ví da", "ví da bò", 90.0, 100.0),
        ("ví da", "ví da bò nâu", 85.0, 100.0),
        ("tai nghe bluetooth", "tai nghe bluetooth sony", 85.0, 100.0),
        ("balo laptop", "balo laptop lenovo thinkpad chống nước", 75.0, 95.0),
        ("iphone 13", "iphone 13 pro max", 85.0, 100.0),
    ],
)
def test_fuzzy_match_subset_and_expanded_descriptions(
    short_desc: str, long_desc: str, min_score: float, max_score: float
):
    score = fuzzy_match(short_desc, long_desc)
    assert min_score <= score <= max_score, (
        f"{short_desc!r} vs {long_desc!r}: điểm {score} ngoài [{min_score}, {max_score}]"
    )


@pytest.mark.parametrize(
    ("item_a", "item_b", "max_score"),
    [
        ("tai nghe", "balo laptop", 30.0),
        ("iphone 13", "chìa khóa xe máy", 40.0),
        ("ví da", "bình nước", 30.0),
        ("đồng hồ", "thẻ sinh viên", 35.0),
    ],
)
def test_fuzzy_match_different_items_low_score(
    item_a: str, item_b: str, max_score: float
):
    score = fuzzy_match(item_a, item_b)
    assert score <= max_score, (
        f"{item_a!r} vs {item_b!r}: điểm {score} vượt ngưỡng {max_score}"
    )


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("bluetoth", "bluetooth"),
        ("ví da", "ví da bò nâu"),
        ("tai nghe", "tai nghe bluetooth"),
        (None, "bluetooth"),
        ("", "ví da"),
    ],
)
def test_fuzzy_match_symmetry(a: str | None, b: str | None):
    assert fuzzy_match(a, b) == fuzzy_match(b, a)


@pytest.mark.parametrize(
    "text",
    [
        "bluetooth",
        "ví da bò",
        "tai nghe không dây",
        "balo chống nước",
    ],
)
def test_fuzzy_match_idempotency(text: str):
    assert fuzzy_match(text, text) == 100.0


@pytest.mark.parametrize(
    ("raw_a", "raw_b"),
    [
        (None, None),
        (None, "bluetooth"),
        ("bluetooth", None),
        ("", ""),
        ("   ", "   "),
        ("!!!", "???"),
        ("", "ví da"),
    ],
)
def test_fuzzy_match_boundary_and_empty_inputs(raw_a: str | None, raw_b: str | None):
    assert fuzzy_match(raw_a, raw_b) == 0.0


def test_fuzzy_match_with_item_aliases():
    assert fuzzy_match("AirPods Pro", "tai nghe pro", alias_table=ITEM_ALIASES) == 100.0
    assert fuzzy_match("Thẻ SV", "thẻ sinh viên", alias_table="item") == 100.0
    assert fuzzy_match("cục sạc macbook", "củ sạc laptop", alias_table="item") == 100.0


def test_fuzzy_match_with_color_aliases():
    assert fuzzy_match("BLACK", "đen", alias_table=COLOR_ALIASES) == 100.0
    assert fuzzy_match("ghi", "xám", alias_table="color") == 100.0
    assert fuzzy_match("blue", "xanh dương", alias_table="color") == 100.0


def test_fuzzy_match_invalid_alias_table_name():
    with pytest.raises(ValueError, match="Bảng alias 'unknown' không tồn tại"):
        fuzzy_match("a", "b", alias_table="unknown")


def test_detailed_fuzzy_match_structure():
    result = detailed_fuzzy_match("bluetoth", "bluetooth tai nghe", alias_table="item")
    assert isinstance(result, FuzzySimilarityResult)
    assert result.score > 0
    assert result.normalized_a == "bluetoth"
    assert result.normalized_b == "bluetooth tai nghe"
    assert result.breakdown.levenshtein_ratio > 0
    assert result.breakdown.token_sort_ratio > 0
    assert result.breakdown.token_set_ratio > 0
    assert 0.0 <= result.breakdown.length_penalty <= 1.0


def test_individual_metrics():
    assert levenshtein_similarity("bluetoth", "bluetooth") > 90.0
    assert levenshtein_similarity("", "test") == 0.0
    assert (
        token_similarity("tai nghe bluetooth", "bluetooth tai nghe", mode="sort")
        == 100.0
    )
    assert token_similarity("vi da", "vi da bo", mode="set") == 100.0
    with pytest.raises(ValueError, match="Chế độ token similarity không hợp lệ"):
        token_similarity("a", "b", mode="invalid")  # type: ignore


def test_composite_similarity_whitespace_handling():
    score, breakdown = composite_similarity("   ", "abc")
    assert score == 0.0
    assert breakdown.levenshtein_ratio == 0.0


def test_single_word_versus_long_text_penalty():
    score = fuzzy_match("den", "ao thun trang co hoa tiet mau den rat dep")
    assert score <= 35.0
