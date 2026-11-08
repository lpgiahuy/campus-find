import re
import unicodedata

import pytest

from app.modules.matching.engine.aliases import (
    COLOR_ALIASES,
    ITEM_ALIASES,
    apply_aliases,
)
from app.modules.matching.engine.normalizer import normalize

# ---------- normalize ----------

NORMALIZE_CASES = [
    ("  Ví   DA  Nâu ", "vi da nau"),
    ("Đồng hồ", "dong ho"),
    ("khóa", "khoa"),
    ("khoá", "khoa"),
    ("iPhone-13, màu ĐEN!", "iphone 13 mau den"),
    ("Thẻ SV\nNguyễn Văn A", "the sv nguyen van a"),
    (None, ""),
    ("", ""),
    ("   ", ""),
    ("!!!", ""),
]


@pytest.mark.parametrize(("text", "expected"), NORMALIZE_CASES)
def test_normalize(text, expected):
    assert normalize(text) == expected


def test_normalize_nfc_and_nfd_equal():
    text = "Ví da nâu Nguyễn"
    nfd = unicodedata.normalize("NFD", text)
    assert nfd != text
    assert normalize(nfd) == normalize(text) == "vi da nau nguyen"


@pytest.mark.parametrize(("text", "_"), NORMALIZE_CASES)
def test_normalize_idempotent(text, _):
    once = normalize(text)
    assert normalize(once) == once


# ---------- apply_aliases ----------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Cái Ba Lô đen", "cai balo den"),
        ("balô", "balo"),
        ("AirPods Pro", "tai nghe pro"),
        ("Thẻ SV", "the sinh vien"),
        ("CCCD", "can cuoc"),
        ("pin dự phòng", "sac du phong"),  # cụm dài khớp trước "sac"
        ("cục sạc laptop", "sac laptop"),
        ("balomini", "balomini"),  # chỉ thay theo biên từ
        ("", ""),
    ],
)
def test_apply_item_aliases(text, expected):
    assert apply_aliases(normalize(text), ITEM_ALIASES) == expected


def test_color_alias_not_applied_to_item_name():
    # "ghi" = xám chỉ đúng với màu; tên đồ phải giữ nguyên.
    assert apply_aliases(normalize("sổ ghi chép"), ITEM_ALIASES) == "so ghi chep"
    assert apply_aliases(normalize("Ghi"), COLOR_ALIASES) == "xam"
    assert apply_aliases(normalize("Xanh nước biển"), COLOR_ALIASES) == "xanh duong"
    assert apply_aliases(normalize("BLACK"), COLOR_ALIASES) == "den"


@pytest.mark.parametrize("table", [ITEM_ALIASES, COLOR_ALIASES])
def test_alias_table_is_normalized_and_idempotent(table):
    """Từ chuẩn không chứa biến thể nào → gọi 2 lần ra cùng kết quả, không thay dây chuyền."""
    for variant, canonical in table.items():
        assert variant == normalize(variant)
        assert canonical == normalize(canonical)
        assert variant != canonical
        for other in table:
            assert not re.search(
                rf"\b{re.escape(other)}\b", canonical
            ), f"{canonical!r} (từ chuẩn của {variant!r}) chứa biến thể {other!r}"
        once = apply_aliases(variant, table)
        assert once == canonical
        assert apply_aliases(once, table) == once
