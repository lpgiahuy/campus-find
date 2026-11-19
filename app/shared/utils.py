import math
import re
import unicodedata
from contextlib import asynccontextmanager

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ConflictError

VIETNAMESE_NAME_PATTERN = re.compile(
    r"^[a-zA-Z\sàáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴĐ'\-]+$"
)

VIETNAMESE_TITLE_PATTERN = re.compile(
    r"^[a-zA-Z0-9\sàáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴĐ'\-.,/()_&]+$"
)

VIETNAMESE_LETTER_OR_DIGIT_PATTERN = re.compile(
    r"[a-zA-Z0-9àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴĐ]"
)


def normalize_vietnamese_text(text: str, preserve_newlines: bool = False) -> str:
    if not text:
        return text
    normalized = unicodedata.normalize("NFC", text)
    if preserve_newlines:
        return normalized.strip()
    return re.sub(r"\s+", " ", normalized).strip()


def escape_like_term(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def calculate_total_pages(total: int, page_size: int) -> int:
    return math.ceil(total / page_size) if total > 0 else 0


@asynccontextmanager
async def handle_unique_violation(message: str):
    try:
        yield
    except IntegrityError as exc:
        if getattr(exc.orig, "sqlstate", None) == "23505":
            raise ConflictError(message) from exc
        raise


def validate_vietnamese_name(value: str, min_len: int = 2, max_len: int = 150) -> str:
    cleaned = normalize_vietnamese_text(value)
    if len(cleaned) < min_len or len(cleaned) > max_len:
        raise ValueError(f"Họ và tên phải có độ dài từ {min_len} đến {max_len} ký tự.")
    if not VIETNAMESE_NAME_PATTERN.match(cleaned):
        raise ValueError(
            "Họ và tên chỉ được chứa chữ cái tiếng Việt, dấu cách, dấu gạch nối hoặc dấu nháy đơn."
        )
    return cleaned


def validate_vietnamese_title(
    value: str, field_name: str = "Tên", min_len: int = 2, max_len: int = 150
) -> str:
    cleaned = normalize_vietnamese_text(value)
    if len(cleaned) < min_len or len(cleaned) > max_len:
        raise ValueError(
            f"{field_name} phải có độ dài từ {min_len} đến {max_len} ký tự."
        )
    if not VIETNAMESE_TITLE_PATTERN.match(cleaned):
        raise ValueError(
            f"{field_name} chỉ được chứa chữ cái tiếng Việt, chữ số, dấu cách và các ký tự phân cách cơ bản."
        )
    if not VIETNAMESE_LETTER_OR_DIGIT_PATTERN.search(cleaned):
        raise ValueError(f"{field_name} phải chứa ít nhất một chữ cái hoặc chữ số.")
    return cleaned
