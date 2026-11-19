"""Chuẩn hóa chữ tự do (tên đồ, màu) để so khớp — không dùng để lưu DB."""

import re

from unidecode import unidecode

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize(text: str | None) -> str:
    """Chuỗi so khớp: không dấu, chữ thường, chỉ a-z0-9, cách nhau đúng 1 khoảng trắng.

    unidecode xử lý được cả NFD và "đ" nên không cần bước NFC riêng.
    """
    if not text:
        return ""
    return _NON_ALNUM.sub(" ", unidecode(text).lower()).strip()
