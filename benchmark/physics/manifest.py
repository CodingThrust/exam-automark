import random
from collections import defaultdict


def assign_split(
    rows: list[dict[str, str]], dev_size: int, seed: int
) -> list[dict[str, str]]:
    if dev_size <= 0 or dev_size >= len(rows):
        raise ValueError("dev_size must leave both splits non-empty")
    rng = random.Random(seed)
    strata: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = (row["clarity"], row["format"], row["score_band"])
        strata[key].append(dict(row))
    ordered: list[dict[str, str]] = []
    for key in sorted(strata):
        group = strata[key]
        rng.shuffle(group)
        ordered.extend(group)
    selected = {row["student_id"] for row in ordered[::3][:dev_size]}
    if len(selected) < dev_size:
        for row in ordered:
            selected.add(row["student_id"])
            if len(selected) == dev_size:
                break
    result = []
    for row in sorted(rows, key=lambda item: item["student_id"]):
        item = dict(row)
        item["split"] = "dev" if item["student_id"] in selected else "test"
        result.append(item)
    return result
