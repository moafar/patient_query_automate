import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


LOG_DIR = Path(r"C:\patient_query_automate\logs")


@dataclass(frozen=True)
class LoggingContext:
    logger: logging.LoggerAdapter
    run_id: str
    log_path: Path


class ContextFilter(logging.Filter):
    def __init__(self, run_id: str, extractor: str) -> None:
        super().__init__()
        self.run_id = run_id
        self.extractor = extractor

    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = getattr(record, "run_id", self.run_id)
        record.extractor = getattr(record, "extractor", self.extractor)
        record.phase = getattr(record, "phase", "general")
        return True


def sanitize_filename(value: str) -> str:
    sanitized = re.sub(r'[^A-Za-z0-9_.-]+', "_", value).strip("._")
    return sanitized or "extractor"


def setup_logging(
    extractor: str,
    log_dir: Path = LOG_DIR,
    now: datetime | None = None,
) -> LoggingContext:
    started_at = now or datetime.now()
    timestamp = started_at.strftime("%Y%m%d_%H%M%S")
    run_id = started_at.strftime("%Y%m%dT%H%M%S")
    safe_extractor = sanitize_filename(extractor)

    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{safe_extractor}_{timestamp}.log"

    logger_name = f"patient_query.{run_id}.{safe_extractor}"
    base_logger = logging.getLogger(logger_name)
    base_logger.setLevel(logging.DEBUG)
    base_logger.propagate = False
    base_logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | run_id=%(run_id)s | "
        "extractor=%(extractor)s | phase=%(phase)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    context_filter = ContextFilter(run_id=run_id, extractor=extractor)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(context_filter)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(context_filter)

    base_logger.addHandler(console_handler)
    base_logger.addHandler(file_handler)

    adapter = logging.LoggerAdapter(base_logger, {})
    return LoggingContext(logger=adapter, run_id=run_id, log_path=log_path)
