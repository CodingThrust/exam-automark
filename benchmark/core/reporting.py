import json
from pathlib import Path
from typing import Any

from .manifests import ExperimentRecord


CONDITION_LABELS = {
    "G0": "Historical direct workflow",
    "G2": "Codex/Codex-like grading from automatic transcript",
    "D1": "DeepSeek grading from automatic transcript",
    "G3": "Codex/Codex-like grading from human transcript",
    "D2": "DeepSeek grading from human transcript",
    "T1": "Transcription packet",
}


def render_typst_note(
    record: ExperimentRecord,
    *,
    metrics: dict[str, Any] | None = None,
    title: str | None = None,
) -> str:
    title = title or _title(record)
    lines = [
        '#set document(title: "{}")'.format(_escape_typst_string(title)),
        "#set page(margin: (x: 1.6cm, y: 1.25cm))",
        '#set text(font: "New Computer Modern", size: 9.25pt)',
        '#import "@preview/cetz:0.5.2"',
        '#let ink = rgb("#17212b")',
        '#let accent = rgb("#256d85")',
        '#let accent2 = rgb("#7a5c00")',
        '#let soft = rgb("#edf5f7")',
        '#let line = rgb("#d8e4e8")',
        '#let danger = rgb("#a33b2f")',
        '#let muted = rgb("#63707a")',
        '#let pill(body) = box(fill: soft, stroke: line, inset: (x: 7pt, y: 4pt), radius: 3pt, body)',
        '#let metric-card(label, value, detail) = box(fill: soft, stroke: line, inset: 8pt, radius: 4pt, width: 100%)[#text(size: 8pt, fill: accent)[#label]\\ #text(size: 17pt, weight: "bold")[#value]\\ #text(size: 8pt)[#detail]]',
        "",
        "#align(center)[",
        f"  #text(size: 20pt, weight: \"bold\", fill: ink)[{_escape_markup(title)}]",
        "]",
        "",
        "#align(center)[",
        f"  #pill[{_escape_markup(_status_line(record))}]",
        "]",
        "",
        _executive_summary(record, metrics),
        "",
        "== What Is Being Reproduced",
        "",
        _method_overview(record),
        "",
        "== Reproducibility Anchors",
        "",
        _anchor_grid(record),
        "",
        "== Prompt Packet Registry",
        "",
        _packet_table(record),
        "",
    ]
    if metrics is not None:
        lines.extend(
            [
                "== Key Findings",
                "",
                _key_findings(record, metrics),
                "",
                "#pagebreak()",
                "",
                "== Results At A Glance",
                "",
                _metric_cards(metrics),
                "",
                _results_dashboard(metrics),
                "",
                "#pagebreak()",
                "",
                "== Condition Details",
                "",
                _condition_table(metrics),
                "",
                "== Where Errors Concentrate",
                "",
                _weak_question_table(metrics),
                "",
                "== Paired And Transcript Comparisons",
                "",
                _paired_section(metrics),
                "",
            ]
        )
    lines.extend(
        [
            "== Reproduction Commands",
            "",
            _reproduction_commands(record),
            "",
            "== Limitations",
            "",
            _limitations(record, metrics),
            "",
        ]
    )
    return "\n".join(lines)


def write_typst_note(
    record_path: Path,
    output_path: Path | None = None,
    *,
    metrics_path: Path | None = None,
    title: str | None = None,
) -> Path:
    record = ExperimentRecord.from_json_path(record_path)
    if metrics_path is None and record.metrics_path:
        candidate = Path(record.metrics_path)
        metrics_path = candidate if candidate.exists() else None
    metrics = _read_json(metrics_path) if metrics_path is not None else None
    target = output_path or Path(record.note_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        render_typst_note(record, metrics=metrics, title=title),
        encoding="utf-8",
        newline="\n",
    )
    return target


