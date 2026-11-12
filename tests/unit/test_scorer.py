from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.db.models import FoundReport, LostReport
from app.modules.matching.engine.scorer import (
    ALGORITHM_VERSION,
    COLOR_NEUTRAL_SCORE,
    LOCATION_NEUTRAL_SCORE,
    MAX_TIME_DIFF_DAYS,
    NAME_MIN_SCORE,
    THRESHOLD_HIGH,
    THRESHOLD_MEDIUM,
    TIME_NEUTRAL_SCORE,
    WEIGHT_CATEGORY,
    WEIGHT_COLOR,
    WEIGHT_LOCATION,
    WEIGHT_NAME,
    WEIGHT_TIME,
    calculate_match_score,
    get_match_level,
    score_category,
    score_color,
    score_location,
    score_name,
    score_time,
)
from app.modules.matching.schemas import MatchItemInput
from app.shared.enums import MatchLevel


def test_weights_sum_to_one():
    total_weights = (
        WEIGHT_NAME + WEIGHT_CATEGORY + WEIGHT_COLOR + WEIGHT_LOCATION + WEIGHT_TIME
    )
    assert total_weights == pytest.approx(1.0, rel=1e-6)
    assert WEIGHT_NAME == 0.35
    assert WEIGHT_CATEGORY == 0.25
    assert WEIGHT_COLOR == 0.15
    assert WEIGHT_LOCATION == 0.15
    assert WEIGHT_TIME == 0.10


def test_threshold_constants():
    assert THRESHOLD_HIGH == 80.0
    assert THRESHOLD_MEDIUM == 60.0
    assert MAX_TIME_DIFF_DAYS == 14.0
    assert ALGORITHM_VERSION == "rules-v1"


@pytest.mark.parametrize(
    ("score", "expected_level"),
    [
        (100.0, MatchLevel.HIGH),
        (85.5, MatchLevel.HIGH),
        (80.0, MatchLevel.HIGH),
        (79.99, MatchLevel.MEDIUM),
        (70.0, MatchLevel.MEDIUM),
        (60.0, MatchLevel.MEDIUM),
        (59.99, MatchLevel.LOW),
        (35.0, MatchLevel.LOW),
        (0.0, MatchLevel.LOW),
    ],
)
def test_get_match_level_thresholds(score: float, expected_level: MatchLevel):
    assert get_match_level(score) == expected_level


def test_score_name_exact_match():
    score, reason, details = score_name("Ví da Pedro", "Ví da Pedro")
    assert score == 100.0
    assert "trùng khớp hoàn toàn" in reason
    assert details["token_sort_ratio"] == 100.0


def test_score_name_alias_and_diacritics():
    score, reason, _ = score_name("AirPods Pro", "tai nghe pro")
    assert score == 100.0
    assert "trùng khớp hoàn toàn" in reason or "tương đồng rất cao" in reason


def test_score_name_typo():
    score, reason, _ = score_name("bluetoth", "bluetooth")
    assert score >= 90.0
    assert "tương đồng rất cao" in reason


def test_score_name_empty_or_none():
    score, reason, _ = score_name("", "Ví da")
    assert score == 0.0
    assert "Thiếu thông tin" in reason

    score_none, reason_none, _ = score_name(None, None)
    assert score_none == 0.0
    assert "Thiếu thông tin" in reason_none


def test_score_category_same_id():
    cat_id = uuid4()
    score, reason, details = score_category(cat_id, cat_id, "Điện tử", "Điện tử")
    assert score == 100.0
    assert "Cùng danh mục" in reason
    assert details["matched"] is True


def test_score_category_different_id():
    score, reason, details = score_category(uuid4(), uuid4(), "Điện tử", "Giấy tờ")
    assert score == 0.0
    assert "Khác danh mục" in reason
    assert details["matched"] is False


def test_score_category_id_vs_name_only_lacks_info():
    score, reason, _ = score_category(uuid4(), None, None, "Điện tử")
    assert score == 0.0
    assert "Không đủ thông tin" in reason


def test_score_category_name_only():
    score, reason, _ = score_category(None, None, "Điện tử", "điện tử")
    assert score == 100.0
    assert "Cùng tên danh mục" in reason

    score_diff, reason_diff, _ = score_category(None, None, "Điện tử", "Giấy tờ")
    assert score_diff == 0.0
    assert "Khác danh mục" in reason_diff


