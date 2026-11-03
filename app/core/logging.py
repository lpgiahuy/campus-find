import logging
import re
import sys
from app.core.config import settings

# Regex tìm kiếm và che giấu các trường nhạy cảm trong log
SENSITIVE_PATTERNS = [
    (re.compile(r"(password['\"]?\s*[:=]\s*['\"])([^'\"]+)(['\"])", re.IGNORECASE), r"\1******\3"),
    (re.compile(r"(token['\"]?\s*[:=]\s*['\"])([^'\"]+)(['\"])", re.IGNORECASE), r"\1******\3"),
    (re.compile(r"(secret['\"]?\s*[:=]\s*['\"])([^'\"]+)(['\"])", re.IGNORECASE), r"\1******\3"),
    (re.compile(r"(authorization:\s*bearer\s+)([a-zA-Z0-9\-_.]+)", re.IGNORECASE), r"\1******"),
]


class SafeLogFilter(logging.Filter):
    """Filter bảo mật nhằm tự động mask các thông tin nhạy cảm (passwords, tokens, PII)."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for pattern, repl in SENSITIVE_PATTERNS:
                record.msg = pattern.sub(repl, record.msg)
        return True


def setup_logging() -> None:
    """Khởi tạo cấu hình logging toàn hệ thống."""
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(SafeLogFilter())
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Giảm mức ồn của các thư viện thứ 3
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.DEBUG else logging.WARN
    )