def _metadata_table(record: ExperimentRecord) -> str:
    rows = [
        ("Experiment", record.experiment_id),
        ("Course", record.course_id),
        ("Assessment", record.assessment_id),
        ("Git branch", record.git_branch),
        ("Git commit", record.git_commit),
        ("Data snapshot", _short_hash(record.data_snapshot_hash)),
        ("Metrics", record.metrics_path),
        ("Typst note", record.note_path),
    ]
    return _simple_table(("Field", "Value"), rows)


def _packet_table(record: ExperimentRecord) -> str:
    rows = [
        (condition, _short_hash(digest))
        for condition, digest in sorted(record.prompt_packet_hashes.items())
    ]
    return _simple_table(("Condition", "Packet SHA-256"), rows)


def _condition_table(metrics: dict[str, Any]) -> str:
    conditions = metrics.get("conditions", {})
    rows = []
    for condition, result in sorted(conditions.items()):
        rows.append(
            (
                condition,
                str(result.get("n_students", "")),
                str(result.get("population", "")),
                _percent(result.get("exact_agreement", 0)),
                _number(result.get("total_score_mae", 0)),
                _percent(result.get("within_1_point_rate", 0)),
                _percent(result.get("severe_error_rate", 0)),
                _signed(result.get("mean_signed_error", 0)),
            )
        )
    if not rows:
        return "_No condition metrics were available._"
    return _simple_table(
        (
            "Cond.",
            "N",
            "Population",
            "Exact",
            "Total MAE",
            "Within 1",
            "Severe",
            "Bias",
        ),
        rows,
    )


def _accuracy_bar_chart(metrics: dict[str, Any]) -> str:
    conditions = metrics.get("conditions", {})
    if not conditions:
        return "_No chart data was available._"
    lines = ["#grid(columns: 1, row-gutter: 5pt,"]
    for condition, result in _sorted_conditions(conditions):
        exact = float(result.get("exact_agreement", 0))
        severe = float(result.get("severe_error_rate", 0))
        width = max(4.0, exact * 250)
        lines.append(
            "  box(width: 100%, inset: (x: 0pt, y: 3pt))[{}],".format(
                "#grid(columns: (34pt, 1fr, 54pt, 54pt), column-gutter: 8pt, {}, {}, {}, {})".format(
                    _cell(condition),
                    "[#box(width: 100%, height: 9pt, fill: line, radius: 2pt)[#rect(width: {:.1f}pt, height: 9pt, fill: accent, radius: 2pt)] #v(2pt) #text(size: 8pt)[{}]]".format(
                        width, CONDITION_LABELS.get(condition, result.get("run_id", condition))
                    ),
                    _cell(_percent(exact)),
                    _cell("sev. " + _percent(severe)),
                )
            )
        )
    lines.append(")")
    lines.append("")
    lines.append("_Bars show exact agreement. Severe-error rate is shown at right._")
    return "\n".join(lines)


def _results_dashboard(metrics: dict[str, Any]) -> str:
    conditions = metrics.get("conditions", {})
    if not conditions:
        return "_No chart data was available._"
    left = _visual_panel(
        "Accuracy vs severe-error risk",
        _accuracy_risk_map(metrics),
        "Upper left is better: high exact agreement and low severe-error rate.",
    )
    right = _visual_panel(
        "Ranked condition bars",
        _condition_bar_chart(metrics),
        "Blue bars show exact agreement. Red ticks show severe-error rate.",
    )
    transcript = _visual_panel(
        "Transcript-path delta",
        _transcript_delta_chart(metrics),
        "Same-student subset comparison: automatic transcript versus human transcript.",
    )
    heatmap = _visual_panel(
        "Question-level agreement heatmap",
        _question_heatmap(metrics),
        "Cells show per-question exact agreement. Red and amber cells are review targets.",
    )
    return "\n".join(
        [
            "#grid(columns: (1.05fr, 0.95fr), gutter: 8pt,",
            f"  {left},",
            f"  {right},",
            ")",
            "#v(6pt)",
            "#" + transcript,
            "#v(6pt)",
            "#" + heatmap,
        ]
    )


