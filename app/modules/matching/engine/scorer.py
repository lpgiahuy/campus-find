"""Weighted Match Scoring Strategy (S = 100*(0.35N + 0.25C + 0.15K + 0.15L + 0.10T))."""

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from app.modules.matching.engine.fuzzy import detailed_fuzzy_match
from app.modules.matching.engine.normalizer import normalize
from app.modules.matching.schemas import (
    ComponentScore,
    MatchScoreBreakdown,
    MatchScoreResult,
)
from app.shared.enums import MatchLevel

WEIGHT_NAME = 0.35
WEIGHT_CATEGORY = 0.25
WEIGHT_COLOR = 0.15
WEIGHT_LOCATION = 0.15
WEIGHT_TIME = 0.10

THRESHOLD_HIGH = 80.0
THRESHOLD_MEDIUM = 60.0
MAX_TIME_DIFF_DAYS = 14.0
NAME_MIN_SCORE = 50.0

COLOR_NEUTRAL_SCORE = 50.0
LOCATION_NEUTRAL_SCORE = 50.0
TIME_NEUTRAL_SCORE = 50.0
ALGORITHM_VERSION = "rules-v1"


def get_match_level(score: float) -> MatchLevel:
    if score >= THRESHOLD_HIGH:
        return MatchLevel.HIGH
    return MatchLevel.MEDIUM if score >= THRESHOLD_MEDIUM else MatchLevel.LOW


def _extract_val(obj: Any, key: str) -> Any:
    if obj is None:
        return None
    return obj.get(key) if isinstance(obj, Mapping) else getattr(obj, key, None)


def score_name(
    name_a: str | None, name_b: str | None
) -> tuple[float, str, dict[str, Any]]:
    s1, s2 = (name_a or "").strip(), (name_b or "").strip()
    if not s1 or not s2:
        return 0.0, "Thiếu thông tin tên tài sản", {}

    res = detailed_fuzzy_match(s1, s2, alias_table="item")
    score = res.score
    if score >= 99.9:
        reason = f"Tên tài sản trùng khớp hoàn toàn ('{s1}')"
    elif score >= 85.0:
        reason = f"Tên tài sản tương đồng rất cao ({score}%)"
    else:
        reason = f"Tên tài sản tương đồng ({score}%)"

    return (
        score,
        reason,
        {
            "token_sort_ratio": res.breakdown.token_sort_ratio,
            "token_set_ratio": res.breakdown.token_set_ratio,
            "levenshtein_ratio": res.breakdown.levenshtein_ratio,
        },
    )


def score_category(
    cat_id_a: Any = None,
    cat_id_b: Any = None,
    cat_name_a: str | None = None,
    cat_name_b: str | None = None,
) -> tuple[float, str, dict[str, Any]]:
    if cat_id_a and cat_id_b:
        if str(cat_id_a).strip() == str(cat_id_b).strip():
            return (
                100.0,
                f"Cùng danh mục ({cat_name_a or cat_id_a})",
                {"matched": True},
            )
        return 0.0, "Khác danh mục tài sản", {"matched": False}
    if cat_name_a and cat_name_b:
        if normalize(cat_name_a) == normalize(cat_name_b):
            return 100.0, f"Cùng tên danh mục ('{cat_name_a}')", {"matched": True}
        return 0.0, "Khác danh mục tài sản", {"matched": False}
    return 0.0, "Không đủ thông tin danh mục", {"matched": False}


def score_color(
    color_a: str | None = None, color_b: str | None = None
) -> tuple[float, str, dict[str, Any]]:
    c1, c2 = (color_a or "").strip(), (color_b or "").strip()
    if not c1 or not c2:
        reason = (
            "Cả hai không khai báo màu (điểm trung tính 50%)"
            if not c1 and not c2
            else f"Một bên không cung cấp màu ('{c1 or c2}', điểm trung tính 50%)"
        )
        return COLOR_NEUTRAL_SCORE, reason, {"neutral": True}

    score = detailed_fuzzy_match(c1, c2, alias_table="color").score
    if score >= 99.9:
        reason = f"Màu sắc trùng khớp hoàn toàn ('{c1}' / '{c2}')"
    elif score >= 70.0:
        reason = f"Màu sắc tương đồng ({score}%)"
    else:
        reason = f"Màu sắc không tương đồng ({score}%)"
    return score, reason, {"fuzzy_score": score}


