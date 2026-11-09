"""Từ đồng nghĩa / viết tắt / tiếng Anh cho tên đồ và màu (task #8).

Thêm từ: thêm biến thể (viết có dấu cũng được) vào nhóm của từ chuẩn.
Quy tắc: từ chuẩn không được chứa biến thể nào — test kiểm tra cả bảng.
"""

import re
from collections.abc import Mapping

from app.modules.matching.engine.normalizer import normalize

# Không alias từ một âm tiết dễ va chạm sau khi bỏ dấu (ô / dù, ví / vì).
_ITEM_GROUPS = {
    "balo": ["ba lô", "balô", "backpack", "cặp đeo lưng"],
    "tai nghe": [
        "airpods",
        "earphone",
        "earphones",
        "earbuds",
        "headphone",
        "headphones",
        "tai phone",
    ],
    "dien thoai": ["đt", "điện thoại di động", "smartphone", "phone"],
    "laptop": ["máy tính xách tay", "notebook", "macbook"],
    "sac": ["củ sạc", "cục sạc", "charger"],
    "sac du phong": ["pin dự phòng", "power bank"],
    "vi": ["bóp", "ví tiền", "wallet"],
    # "móc khóa" không gộp: có thể chỉ là móc treo.
    "chia khoa": ["chùm chìa khóa", "key"],
    "the sinh vien": ["thẻ sv", "student card"],
    "can cuoc": [
        "cccd",
        "cmnd",
        "căn cước công dân",
        "chứng minh nhân dân",
        "chứng minh thư",
    ],
    "binh nuoc": ["bình giữ nhiệt", "chai nước"],
    "cay du": ["cây ô", "umbrella"],
    "kinh": ["mắt kính", "kính mắt", "glasses"],
    "chuot": ["chuột máy tính", "mouse"],
}

# Tách khỏi bảng tên đồ: "ghi" = xám chỉ đúng với màu ("sổ ghi chép").
_COLOR_GROUPS = {
    "den": ["black"],
    "trang": ["white"],
    "do": ["red"],
    "xanh duong": ["xanh dương", "xanh biển", "xanh nước biển", "blue"],
    "xanh la": ["xanh lá cây", "green"],
    "xam": ["ghi", "bạc", "gray", "grey", "silver"],
    "vang": ["vàng đồng", "yellow", "gold"],
    "cam": ["orange"],
    "hong": ["pink"],
    "nau": ["brown"],
    "tim": ["purple"],
}


def _build(groups: dict[str, list[str]]) -> dict[str, str]:
    """{từ chuẩn: [biến thể]} → {biến thể đã normalize: từ chuẩn đã normalize}."""
    table = {}
    for canonical, variants in groups.items():
        canonical = normalize(canonical)
        for variant in variants:
            if (key := normalize(variant)) != canonical:
                table[key] = canonical
    return table


ITEM_ALIASES: dict[str, str] = _build(_ITEM_GROUPS)
COLOR_ALIASES: dict[str, str] = _build(_COLOR_GROUPS)


def apply_aliases(text: str | None, table: Mapping[str, str]) -> str:
    """normalize() rồi thay biến thể bằng từ chuẩn; truyền chuỗi gốc hay đã normalize đều được."""
    text = normalize(text)  # idempotent nên gọi lại trên chuỗi đã normalize vẫn đúng
    if not text or not table:
        return text
    # Cụm dài thử trước: "pin du phong" thắng "sac"; thay một lượt nên không dây chuyền.
    # re tự cache pattern đã biên dịch theo chuỗi pattern.
    keys = sorted(table, key=len, reverse=True)
    pattern = r"\b(?:" + "|".join(map(re.escape, keys)) + r")\b"
    return re.sub(pattern, lambda m: table[m.group()], text)