def test_score_category_missing_both():
    score, reason, _ = score_category(None, None, None, None)
    assert score == 0.0
    assert "Không đủ thông tin" in reason


def test_score_color_exact_and_alias():
    score, reason, _ = score_color("black", "đen")
    assert score == 100.0
    assert "trùng khớp hoàn toàn" in reason


def test_score_color_different():
    score, reason, _ = score_color("đỏ", "xanh lá")
    assert score < 50.0
    assert "không tương đồng" in reason


def test_score_color_missing_neutral():
    score_both, reason_both, det_both = score_color(None, None)
    assert score_both == COLOR_NEUTRAL_SCORE
    assert det_both["neutral"] is True
    assert "điểm trung tính" in reason_both

    score_one, reason_one, det_one = score_color("đen", None)
    assert score_one == COLOR_NEUTRAL_SCORE
    assert det_one["neutral"] is True
    assert "Một bên không cung cấp" in reason_one


def test_score_location_same_id():
    loc_id = uuid4()
    score, reason, details = score_location(loc_id, loc_id, "Thư viện", "Thư viện")
    assert score == 100.0
    assert "Cùng địa điểm" in reason
    assert details["matched"] is True


def test_score_location_different_id():
    score, reason, details = score_location(uuid4(), uuid4(), "Thư viện", "Căn tin")
    assert score == 0.0
    assert "Khác địa điểm" in reason
    assert details["matched"] is False


def test_score_location_different_id_same_name():
    score, _, details = score_location(uuid4(), uuid4(), "Thư viện", "Thư viện")
    assert score == 0.0
    assert details["matched"] is False


def test_score_location_id_vs_name_only_is_neutral():
    score, _, details = score_location(uuid4(), None, None, "Thư viện")
    assert score == LOCATION_NEUTRAL_SCORE
    assert details["neutral"] is True


def test_score_location_name_fuzzy():
    score, reason, _ = score_location(None, None, "Tòa A", "Khu Tòa A")
    assert score >= 80.0
    assert "Địa điểm tương đồng" in reason


def test_score_location_missing_neutral():
    score, reason, details = score_location(None, None, None, None)
    assert score == LOCATION_NEUTRAL_SCORE
    assert details["neutral"] is True
    assert "điểm trung tính" in reason


def test_score_time_exact():
    now = datetime.now(UTC)
    score, reason, _ = score_time(now, now)
    assert score == 100.0
    assert "cách nhau 0.0 ngày" in reason


def test_score_time_within_one_day():
    now = datetime.now(UTC)
    one_day_later = now + timedelta(days=1)
    score, reason, details = score_time(now, one_day_later)
    assert score == pytest.approx(92.86, abs=0.1)
    assert details["diff_days"] == pytest.approx(1.0, abs=0.05)
    assert "cách nhau" in reason


def test_score_time_half_window():
    now = datetime.now(UTC)
    seven_days = now + timedelta(days=7)
    score, _, _ = score_time(now, seven_days)
    assert score == pytest.approx(50.0, abs=0.1)


def test_score_time_boundary_14_days():
    now = datetime.now(UTC)
    fourteen_days = now + timedelta(days=14)
    score, _, _ = score_time(now, fourteen_days)
    assert score == 0.0


def test_score_time_exceeds_14_days():
    now = datetime.now(UTC)
    far_future = now + timedelta(days=20)
    score, reason, _ = score_time(now, far_future)
    assert score == 0.0
    assert "vượt ngưỡng 14 ngày" in reason


def test_score_time_timezone_mixed():
    naive = datetime(2026, 11, 10, 10, 0, 0)
    aware = datetime(2026, 11, 10, 10, 0, 0, tzinfo=UTC)
    score, _, details = score_time(naive, aware)
    assert score == 100.0
    assert details["diff_seconds"] == 0.0


def test_score_time_missing_neutral():
    score, reason, details = score_time(None, datetime.now(UTC))
    assert score == TIME_NEUTRAL_SCORE
    assert details["neutral"] is True