def score_location(
    loc_id_a: Any = None,
    loc_id_b: Any = None,
    loc_name_a: str | None = None,
    loc_name_b: str | None = None,
) -> tuple[float, str, dict[str, Any]]:
    if loc_id_a and loc_id_b:
        if str(loc_id_a).strip() == str(loc_id_b).strip():
            return (
                100.0,
                f"Cùng địa điểm ({loc_name_a or loc_id_a})",
                {"matched": True},
            )
        return 0.0, "Khác địa điểm thất lạc và nhặt được", {"matched": False}
    if loc_name_a and loc_name_b:
        score = detailed_fuzzy_match(loc_name_a, loc_name_b).score
        if score >= 80.0:
            return (
                score,
                f"Địa điểm tương đồng cao ({score}%)",
                {"matched": True, "fuzzy_score": score},
            )
        return (
            0.0,
            f"Khác địa điểm ('{loc_name_a}' vs '{loc_name_b}')",
            {"matched": False},
        )
    return (
        LOCATION_NEUTRAL_SCORE,
        "Thiếu địa điểm (điểm trung tính 50%)",
        {"neutral": True},
    )


def score_time(
    time_a: datetime | None, time_b: datetime | None
) -> tuple[float, str, dict[str, Any]]:
    if not time_a or not time_b:
        return (
            TIME_NEUTRAL_SCORE,
            "Không xác định mốc thời gian (điểm trung tính 50%)",
            {"neutral": True},
        )

    t_a = time_a.replace(tzinfo=UTC) if time_a.tzinfo is None else time_a
    t_b = time_b.replace(tzinfo=UTC) if time_b.tzinfo is None else time_b
    diff_sec = abs((t_b - t_a).total_seconds())
    diff_days = diff_sec / 86400.0

    if diff_days <= MAX_TIME_DIFF_DAYS:
        score = round(100.0 * (1.0 - diff_days / MAX_TIME_DIFF_DAYS), 2)
        return (
            score,
            f"Thời gian xảy ra cách nhau {round(diff_days, 1)} ngày ({score}% khớp)",
            {"diff_seconds": diff_sec, "diff_days": diff_days},
        )
    return (
        0.0,
        f"Thời gian chênh lệch quá xa ({round(diff_days, 1)} ngày, vượt ngưỡng 14 ngày)",
        {"diff_seconds": diff_sec, "diff_days": diff_days},
    )


def calculate_match_score(lost: Any, found: Any) -> MatchScoreResult:
    results = {
        "name": (
            WEIGHT_NAME,
            score_name(
                _extract_val(lost, "item_name"), _extract_val(found, "item_name")
            ),
        ),
        "category": (
            WEIGHT_CATEGORY,
            score_category(
                _extract_val(lost, "category_id"),
                _extract_val(found, "category_id"),
                _extract_val(lost, "category_name"),
                _extract_val(found, "category_name"),
            ),
        ),
        "color": (
            WEIGHT_COLOR,
            score_color(_extract_val(lost, "color"), _extract_val(found, "color")),
        ),
        "location": (
            WEIGHT_LOCATION,
            score_location(
                _extract_val(lost, "location_id"),
                _extract_val(found, "location_id"),
                _extract_val(lost, "location_name"),
                _extract_val(found, "location_name"),
            ),
        ),
        "time": (
            WEIGHT_TIME,
            score_time(
                _extract_val(lost, "lost_at") or _extract_val(lost, "timestamp"),
                _extract_val(found, "found_at") or _extract_val(found, "timestamp"),
            ),
        ),
    }

    components = {
        key: ComponentScore(
            score=score,
            weight=weight,
            weighted_score=round(score * weight, 2),
            reason=reason,
            details=details,
        )
        for key, (weight, (score, reason, details)) in results.items()
    }

    total = round(sum(score * weight for weight, (score, _, _) in results.values()), 2)
    level = get_match_level(total)
    if results["name"][1][0] < NAME_MIN_SCORE:
        level = MatchLevel.LOW

    return MatchScoreResult(
        total_score=total,
        level=level,
        reasons=[comp.reason for comp in components.values()],
        breakdown=MatchScoreBreakdown(**components),
        algorithm_version=ALGORITHM_VERSION,
    )
