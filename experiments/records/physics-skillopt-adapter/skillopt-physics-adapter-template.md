# SkillOpt Physics Adapter Template

This file is a copy-and-adapt guide for an external Microsoft SkillOpt checkout.
It is not imported by `exam-automark`.

## Target Layout In SkillOpt

```text
SkillOpt/
  skillopt/envs/physics_grading/
    __init__.py
    adapter.py
    dataloader.py
    rollout.py
    skills/initial.md
  configs/physics_grading/default.yaml
```

The split directory should be produced by `exam-automark`:

```text
Data/physics/benchmark/skillopt/physics-week9-text-split-v1/
  train/items.json
  val/items.json
  test/items.json
```

## dataloader.py

```python
from __future__ import annotations

import json
from pathlib import Path

from skillopt.datasets.base import SplitDataLoader


class PhysicsGradingDataLoader(SplitDataLoader):
    def load_split_items(self, split_path: str) -> list[dict]:
        path = Path(split_path) / "items.json"
        if not path.exists():
            raise FileNotFoundError(f"items.json not found: {path}")
        with path.open(encoding="utf-8") as handle:
            items = json.load(handle)
        if not isinstance(items, list):
            raise ValueError(f"items.json must contain a list: {path}")
        return items
```

## rollout.py

```python
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from skillopt.model import chat_target


def run_batch(
    *,
    items: list[dict],
    skill_content: str,
    out_root: str,
    workers: int = 4,
    max_completion_tokens: int = 4096,
) -> list[dict]:
    out_dir = Path(out_root)
    prediction_dir = out_dir / "predictions"
    prediction_dir.mkdir(parents=True, exist_ok=True)
    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(
                _run_one,
                item,
                skill_content,
                prediction_dir,
                max_completion_tokens,
            )
            for item in items
        ]
        for future in as_completed(futures):
            results.append(future.result())
    return sorted(results, key=lambda row: row["id"])


def _run_one(
    item: dict,
    skill_content: str,
    prediction_dir: Path,
    max_completion_tokens: int,
) -> dict:
    system = skill_content
    user = _build_user_prompt(item)
    prediction, _usage = chat_target(
        system=system,
        user=user,
        max_completion_tokens=max_completion_tokens,
    )
    parsed = _parse_json(prediction)
    hard, soft, total_abs_error = _score(parsed, item)
    item_dir = prediction_dir / item["id"]
    item_dir.mkdir(parents=True, exist_ok=True)
    (item_dir / "conversation.json").write_text(
        json.dumps(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
                {"role": "assistant", "content": prediction},
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "id": item["id"],
        "hard": hard,
        "soft": soft,
        "student_id": item["student_id"],
        "task_description": item["question"],
        "total_abs_error": total_abs_error,
    }


def _build_user_prompt(item: dict) -> str:
    payload = {
        "student_id": item["student_id"],
        "course": item["course"],
        "rubric": item["rubric"],
        "output_schema": item["output_schema"],
        "transcript": item["transcript"],
    }
    return (
        "Grade the anonymous physics work. Return one JSON object only. "
        "The JSON must follow output_schema exactly.\n\n"
        + json.dumps(payload, ensure_ascii=False, sort_keys=True)
    )


def _parse_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("model response did not contain a JSON object")
    return json.loads(text[start : end + 1])


def _score(payload: dict, item: dict) -> tuple[float, float, float]:
    gold = {row["question_id"]: float(row["score"]) for row in item["gold_scores"]}
    predicted = {
        row["question_id"]: float(row["score"])
        for row in payload.get("scores", [])
        if "question_id" in row and "score" in row
    }
    if set(predicted) != set(gold):
        return 0.0, 0.0, 999.0
    abs_errors = [abs(predicted[qid] - gold[qid]) for qid in sorted(gold)]
    exact = sum(error == 0 for error in abs_errors)
    total_abs_error = sum(abs_errors)
    hard = 1.0 if total_abs_error == 0 else 0.0
    soft = exact / len(abs_errors)
    return hard, soft, total_abs_error
```

## adapter.py