def _visual_panel(title: str, body: str, caption: str) -> str:
    return "\n".join(
        [
            "box(fill: white, stroke: line, inset: 8pt, radius: 4pt, width: 100%)[",
            f"#strong[{_escape_markup(title)}]",
            "#v(4pt)",
            body,
            "#v(3pt)",
            f"#text(size: 7.5pt, fill: muted)[{_escape_markup(caption)}]",
            "]",
        ]
    )


def _accuracy_risk_map(metrics: dict[str, Any]) -> str:
    conditions = metrics.get("conditions", {})
    if not conditions:
        return "_No chart data was available._"
    x_min, x_max = 0.0, 0.42
    y_min, y_max = 0.75, 0.95

    def x(value: float) -> float:
        return 0.8 + _clamp((value - x_min) / (x_max - x_min), 0, 1) * 6.1

    def y(value: float) -> float:
        return 0.6 + _clamp((value - y_min) / (y_max - y_min), 0, 1) * 3.5

    lines = [
        'rect((0.55, 0.45), (7.25, 4.45), fill: rgb("#fbfdfe"), stroke: rgb("#d8e4e8"))',
        'line((0.8, 0.6), (6.9, 0.6), stroke: rgb("#63707a"))',
        'line((0.8, 0.6), (0.8, 4.1), stroke: rgb("#63707a"))',
        'content((0.75, 4.32), text(size: 7pt, fill: rgb("#63707a"))[Exact])',
        'content((6.95, 0.35), text(size: 7pt, fill: rgb("#63707a"))[Severe])',
    ]
    for tick in (0.0, 0.2, 0.4):
        x_pos = x(tick)
        lines.extend(
            [
                f'line(({x_pos:.2f}, 0.54), ({x_pos:.2f}, 0.66), stroke: rgb("#63707a"))',
                f'content(({x_pos:.2f}, 0.24), text(size: 6.5pt, fill: rgb("#63707a"))[{_percent(tick)}])',
            ]
        )
    for tick in (0.8, 0.9):
        y_pos = y(tick)
        lines.extend(
            [
                f'line((0.74, {y_pos:.2f}), (0.86, {y_pos:.2f}), stroke: rgb("#63707a"))',
                f'content((0.38, {y_pos:.2f}), text(size: 6.5pt, fill: rgb("#63707a"))[{_percent(tick)}])',
            ]
        )
    label_offsets = {
        "D1": (0.32, 0.18),
        "D2": (0.28, -0.18),
        "G0": (0.30, 0.15),
        "G2": (0.28, 0.18),
        "G3": (0.30, -0.18),
    }
    for condition, result in sorted(conditions.items()):
        exact = float(result.get("exact_agreement", 0))
        severe = float(result.get("severe_error_rate", 0))
        x_pos, y_pos = x(severe), y(exact)
        fill = _risk_color(severe)
        dx, dy = label_offsets.get(condition, (0.28, 0.14))
        lines.extend(
            [
                f'rect(({x_pos - 0.10:.2f}, {y_pos - 0.10:.2f}), ({x_pos + 0.10:.2f}, {y_pos + 0.10:.2f}), fill: rgb("{fill}"), stroke: white)',
                f'content(({x_pos + dx:.2f}, {y_pos + dy:.2f}), text(size: 7pt, weight: "bold", fill: rgb("#17212b"))[{_escape_markup(condition)}])',
            ]
        )
    lines.extend(
        [
            'rect((0.90, 3.62), (2.30, 3.98), fill: rgb("#e8f3ed"), stroke: none)',
            'content((1.60, 3.80), text(size: 6.5pt, fill: rgb("#316a4d"))[target zone])',
        ]
    )
    return _cetz_canvas(lines)


