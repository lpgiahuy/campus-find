"""Fuzzy String Matching Engine cho CampusFind (Task #9).

Cung cấp các hàm đo độ tương đồng chuỗi ký tự kết hợp Levenshtein và Token Similarity:
- Bắt lỗi sai chính tả gõ phím (Levenshtein): bluetoth/bluetooth, tai nge/tai nghe, bal0/balo.
- Bắt đảo trật tự từ (Token Sort): tai nghe bluetooth / bluetooth tai nghe.
- Bắt từ con / mô tả chi tiết mở rộng (Token Set có phạt độ dài): ví da bò / ví da.
- Bỏ dấu tiếng Việt thông qua pipeline normalize() từ Task #8: vi da / ví da.
"""

from collections.abc import Mapping
from typing import Literal

from rapidfuzz import fuzz

from app.modules.matching.engine.aliases import (
    COLOR_ALIASES,
    ITEM_ALIASES,
    apply_aliases,
)
from app.modules.matching.engine.normalizer import normalize
from app.modules.matching.schemas import FuzzyScoreBreakdown, FuzzySimilarityResult

ALIAS_TABLES: Mapping[str, Mapping[str, str]] = {
    "item": ITEM_ALIASES,
    "color": COLOR_ALIASES,
}


def levenshtein_similarity(s1: str, s2: str) -> float:
    """Tính độ tương đồng Levenshtein (khoảng cách chỉnh sửa) trên thang [0.0, 100.0]."""
    if not s1 or not s2:
        return 0.0
    return round(float(fuzz.ratio(s1, s2)), 2)


def token_similarity(s1: str, s2: str, mode: Literal["sort", "set"] = "sort") -> float:
    """Tính độ tương đồng token (sort hoặc set) trên thang [0.0, 100.0]."""
    if not s1 or not s2:
        return 0.0
    if mode == "sort":
        score = fuzz.token_sort_ratio(s1, s2)
    elif mode == "set":
        score = fuzz.token_set_ratio(s1, s2)
    else:
        raise ValueError(f"Chế độ token similarity không hợp lệ: {mode!r}")
    return round(float(score), 2)


def composite_similarity(norm_a: str, norm_b: str) -> tuple[float, FuzzyScoreBreakdown]:
    """Tính điểm tương đồng kết hợp giữa hai chuỗi đã qua chuẩn hóa.

    Áp dụng Phương án A:
    - Nếu 1 trong 2 chuỗi rỗng: điểm 0.0.
    - Nếu hai chuỗi trùng khớp tuyệt đối: điểm 100.0.
    - Tính Levenshtein ratio (bắt lỗi typo ký tự).
    - Tính Token Sort ratio (bắt đảo từ).
    - Tính Token Set ratio có áp dụng hệ số phạt tỷ lệ độ dài (length penalty)
      để tránh trường hợp từ ngắn vô tình khớp 100% với chuỗi quá dài.
    - Điểm cuối cùng = max(Levenshtein, max(TokenSort, TokenSet * penalty)).
    """
    if not norm_a or not norm_b:
        breakdown = FuzzyScoreBreakdown(
            levenshtein_ratio=0.0,
            token_sort_ratio=0.0,
            token_set_ratio=0.0,
            length_penalty=0.0,
        )
        return 0.0, breakdown

    if norm_a == norm_b:
        breakdown = FuzzyScoreBreakdown(
            levenshtein_ratio=100.0,
            token_sort_ratio=100.0,
            token_set_ratio=100.0,
            length_penalty=1.0,
        )
        return 100.0, breakdown

    lev = float(fuzz.ratio(norm_a, norm_b))
    ts = float(fuzz.token_sort_ratio(norm_a, norm_b))
    tset = float(fuzz.token_set_ratio(norm_a, norm_b))

    tokens_a = norm_a.split()
    tokens_b = norm_b.split()
    min_len = min(len(tokens_a), len(tokens_b))
    max_len = max(len(tokens_a), len(tokens_b))
    length_penalty = min_len / max_len if max_len > 0 else 1.0

    # Phạt độ dài: nếu một bên mô tả ngắn, bên kia quá dài thì giảm bớt token_set_ratio
    penalized_tset = tset * (0.8 + 0.2 * length_penalty)
    token_score = max(ts, penalized_tset)
    final_score = max(lev, token_score)
    final_score = min(100.0, max(0.0, final_score))

    breakdown = FuzzyScoreBreakdown(
        levenshtein_ratio=round(lev, 2),
        token_sort_ratio=round(ts, 2),
        token_set_ratio=round(tset, 2),
        length_penalty=round(length_penalty, 2),
    )
    return round(final_score, 2), breakdown


def _resolve_alias_table(
    alias_table: Mapping[str, str] | str | None,
) -> Mapping[str, str] | None:
    """Chuyển đổi tham số alias table từ chuỗi tên bảng hoặc đối tượng mapping."""
    if isinstance(alias_table, str):
        table = ALIAS_TABLES.get(alias_table.lower())
        if table is None:
            raise ValueError(
                f"Bảng alias {alias_table!r} không tồn tại. Chọn 'item' hoặc 'color'."
            )
        return table
    return alias_table


def fuzzy_match(
    text_a: str | None,
    text_b: str | None,
    alias_table: Mapping[str, str] | str | None = None,
) -> float:
    """So khớp mờ 2 chuỗi tự do (tên đồ / màu) trả về điểm số [0.0, 100.0].

    Chuỗi đầu vào sẽ được tự động normalize và áp dụng bảng alias trước khi tính điểm.
    """
    table = _resolve_alias_table(alias_table)
    norm_a = apply_aliases(text_a, table) if table else normalize(text_a)
    norm_b = apply_aliases(text_b, table) if table else normalize(text_b)

    score, _ = composite_similarity(norm_a, norm_b)
    return score


def detailed_fuzzy_match(
    text_a: str | None,
    text_b: str | None,
    alias_table: Mapping[str, str] | str | None = None,
) -> FuzzySimilarityResult:
    """So khớp mờ 2 chuỗi và trả về kết quả chi tiết kèm giải trình chỉ số."""
    table = _resolve_alias_table(alias_table)
    norm_a = apply_aliases(text_a, table) if table else normalize(text_a)
    norm_b = apply_aliases(text_b, table) if table else normalize(text_b)

    score, breakdown = composite_similarity(norm_a, norm_b)
    return FuzzySimilarityResult(
        score=score,
        normalized_a=norm_a,
        normalized_b=norm_b,
        breakdown=breakdown,
    )
