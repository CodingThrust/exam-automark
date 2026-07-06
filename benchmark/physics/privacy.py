from pathlib import Path

from PIL import Image, ImageDraw


def apply_redactions(
    source: Path,
    output: Path,
    rectangles: list[tuple[int, int, int, int]],
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source).convert("RGB") as image:
        draw = ImageDraw.Draw(image)
        for rectangle in rectangles:
            draw.rectangle(rectangle, fill="black")
        image.save(output, quality=95)


def assert_privacy_approved(rows: list[dict[str, str]]) -> None:
    rejected = [
        row["page"] for row in rows if row.get("approved", "").lower() != "true"
    ]
    if rejected:
        raise ValueError(f"privacy approval missing for: {', '.join(rejected)}")


def assert_anonymous_name(path: Path) -> None:
    if not path.stem.startswith("S") or "_" in path.name:
        raise ValueError(f"non-anonymous filename: {path.name}")