def _condition_bar_chart(metrics: dict[str, Any]) -> str:
    conditions = metrics.get("conditions", {})
    if not conditions:
        return "_No chart data was available._"
    lines = [
        'content((1.05, 4.72), text(size: 6.5pt, fill: rgb("#63707a"))[0])',
        'content((4.20, 4.72), text(size: 6.5pt, fill: rgb("#63707a"))[50%])',
        'content((7.25, 4.72), text(size: 6.5pt, fill: rgb("#63707a"))[100%])',
    ]
    y_pos = 4.2
    for condition, result in _sorted_conditions(conditions):
        exact = float(result.get("exact_agreement", 0))
        severe = float(result.get("severe_error_rate", 0))
        bar_start, bar_end = 1.05, 7.25
        exact_end = bar_start + exact * (bar_end - bar_start)
        severe_x = bar_start + severe * (bar_end - bar_start)
        lines.extend(
            [
                f'content((0.34, {y_pos + 0.07:.2f}), text(size: 7.5pt, weight: "bold")[{_escape_markup(condition)}])',
                f'rect(({bar_start:.2f}, {y_pos - 0.08:.2f}), ({bar_end:.2f}, {y_pos + 0.08:.2f}), fill: rgb("#d8e4e8"), stroke: none)',
                f'rect(({bar_start:.2f}, {y_pos - 0.08:.2f}), ({exact_end:.2f}, {y_pos + 0.08:.2f}), fill: rgb("#256d85"), stroke: none)',
                f'rect(({severe_x - 0.025:.2f}, {y_pos - 0.19:.2f}), ({severe_x + 0.025:.2f}, {y_pos + 0.19:.2f}), fill: rgb("#a33b2f"), stroke: none)',
                f'content((7.72, {y_pos + 0.07:.2f}), text(size: 7pt)[{_percent(exact)}])',
                f'content((8.58, {y_pos + 0.07:.2f}), text(size: 6.5pt, fill: rgb("#a33b2f"))[{_percent(severe)}])',
            ]
        )
        y_pos -= 0.75
    return _cetz_canvas(lines)


def _transcript_delta_chart(metrics: dict[str, Any]) -> str:
    subset = metrics.get("transcript_subset_comparisons", {})
    if not subset:
        return "_No transcript subset comparison data was available._"
    x_min, x_max = 0.75, 0.90

    def x(value: float) -> float:
        return 1.0 + _clamp((value - x_min) / (x_max - x_min), 0, 1) * 9.0

    lines = [
        'line((1.0, 0.55), (10.0, 0.55), stroke: rgb("#63707a"))',
        'content((1.0, 0.25), text(size: 6.5pt, fill: rgb("#63707a"))[75%])',
        'content((4.0, 0.25), text(size: 6.5pt, fill: rgb("#63707a"))[80%])',
        'content((7.0, 0.25), text(size: 6.5pt, fill: rgb("#63707a"))[85%])',
        'content((10.0, 0.25), text(size: 6.5pt, fill: rgb("#63707a"))[90%])',
    ]
    y_pos = 2.05
    for label, comparison in sorted(subset.items()):
        auto = float(comparison.get("automatic_exact_agreement", 0))
        human = float(comparison.get("human_exact_agreement", 0))
        auto_x, human_x = x(auto), x(human)
        model_label = _escape_markup(label)
        auto_label = _escape_markup(str(comparison.get("automatic_condition", "")))
        human_label = _escape_markup(str(comparison.get("human_condition", "")))
        lines.extend(
            [
                f'content((0.35, {y_pos:.2f}), text(size: 7.5pt, weight: "bold")[{model_label}])',
                f'line(({auto_x:.2f}, {y_pos:.2f}), ({human_x:.2f}, {y_pos:.2f}), stroke: (paint: rgb("#7a5c00"), thickness: 1.2pt))',
                f'rect(({auto_x - 0.08:.2f}, {y_pos - 0.08:.2f}), ({auto_x + 0.08:.2f}, {y_pos + 0.08:.2f}), fill: rgb("#256d85"), stroke: white)',
                f'rect(({human_x - 0.08:.2f}, {y_pos - 0.08:.2f}), ({human_x + 0.08:.2f}, {y_pos + 0.08:.2f}), fill: rgb("#7a5c00"), stroke: white)',
                f'content(({auto_x:.2f}, {y_pos + 0.32:.2f}), text(size: 6.5pt, fill: rgb("#256d85"))[{auto_label} {_percent(auto)}])',
                f'content(({human_x:.2f}, {y_pos - 0.32:.2f}), text(size: 6.5pt, fill: rgb("#7a5c00"))[{human_label} {_percent(human)}])',
            ]
        )
        y_pos -= 0.95
    return _cetz_canvas(lines)


