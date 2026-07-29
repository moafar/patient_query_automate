import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


LOG_DIR = Path(r"C:\patient_query_automate\logs")


@dataclass(frozen=True)
class LoggingContext:
    logger: logging.Logger
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


def unique_log_path(log_dir: Path, extractor: str, timestamp: str) -> Path:
    base_path = log_dir / f"{extractor}_{timestamp}.log"
    if not base_path.exists():
        return base_path

    counter = 1
    while True:
        candidate = log_dir / f"{extractor}_{timestamp}_{counter:02d}.log"
        if not candidate.exists():
            return candidate
        counter += 1


def setup_logging(
    extractor: str,
    log_dir: Path = LOG_DIR,
    now: datetime | None = None,
) -> LoggingContext:
    started_at = now or datetime.now()
    timestamp = started_at.strftime("%Y%m%d_%H%M%S")
    safe_extractor = sanitize_filename(extractor)

    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = unique_log_path(log_dir, safe_extractor, timestamp)
    run_suffix = log_path.stem.removeprefix(f"{safe_extractor}_")
    run_id = run_suffix.replace("_", "T", 1)

    logger_name = f"patient_query.{run_id}.{safe_extractor}"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.handlers.clear()

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

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return LoggingContext(logger=logger, run_id=run_id, log_path=log_path)
