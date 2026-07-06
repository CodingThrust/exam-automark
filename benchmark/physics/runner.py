import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .gold import SCORE_FIELDS
from .schema import ProviderResult


class ValidationFailure(ValueError):
    def __init__(
        self,
        message: str,
        *,
        result: ProviderResult | None = None,
    ):
        super().__init__(message)
        self.result = result


def create_run_directory(
    root: Path,
    run_id: str,
    manifest: dict[str, Any] | None = None,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    run_dir = root / run_id
    if run_dir.exists():
        raise FileExistsError(f"run directory already exists: {run_dir}")
    run_dir.mkdir(exist_ok=False)

    manifest_data = dict(manifest or {})
    manifest_data.setdefault("run_id", run_id)
    manifest_data.setdefault("start_time", _utc_now())
    manifest_data.setdefault("end_time", None)
    manifest_data.setdefault("usage", {})

    (run_dir / "manifest.json").write_text(
        json.dumps(manifest_data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (run_dir / "predictions.csv").open("w", newline="", encoding="utf-8") as handle:
        csv.DictWriter(handle, fieldnames=SCORE_FIELDS).writeheader()
    (run_dir / "raw_responses.jsonl").write_text("", encoding="utf-8")
    (run_dir / "failures.jsonl").write_text("", encoding="utf-8")
    return run_dir


def run_student_with_retries(
    run_dir: Path,
    student_id: str,
    operation: Callable[[int], ProviderResult],
    *,
    max_retries: int = 2,
) -> ProviderResult | None:
    attempt = 1
    validation_repaired = False
    while True:
        try:
            result = operation(attempt)
        except ValidationFailure as error:
            if not validation_repaired:
                validation_repaired = True
                _append_attempt(
                    run_dir,
                    student_id,
                    attempt,
                    "repair",
                    result=error.result,
                    error=error,
                )
                attempt += 1
                continue
            _record_missing(run_dir, student_id, attempt, error)
            return None
        except Exception as error:
            if _is_retryable_error(error) and attempt <= max_retries:
                _append_attempt(run_dir, student_id, attempt, "retry", error=error)
                attempt += 1
                continue
            _record_missing(run_dir, student_id, attempt, error)
            return None

        _append_attempt(run_dir, student_id, attempt, "ok", result=result)
        return result


def _record_missing(
    run_dir: Path,
    student_id: str,
    attempt: int,
    error: Exception,
) -> None:
    result = error.result if isinstance(error, ValidationFailure) else None
    _append_attempt(
        run_dir,
        student_id,
        attempt,
        "failed",
        result=result,
        error=error,
    )
    _append_jsonl(
        run_dir / "failures.jsonl",
        {
            "student_id": student_id,
            "status": "missing",
            "attempts": attempt,
            "error_type": type(error).__name__,
            "error": str(error),
        },
    )


def _append_attempt(
    run_dir: Path,
    student_id: str,
    attempt: int,
    status: str,
    *,
    result: ProviderResult | None = None,
    error: Exception | None = None,
) -> None:
    row: dict[str, Any] = {
        "student_id": student_id,
        "attempt": attempt,
        "status": status,
        "timestamp": _utc_now(),
    }
    if result is not None:
        row.update(
            {
                "model": result.model,
                "raw_text": result.raw_text,
                "usage": result.usage,
                "system_fingerprint": result.system_fingerprint,
            }
        )
    if error is not None:
        row.update({"error_type": type(error).__name__, "error": str(error)})
    _append_jsonl(run_dir / "raw_responses.jsonl", row)


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def _is_retryable_error(error: Exception) -> bool:
    if _error_code(error) == "insufficient_quota":
        return False
    status_code = getattr(error, "status_code", None)
    if status_code == 429 or (isinstance(status_code, int) and status_code >= 500):
        return True
    error_name = type(error).__name__.lower()
    if "ratelimit" in error_name or "server" in error_name:
        return True
    return isinstance(error, (TimeoutError, ConnectionError))


def _error_code(error: Exception) -> str | None:
    code = getattr(error, "code", None)
    if isinstance(code, str):
        return code
    body = getattr(error, "body", None)
    if isinstance(body, dict):
        nested = body.get("error", body)
        if isinstance(nested, dict) and isinstance(nested.get("code"), str):
            return nested["code"]
    return None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