def _question_heatmap(metrics: dict[str, Any]) -> str:
    conditions = metrics.get("conditions", {})
    if not conditions:
        return "_No per-question data was available._"
    question_ids = sorted(
        {
            question
            for result in conditions.values()
            for question in result.get("per_question_accuracy", {})
        },
        key=_question_sort_key,
    )
    if len(question_ids) > 12:
        means = []
        for question in question_ids:
            values = [
                float(result.get("per_question_accuracy", {}).get(question, 0))
                for result in conditions.values()
                if question in result.get("per_question_accuracy", {})
            ]
            means.append((sum(values) / len(values), question))
        question_ids = sorted(
            [question for _, question in sorted(means)[:12]],
            key=_question_sort_key,
        )
    x0, y0 = 1.05, 0.62
    cell_w, cell_h = 0.52, 0.35
    top_y = y0 + len(conditions) * cell_h
    lines = [
        f'content((0.35, {top_y + 0.22:.2f}), text(size: 6.5pt, fill: rgb("#63707a"))[Cond.])'
    ]
    for index, question in enumerate(question_ids):
        x = x0 + index * cell_w
        lines.append(
            f'content(({x + cell_w / 2:.2f}, {top_y + 0.22:.2f}), text(size: 5.8pt, fill: rgb("#63707a"))[{_escape_markup(question)}])'
        )
    for row_index, (condition, result) in enumerate(_sorted_conditions(conditions)):
        y = top_y - (row_index + 1) * cell_h
        lines.append(
            f'content((0.35, {y + cell_h / 2:.2f}), text(size: 6.5pt, weight: "bold")[{_escape_markup(condition)}])'
        )
        per_question = result.get("per_question_accuracy", {})
        for column_index, question in enumerate(question_ids):
            value = float(per_question.get(question, 0))
            x = x0 + column_index * cell_w
            lines.append(
                f'rect(({x:.2f}, {y:.2f}), ({x + cell_w:.2f}, {y + cell_h:.2f}), fill: rgb("{_heat_color(value)}"), stroke: white)'
            )
    legend_x = x0 + len(question_ids) * cell_w + 0.65
    for label, color, offset in (
        ("low", "#a33b2f", 0.70),
        ("mid", "#b9822f", 0.35),
        ("high", "#2d7a5b", 0.00),
    ):
        y = top_y - offset
        lines.extend(
            [
                f'rect(({legend_x:.2f}, {y:.2f}), ({legend_x + 0.25:.2f}, {y + 0.18:.2f}), fill: rgb("{color}"), stroke: none)',
                f'content(({legend_x + 0.62:.2f}, {y + 0.09:.2f}), text(size: 6.3pt, fill: rgb("#63707a"))[{label}])',
            ]
        )
    return _cetz_canvas(lines)


def _cetz_canvas(lines: list[str]) -> str:
    body = "\n".join(f"  {line}" for line in lines)
    return "#cetz.canvas({\n  import cetz.draw: *\n" + body + "\n})"


def _risk_color(severe: float) -> str:
    if severe >= 0.35:
        return "#a33b2f"
    if severe >= 0.20:
        return "#b9822f"
    return "#2d7a5b"


def _heat_color(value: float) -> str:
    if value < 0.60:
        return "#a33b2f"
    if value < 0.75:
        return "#b9822f"
    if value < 0.85:
        return "#d6b15b"
    if value < 0.95:
        return "#7ba989"
    return "#2d7a5b"