def test_calculate_match_score_high_match():
    now = datetime.now(UTC)
    cat_id = uuid4()
    loc_id = uuid4()

    lost = MatchItemInput(
        item_name="Ví da nam Pedro",
        category_id=cat_id,
        category_name="Phụ kiện",
        color="đen",
        location_id=loc_id,
        location_name="Thư viện",
        timestamp=now,
    )
    found = MatchItemInput(
        item_name="Bóp da Pedro",
        category_id=cat_id,
        category_name="Phụ kiện",
        color="black",
        location_id=loc_id,
        location_name="Thư viện",
        timestamp=now + timedelta(hours=3),
    )

    result = calculate_match_score(lost, found)

    assert result.total_score >= 80.0
    assert result.level == MatchLevel.HIGH
    assert len(result.reasons) == 5
    assert result.algorithm_version == "rules-v1"

    bd = result.breakdown
    assert bd.name.weight == 0.35
    assert bd.category.weight == 0.25
    assert bd.color.weight == 0.15
    assert bd.location.weight == 0.15
    assert bd.time.weight == 0.10

    assert bd.category.score == 100.0
    assert bd.color.score == 100.0
    assert bd.location.score == 100.0


def test_calculate_match_score_medium_match():
    now = datetime.now(UTC)
    cat_id = uuid4()

    lost = {
        "item_name": "Tai nghe AirPods Pro",
        "category_id": cat_id,
        "category_name": "Điện tử",
        "color": None,
        "location_id": uuid4(),
        "location_name": "Tòa A",
        "timestamp": now,
    }
    found = {
        "item_name": "Tai nghe bluetooth không dây",
        "category_id": cat_id,
        "category_name": "Điện tử",
        "color": None,
        "location_id": uuid4(),
        "location_name": "Căn tin",
        "timestamp": now + timedelta(days=2),
    }

    result = calculate_match_score(lost, found)

    assert 60.0 <= result.total_score < 80.0
    assert result.level == MatchLevel.MEDIUM
    assert len(result.reasons) == 5


def test_calculate_match_score_low_match():
    now = datetime.now(UTC)

    lost = {
        "item_name": "Balo laptop ASUS",
        "category_id": uuid4(),
        "category_name": "Phụ kiện",
        "color": "đỏ",
        "location_id": uuid4(),
        "location_name": "Sân bóng",
        "timestamp": now,
    }
    found = {
        "item_name": "Thẻ sinh viên UIT",
        "category_id": uuid4(),
        "category_name": "Giấy tờ",
        "color": "xanh",
        "location_id": uuid4(),
        "location_name": "Thư viện",
        "timestamp": now + timedelta(days=12),
    }

    result = calculate_match_score(lost, found)

    assert result.total_score < 60.0
    assert result.level == MatchLevel.LOW


def test_calculate_match_score_with_orm_models():
    now = datetime.now(UTC)
    cat_id = uuid4()
    loc_id = uuid4()
    user1 = uuid4()
    user2 = uuid4()

    lost_model = LostReport(
        user_id=user1,
        category_id=cat_id,
        location_id=loc_id,
        item_name="Căn cước công dân",
        color=None,
        lost_at=now,
    )
    found_model = FoundReport(
        user_id=user2,
        category_id=cat_id,
        location_id=loc_id,
        item_name="Căn cước công dân gắn chip",
        color=None,
        found_at=now + timedelta(hours=2),
    )

    result = calculate_match_score(lost_model, found_model)

    assert result.total_score >= 80.0
    assert result.level == MatchLevel.HIGH
    assert result.breakdown.category.score == 100.0
    assert result.breakdown.location.score == 100.0


@pytest.mark.parametrize(
    ("lost_name", "found_name"),
    [("Ví da", "Chuột máy tính"), ("Ví da", "Áo khoác")],
)
def test_dissimilar_names_are_forced_low(lost_name: str, found_name: str):
    now = datetime.now(UTC)
    cat_id = uuid4()
    loc_id = uuid4()
    lost = {
        "item_name": lost_name,
        "category_id": cat_id,
        "color": "đen",
        "location_id": loc_id,
        "timestamp": now,
    }
    found = {
        "item_name": found_name,
        "category_id": cat_id,
        "color": "đen",
        "location_id": loc_id,
        "timestamp": now + timedelta(hours=3),
    }

    result = calculate_match_score(lost, found)

    assert result.breakdown.name.score < NAME_MIN_SCORE
    assert result.level == MatchLevel.LOW


def test_score_clamping_guarantees_0_to_100():
    lost = {"item_name": "Balo"}
    found = {"item_name": "Balo"}
    result = calculate_match_score(lost, found)
    assert 0.0 <= result.total_score <= 100.0
