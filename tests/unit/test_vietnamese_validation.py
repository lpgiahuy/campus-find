import unicodedata

import pytest

from app.shared.utils import (
    escape_like_term,
    normalize_vietnamese_text,
    validate_vietnamese_name,
    validate_vietnamese_title,
)


def test_normalize_vietnamese_nfd_to_nfc():
    nfd_text = unicodedata.normalize("NFD", "Nguyễn Văn A - Giảng đường")
    assert any(unicodedata.combining(c) for c in nfd_text)

    normalized = normalize_vietnamese_text(nfd_text)
    assert not any(unicodedata.combining(c) for c in normalized)
    assert normalized == "Nguyễn Văn A - Giảng đường"


def test_normalize_vietnamese_whitespace():
    raw = "   Trần   Văn   B   "
    assert normalize_vietnamese_text(raw) == "Trần Văn B"


def test_normalize_vietnamese_preserve_newlines():
    raw = "  Dòng 1  \n\nDòng 2  \n  Dòng 3  "
    normalized = normalize_vietnamese_text(raw, preserve_newlines=True)
    assert normalized == "Dòng 1  \n\nDòng 2  \n  Dòng 3"


def test_escape_like_term():
    assert escape_like_term("normal text") == "normal text"
    assert escape_like_term("100%_safe\\path") == "100\\%\\_safe\\\\path"


@pytest.mark.parametrize(
    "name",
    [
        "Nguyễn Văn A",
        "Trần Thị Bích Ngọc",
        "Lê-Phạm Gia Huy",
        "Đỗ Hoàng O'Connor",
        "Vũ Đình Đạt",
    ],
)
def test_validate_vietnamese_name_valid(name: str):
    assert validate_vietnamese_name(name) == name


@pytest.mark.parametrize(
    "name",
    [
        "A",
        "Nguyễn Văn A123",
        "Trần <script>",
        "Hoàng @#$",
        "   ",
        "B" * 151,
    ],
)
def test_validate_vietnamese_name_invalid(name: str):
    with pytest.raises(ValueError):
        validate_vietnamese_name(name)


@pytest.mark.parametrize(
    "title",
    [
        "Điện thoại",
        "Giấy tờ & Thẻ sinh viên",
        "Giảng đường B1.12",
        "Căn tin A (Tòa C)",
        "Khu tự học - Tầng 2",
    ],
)
def test_validate_vietnamese_title_valid(title: str):
    assert validate_vietnamese_title(title, field_name="Danh mục") == title


@pytest.mark.parametrize(
    "title",
    [
        "A",
        "---",
        "...",
        "()//",
        "   ",
        "C" * 151,
    ],
)
def test_validate_vietnamese_title_invalid(title: str):
    with pytest.raises(ValueError):
        validate_vietnamese_title(title, field_name="Danh mục")