def _sorted_conditions(
    conditions: dict[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    return sorted(
        conditions.items(),
        key=lambda item: (-float(item[1].get("exact_agreement", 0)), item[0]),
    )


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _question_sort_key(value: str) -> tuple[int, str]:
    if len(value) >= 2 and value[0].upper() == "Q":
        digits = ""
        suffix = ""
        for character in value[1:]:
            if character.isdigit() and not suffix:
                digits += character
            else:
                suffix += character
        if digits:
            return (int(digits), suffix)
    return (10_000, value)


def _weak_question_table(metrics: dict[str, Any]) -> str:
    rows = []
    for condition, result in sorted(metrics.get("conditions", {}).items()):
        per_question = result.get("per_question_accuracy", {})
        weakest = sorted(per_question.items(), key=lambda row: (row[1], row[0]))[:3]
        rows.append(
            (
                condition,
                ", ".join(f"{question}: {_percent(value)}" for question, value in weakest),
            )
        )
    if not rows:
        return "_No per-question accuracy data was available._"
    return _simple_table(("Condition", "Lowest-agreement questions"), rows)


def _paired_section(metrics: dict[str, Any]) -> str:
    lines = []
    paired = metrics.get("paired_vs_g0", {})
    if paired:
        lines.extend(
            [
                "#strong[Paired exact-agreement differences versus G0]",
                "",
                _simple_table(
                    ("Condition", "Mean diff.", "95% interval"),
                    [
                        (
                            condition,
                            _percent(result.get("mean_difference", 0)),
                            "{} to {}".format(
                                _percent(result.get("lower", 0)),
                                _percent(result.get("upper", 0)),
                            ),
                        )
                        for condition, result in sorted(paired.items())
                    ],
                ),
                "",
            ]
        )
    subset = metrics.get("transcript_subset_comparisons", {})
    if subset:
        lines.extend(["#strong[Transcript subset comparisons]", ""])
        rows = []
        for label, comparison in sorted(subset.items()):
            interval = comparison.get("human_minus_automatic", {})
            rows.append(
                (
                    label,
                    "{} -> {}".format(
                        comparison.get("automatic_condition", ""),
                        comparison.get("human_condition", ""),
                    ),
                    _percent(comparison.get("automatic_exact_agreement", 0)),
                    _percent(comparison.get("human_exact_agreement", 0)),
                    "{} to {}".format(
                        _percent(interval.get("lower", 0)),
                        _percent(interval.get("upper", 0)),
                    ),
                )
            )
        lines.append(
            _simple_table(
                ("Model", "Conditions", "Auto exact", "Human exact", "Interval"),
                rows,
            )
        )
    if not lines:
        return "_No paired comparison data was available._"
    return "\n".join(lines)


def _key_findings(record: ExperimentRecord, metrics: dict[str, Any]) -> str:
    findings = []
    best = _best_condition(metrics)
    g0 = metrics.get("conditions", {}).get("G0")
    severe = _highest_severe_condition(metrics)
    if best is not None:
        findings.append(
            "{} is the highest exact-agreement condition in this file at {}.".format(
                best[0], _percent(best[1].get("exact_agreement", 0))
            )
        )
    if g0 is not None and best is not None and best[0] != "G0":
        delta = best[1].get("exact_agreement", 0) - g0.get("exact_agreement", 0)
        findings.append(
            "Compared with the historical G0 baseline, the best condition differs by {} exact agreement.".format(
                _percent(delta)
            )
        )
    elif g0 is not None:
        findings.append(
            "The historical G0 baseline remains the top exact-agreement condition, so this pilot does not show a workflow improvement over G0."
        )
    if severe is not None:
        findings.append(
            "{} has the highest severe-error rate ({}), which is the clearest operational risk signal in this pilot.".format(
                severe[0], _percent(severe[1].get("severe_error_rate", 0))
            )
        )
    subset = metrics.get("transcript_subset_comparisons", {})
    for label, comparison in sorted(subset.items()):
        interval = comparison.get("human_minus_automatic", {})
        findings.append(
            "{} transcript subset: {} to {} changed exact agreement from {} to {}; human-minus-automatic interval {} to {}.".format(
                label,
                comparison.get("automatic_condition", ""),
                comparison.get("human_condition", ""),
                _percent(comparison.get("automatic_exact_agreement", 0)),
                _percent(comparison.get("human_exact_agreement", 0)),
                _percent(interval.get("lower", 0)),
                _percent(interval.get("upper", 0)),
            )
        )
    if record.course_id == "physics" and "pilot" in record.experiment_id:
        findings.append(
            "Interpret all findings as protocol guidance only; this pilot is not evidence that one workflow generalizes across courses."
        )
    return "\n".join(f"- {_escape_markup(finding)}" for finding in findings)


def _reproduction_commands(record: ExperimentRecord) -> str:
    benchmark_root = _benchmark_root_from_metrics_path(record.metrics_path)
    commands = [
        f"python -m benchmark.core.cli audit-packet --packet <packet-path>",
    ]
    if benchmark_root is not None:
        commands.extend(
            [
                f"python -m benchmark.physics.cli validate --root {benchmark_root}",
                f"python -m benchmark.physics.cli evaluate --root {benchmark_root} --split dev",
                f"python -m benchmark.physics.cli evaluate --root {benchmark_root} --split test",
                f"python -m benchmark.physics.cli evaluate --root {benchmark_root} --split all",
            ]
        )
    return "```bash\n" + "\n".join(commands) + "\n```"


def _executive_summary(
    record: ExperimentRecord, metrics: dict[str, Any] | None
) -> str:
    if metrics is None or not metrics.get("conditions"):
        return (
            "#box(fill: soft, stroke: line, inset: 10pt, radius: 4pt)["
            "#strong[Summary.] This note records the experiment identity, prompt packets, "
            "and reproduction commands. Metrics were not attached to this rendering.]"
        )
    best = _best_condition(metrics)
    baseline = metrics.get("conditions", {}).get("G0")
    summary = [
        "#box(fill: soft, stroke: line, inset: 10pt, radius: 4pt)[",
        "#strong[Reading guide.] This is a reproducibility note, not a leaderboard. ",
    ]
    if best is not None:
        summary.append(
            "{} has the highest exact agreement in this metrics file ({}). ".format(
                _escape_markup(best[0]), _percent(best[1].get("exact_agreement", 0))
            )
        )
    if baseline is not None:
        summary.append(
            "The historical G0 baseline is retained for context at {} exact agreement. ".format(
                _percent(baseline.get("exact_agreement", 0))
            )
        )
    if record.course_id == "physics" and "pilot" in record.experiment_id:
        summary.append(
            "#text(fill: danger)[Because this is a legacy pilot, these numbers guide protocol design and should not be presented as final cross-course evidence.]"
        )
    summary.append("]")
    return "".join(summary)


def _method_overview(record: ExperimentRecord) -> str:
    return "\n".join(
        [
            "#grid(columns: (1fr, 1fr, 1fr), gutter: 8pt,",
            '  box(fill: soft, stroke: line, inset: 8pt, radius: 4pt)[#strong[1. Freeze]\\ Anonymous data snapshot and rubric are identified by hash.],',
            '  box(fill: soft, stroke: line, inset: 8pt, radius: 4pt)[#strong[2. Packetize]\\ Model-facing work happens only inside prompt packets with `prompt.txt`.],',
            '  box(fill: soft, stroke: line, inset: 8pt, radius: 4pt)[#strong[3. Evaluate]\\ Predictions are compared with the same metrics script and recorded here.],',
            ")",
            "",
            f"This record covers `{_escape_markup(record.course_id)}` / `{_escape_markup(record.assessment_id)}` on branch `{_escape_markup(record.git_branch)}`.",
        ]
    )


def _anchor_grid(record: ExperimentRecord) -> str:
    rows = [
        ("Experiment", record.experiment_id),
        ("Git", f"{record.git_branch} @ {record.git_commit}"),
        ("Data snapshot", _short_hash(record.data_snapshot_hash)),
        ("Metrics", record.metrics_path),
        ("Typst source", record.note_path),
    ]
    return _simple_table(("Anchor", "Value"), rows)


def _metric_cards(metrics: dict[str, Any]) -> str:
    conditions = metrics.get("conditions", {})
    if not conditions:
        return ""
    best = _best_condition(metrics)
    g0 = conditions.get("G0")
    severe = _highest_severe_condition(metrics)
    cards = []
    if best is not None:
        cards.append(
            'metric-card("Best exact", "{}", "{}")'.format(
                _percent(best[1].get("exact_agreement", 0)),
                _escape_typst_string(best[0]),
            )
        )
    if g0 is not None:
        cards.append(
            'metric-card("G0 exact", "{}", "historical baseline")'.format(
                _percent(g0.get("exact_agreement", 0))
            )
        )
    if severe is not None:
        cards.append(
            'metric-card("Highest severe", "{}", "{}")'.format(
                _percent(severe[1].get("severe_error_rate", 0)),
                _escape_typst_string(severe[0]),
            )
        )
    return "#grid(columns: 3, gutter: 8pt, " + ", ".join(cards) + ")"


def _best_condition(metrics: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    conditions = metrics.get("conditions", {})
    if not conditions:
        return None
    return max(
        conditions.items(),
        key=lambda item: (item[1].get("exact_agreement", 0), item[0]),
    )


def _highest_severe_condition(metrics: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    conditions = metrics.get("conditions", {})
    if not conditions:
        return None
    return max(
        conditions.items(),
        key=lambda item: (item[1].get("severe_error_rate", 0), item[0]),
    )


def _limitations(record: ExperimentRecord, metrics: dict[str, Any] | None) -> str:
    bullets = list(record.notes)
    if metrics is not None and metrics.get("reference_status") == "single_primary_rater":
        bullets.append("reference scores are single-primary-rater, not adjudicated")
    if record.course_id == "physics" and "pilot" in record.experiment_id:
        bullets.append("Physics Week 9 is a pilot and must not be generalized to other courses")
        bullets.append("historical baselines and interactive model runs are not controlled reruns")
    if not bullets:
        bullets.append("limitations must be reviewed before reporting results")
    return "\n".join(f"- {_escape_markup(item)}" for item in bullets)


def _simple_table(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> str:
    column_spec = ", ".join("auto" for _ in headers)
    lines = [
        f"#table(columns: ({column_spec}), stroke: line, inset: (x: 6pt, y: 4pt),"
    ]
    lines.append("  " + ", ".join(_header_cell(header) for header in headers) + ",")
    for row in rows:
        lines.append("  " + ", ".join(_cell(value) for value in row) + ",")
    lines.append(")")
    return "\n".join(lines)


def _cell(value: Any) -> str:
    return "[{}]".format(_escape_markup(str(value)))


def _header_cell(value: Any) -> str:
    return "[#strong[{}]]".format(_escape_markup(str(value)))


def _title(record: ExperimentRecord) -> str:
    return f"{record.course_id} {record.assessment_id} Reproducibility Note"


def _status_line(record: ExperimentRecord) -> str:
    if any("pilot" in note.lower() for note in record.notes):
        return "Pilot record. Use for protocol design, not final accuracy claims."
    return "Reproducibility record."


def _benchmark_root_from_metrics_path(metrics_path: str) -> str | None:
    path = Path(metrics_path)
    if path.name.startswith("metrics-"):
        return path.parent.as_posix()
    return None


def _percent(value: Any) -> str:
    return f"{float(value) * 100:.1f}%"


def _number(value: Any) -> str:
    return f"{float(value):.3f}"


def _signed(value: Any) -> str:
    return f"{float(value):+.3f}"


def _short_hash(value: str) -> str:
    return value[:12] + "..." if len(value) > 15 else value


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload


def _escape_typst_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _escape_markup(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace("#", "\\#")
    )
