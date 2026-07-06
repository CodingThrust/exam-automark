import csv
import json
import re
from pathlib import Path
from typing import Any


ANONYMOUS_ID = re.compile(r"^S\d{3}$")
CONDITION_LABELS = {
    "G0": "Historical direct workflow",
    "G2": "Codex Plus interactive run (automatic transcript)",
    "D1": "DeepSeek run (automatic transcript)",
    "G3": "Codex Plus interactive run (human transcript subset)",
    "D2": "DeepSeek run (human transcript subset)",
}


def render_benchmark_report(benchmark_root: Path) -> str:
    _validate_anonymous_run_ids(benchmark_root)
    metrics = {
        split: _read_optional_json(benchmark_root / f"metrics-{split}.json")
        for split in ("test", "all", "dev")
    }
    if not any(metrics.values()):
        raise ValueError("no benchmark metrics are available")

    lines = [
        "# Physics Week 9 Internal Grading Benchmark",
        "",
        "This report compares one historical direct workflow with frozen, "
        "anonymous transcript-based grading conditions.",
        "Each retained condition is represented by a single run.",
        "",
        "## Accuracy Results",
        "",
    ]
    for title, split in (
        ("Held-Out Results", "test"),
        ("Combined Results", "all"),
        ("Development Results", "dev"),
    ):
        if metrics[split] is not None:
            lines.extend(_render_metrics_section(title, metrics[split]))

    lines.extend(
        [
            "## Limitations",
            "",
            "G0 is a historical single-run baseline produced under different prompt and "
            "thread conditions; G0-to-G2 differences represent the overall workflow change. "
            "GPT-5.5 was run interactively through Codex Plus and is not a pinned API "
            "snapshot. Each retained model condition was run once, so model-run variance was "
            "not estimated. Primary human evidence and ambiguity fields were not collected.",
            "",
        ]
    )
    if any(
        item is not None
        and item.get("reference_status") == "single_primary_rater"
        for item in metrics.values()
    ):
        lines.extend(
            [
                "The score reference is a single primary-rater standard; independent human "
                "agreement is not available for this release.",
                "",
            ]
        )
    return "\n".join(lines)


def write_benchmark_report(benchmark_root: Path) -> Path:
    output = benchmark_root / "reports" / "physics_week9_benchmark.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_benchmark_report(benchmark_root), encoding="utf-8")
    return output


def _render_metrics_section(title: str, metrics: dict[str, Any]) -> list[str]:
    lines = [
        f"### {title}",
        "",
        "| Condition | Workflow | N | Population | Exact | Macro | Total MAE | "
        "Within 1 | Bias | Missing |",
        "|---|---|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    conditions = metrics.get("conditions", {})
    for condition in ("G0", "G2", "D1", "G3", "D2"):
        result = conditions.get(condition)
        if result is None:
            continue
        lines.append(
            "| {condition} | {label} | {n} | {population} | {exact} | {macro} | "
            "{mae:.3f} | {within} | {bias:+.3f} | 0 |".format(
                condition=condition,
                label=CONDITION_LABELS[condition],
                n=result["n_students"],
                population=result["population"],
                exact=_percent(result["exact_agreement"]),
                macro=_percent(result["macro_accuracy"]),
                mae=result["total_score_mae"],
                within=_percent(result["within_1_point_rate"]),
                bias=result["mean_signed_error"],
            )
        )

    paired = metrics.get("paired_vs_g0", {})
    if paired:
        lines.extend(["", "**Paired exact-agreement differences versus G0**", ""])
        for condition in ("G2", "D1"):
            interval = paired.get(condition)
            if interval is None:
                continue
            lines.append(
                f"- {condition}: {_percent(interval['mean_difference'])} "
                f"(95% bootstrap interval {_percent(interval['lower'])} to "
                f"{_percent(interval['upper'])})."
            )

    subset = [condition for condition in ("G3", "D2") if condition in conditions]
    if subset:
        lines.extend(
            [
                "",
                "**Transcript-subset comparison**",
                "",
                "G3 and D2 use only the frozen human-reviewed transcript subset and are not "
                "pooled with the full-split conditions.",
            ]
        )
        for label, comparison in metrics.get(
            "transcript_subset_comparisons", {}
        ).items():
            interval = comparison["human_minus_automatic"]
            lines.append(
                f"- {label}: automatic {comparison['automatic_condition']} "
                f"{_percent(comparison['automatic_exact_agreement'])}; human "
                f"{comparison['human_condition']} "
                f"{_percent(comparison['human_exact_agreement'])}. Human minus automatic: "
                f"{_percent(interval['mean_difference'])} (95% bootstrap interval "
                f"{_percent(interval['lower'])} to {_percent(interval['upper'])}; "
                f"N={comparison['n_students']})."
            )

    lines.extend(["", "**Anonymous error categories**", ""])
    for condition in ("G0", "G2", "D1", "G3", "D2"):
        result = conditions.get(condition)
        if result is None:
            continue
        question_accuracy = result.get("per_question_accuracy", {})
        weakest = sorted(question_accuracy.items(), key=lambda row: (row[1], row[0]))[:3]
        detail = ", ".join(
            f"{question_id} ({_percent(accuracy)} exact)"
            for question_id, accuracy in weakest
        )
        lines.append(f"- {condition}: lowest-agreement questions were {detail}.")
    lines.append("")
    return lines


def _validate_anonymous_run_ids(benchmark_root: Path) -> None:
    for path in (benchmark_root / "runs").glob("*/predictions.csv"):
        with path.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                student_id = row.get("student_id", "")
                if not ANONYMOUS_ID.fullmatch(student_id):
                    raise ValueError(f"non-anonymous student ID in {path}: {student_id}")


def _read_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"
