"""Unit tests cho Fuzzy String Matching Engine (Task #9).

Kiểm thử:
- Lỗi sai chính tả / gõ phím: bluetoth/bluetooth, tai nge/tai nghe, bal0/balo, iphn/iphone.
- Biến thể dấu tiếng Việt: vi da/ví da, khoa/khóa, the sinh vien/thẻ sinh viên.
- Đảo trật tự từ: tai nghe bluetooth / bluetooth tai nghe, ví da nam / nam ví da.
- Chuỗi con / mô tả chi tiết: ví da / ví da bò nâu.
- Tính chất đối xứng, lũy đẳng, xử lý giá trị biên (None, rỗng, ký tự lạ).
- Tích hợp bảng alias (item, color).
"""

import pytest

from app.modules.matching.engine.aliases import COLOR_ALIASES, ITEM_ALIASES
from app.modules.matching.engine.fuzzy import (
    detailed_fuzzy_match,
    fuzzy_match,
    levenshtein_similarity,
    token_similarity,
)
from app.modules.matching.schemas import FuzzySimilarityResult

# ==============================================================================
# 1. Kiểm thử lỗi chính tả / gõ phím (Levenshtein & Typo tolerance)
# ==============================================================================


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
    """Xử lý tốt các lỗi sai chính tả gõ phím thông dụng."""
    score = fuzzy_match(typo, standard)
    assert score >= min_score, (
        f"Lỗi chính tả {typo!r} vs {standard!r} có điểm {score} < {min_score}"
    )


# ==============================================================================
# 2. Kiểm thử biến thể dấu tiếng Việt (Normalizer + Fuzzy)
# ==============================================================================


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
    """Chuỗi có dấu và không dấu sau khi normalize phải đạt điểm tuyệt đối 100.0."""
    assert fuzzy_match(raw_a, raw_b) == 100.0


# ==============================================================================
# 3. Kiểm thử đảo trật tự từ ngữ (Token Sort)
# ==============================================================================


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
    """Đảo trật tự từ vẫn đạt điểm tuyệt đối 100.0 nhờ Token Sort Ratio."""
    assert fuzzy_match(str_a, str_b) == 100.0


# ==============================================================================
# 4. Kiểm thử chuỗi con và mô tả chi tiết mở rộng (Token Set + Length Penalty)
# ==============================================================================


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
    """Mô tả mở rộng/chi tiết đạt điểm tương đồng cao nhưng có phạt độ dài hợp lý."""
    score = fuzzy_match(short_desc, long_desc)
    assert min_score <= score <= max_score, (
        f"{short_desc!r} vs {long_desc!r}: điểm {score} nằm ngoài [{min_score}, {max_score}]"
    )


# ==============================================================================
# 5. Kiểm thử đồ khác loại (Phân biệt rõ ràng, điểm thấp)
# ==============================================================================


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
    """Hai món đồ hoàn toàn khác biệt phải nhận điểm tương đồng thấp."""
    score = fuzzy_match(item_a, item_b)
    assert score <= max_score, (
        f"{item_a!r} vs {item_b!r}: điểm {score} vượt quá ngưỡng tối đa {max_score}"
    )


# ==============================================================================
# 6. Kiểm thử tính chất toán học & xử lý biên (Edge Cases & Mathematical Contracts)
# ==============================================================================


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
    """Tính đối xứng: score(a, b) == score(b, a)."""
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
    """Tính lũy đẳng: score(text, text) == 100.0 với chuỗi hợp lệ."""
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
    """Đầu vào None, chuỗi rỗng, hoặc chỉ ký tự đặc biệt trả về đúng 0.0, không văng lỗi."""
    assert fuzzy_match(raw_a, raw_b) == 0.0


# ==============================================================================
# 7. Kiểm thử tích hợp bảng Alias (Aliases integration)
# ==============================================================================


def test_fuzzy_match_with_item_aliases():
    """Áp dụng bảng ITEM_ALIASES trước khi tính điểm mờ."""
    # AirPods -> tai nghe
    assert fuzzy_match("AirPods Pro", "tai nghe pro", alias_table=ITEM_ALIASES) == 100.0
    # Thẻ SV -> the sinh vien
    assert fuzzy_match("Thẻ SV", "thẻ sinh viên", alias_table="item") == 100.0
    # Cục sạc macbook -> sac laptop
    assert fuzzy_match("cục sạc macbook", "củ sạc laptop", alias_table="item") == 100.0


def test_fuzzy_match_with_color_aliases():
    """Áp dụng bảng COLOR_ALIASES cho màu sắc."""
    assert fuzzy_match("BLACK", "đen", alias_table=COLOR_ALIASES) == 100.0
    assert fuzzy_match("ghi", "xám", alias_table="color") == 100.0
    assert fuzzy_match("blue", "xanh dương", alias_table="color") == 100.0


def test_fuzzy_match_invalid_alias_table_name():
    """Tên bảng alias không hợp lệ phải raise ValueError."""
    with pytest.raises(ValueError, match="Bảng alias 'unknown' không tồn tại"):
        fuzzy_match("a", "b", alias_table="unknown")


# ==============================================================================
# 8. Kiểm thử các hàm chi tiết (detailed_fuzzy_match & individual metrics)
# ==============================================================================


def test_detailed_fuzzy_match_structure():
    """detailed_fuzzy_match trả về đúng cấu trúc Pydantic Schema FuzzySimilarityResult."""
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
    """Kiểm tra hoạt động độc lập của levenshtein_similarity và token_similarity."""
    assert levenshtein_similarity("bluetoth", "bluetooth") > 90.0
    assert levenshtein_similarity("", "test") == 0.0

    assert (
        token_similarity("tai nghe bluetooth", "bluetooth tai nghe", mode="sort")
        == 100.0
    )
    assert token_similarity("vi da", "vi da bo", mode="set") == 100.0

    with pytest.raises(ValueError, match="Chế độ token similarity không hợp lệ"):
        token_similarity("a", "b", mode="invalid")  # type: ignore