```python
from __future__ import annotations

from skillopt.datasets.base import BatchSpec
from skillopt.envs.base import EnvAdapter
from skillopt.envs.physics_grading.dataloader import PhysicsGradingDataLoader
from skillopt.envs.physics_grading.rollout import run_batch


class PhysicsGradingAdapter(EnvAdapter):
    def __init__(
        self,
        split_dir: str = "",
        data_path: str = "",
        split_mode: str = "split_dir",
        split_ratio: str = "2:1:7",
        split_seed: int = 42,
        split_output_dir: str = "",
        workers: int = 4,
        analyst_workers: int = 4,
        failure_only: bool = False,
        minibatch_size: int = 4,
        edit_budget: int = 4,
        seed: int = 42,
        limit: int = 0,
        max_completion_tokens: int = 4096,
    ) -> None:
        self.workers = workers
        self.analyst_workers = analyst_workers
        self.failure_only = failure_only
        self.minibatch_size = minibatch_size
        self.edit_budget = edit_budget
        self.max_completion_tokens = int(max_completion_tokens)
        self.dataloader = PhysicsGradingDataLoader(
            split_dir=split_dir,
            data_path=data_path,
            split_mode=split_mode,
            split_ratio=split_ratio,
            split_seed=split_seed,
            split_output_dir=split_output_dir,
            seed=seed,
            limit=limit,
        )

    def setup(self, cfg: dict) -> None:
        super().setup(cfg)
        self.dataloader.setup(cfg)

    def get_dataloader(self):
        return self.dataloader

    def build_env_from_batch(self, batch: BatchSpec, **kwargs):
        return list(batch.payload or [])

    def build_train_env(self, batch_size: int, seed: int, **kwargs):
        batch = self.dataloader.build_train_batch(
            batch_size=batch_size,
            seed=seed,
            **kwargs,
        )
        return self.build_env_from_batch(batch, **kwargs)

    def build_eval_env(self, env_num: int, split: str, seed: int, **kwargs):
        batch = self.dataloader.build_eval_batch(
            env_num=env_num,
            split=split,
            seed=seed,
            **kwargs,
        )
        return self.build_env_from_batch(batch, **kwargs)

    def rollout(self, env_manager, skill_content: str, out_dir: str, **kwargs):
        return run_batch(
            items=list(env_manager),
            skill_content=skill_content,
            out_root=out_dir,
            workers=self.workers,
            max_completion_tokens=self.max_completion_tokens,
        )

    def get_task_types(self) -> list[str]:
        return ["physics_week9_text_grading"]
```

## Registration

Add this lazy import to both `scripts/train.py` and `scripts/eval_only.py` in the
SkillOpt checkout:

```python
try:
    from skillopt.envs.physics_grading.adapter import PhysicsGradingAdapter

    _ENV_REGISTRY["physics_grading"] = PhysicsGradingAdapter
except ImportError:
    pass
```

## configs/physics_grading/default.yaml

```yaml
_base_: ../_base_/default.yaml

model:
  reasoning_effort: medium

train:
  batch_size: 4
  accumulation: 1
  num_epochs: 1

gradient:
  minibatch_size: 4
  merge_batch_size: 4

optimizer:
  learning_rate: 4

env:
  name: physics_grading
  skill_init: skillopt/envs/physics_grading/skills/initial.md
  split_mode: split_dir
  split_dir: /absolute/path/to/exam-automark/Data/physics/benchmark/skillopt/physics-week9-text-split-v1
  workers: 2
  max_completion_tokens: 4096
  limit: 0
```

## initial.md

Use the current grading skill as the initial skill, not a blank file. Copy the
relevant physics grading section from:

```text
exam-automark/.agents/skills/grade-homework/SKILL.md
```

## First Run

Start with one short run:

```bash
python scripts/train.py --config configs/physics_grading/default.yaml
```

Expected useful artifacts:

```text
outputs/<run-name>/best_skill.md
outputs/<run-name>/history.json
outputs/<run-name>/config.json
```

Send back `best_skill.md`, `history.json`, and the exact command line. The
exam-automark repo will evaluate the returned skill against the existing metrics
pipeline and then, only after candidate selection, against held-out test.
