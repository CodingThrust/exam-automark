import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from PIL import Image, ImageDraw

from benchmark.core.grading_mask_workflow import (
    MASK_CANDIDATE_DECISION_COLUMNS,
    PAGE_SWEEP_COLUMNS,
    build_artifact_manifest,
    build_candidate_manifest,
    candidate_decision_rows,
    canonical_json_sha256,
    compile_approved_page_masks,
    page_sweep_rows,
    propose_red_ink_candidates,
    validate_artifact_manifest,
    validate_compiled_mask_provenance,
    validate_mask_review_workflow,
    write_csv,
)


class GradingMaskWorkflowTests(unittest.TestCase):
    def test_red_ink_detector_proposes_component_and_honors_exclusion(self):
        image = Image.new("RGB", (200, 100), "white")
        ImageDraw.Draw(image).line((150, 50, 175, 70), fill=(220, 10, 10), width=4)

        proposed = propose_red_ink_candidates(image, excluded_rectangles=[])
        excluded = propose_red_ink_candidates(
            image,
            excluded_rectangles=[{"left": 0.7, "top": 0.4, "right": 0.95, "bottom": 0.8}],
        )

        self.assertTrue(proposed)
        self.assertEqual(excluded, [])

    def test_pending_candidates_and_sweeps_block_compilation(self):
        layout, manifest = _layout_and_manifest()
        report = validate_mask_review_workflow(
            layout=layout,
            layout_sha256=manifest["layout_sha256"],
            candidate_manifest=manifest,
            decision_rows=candidate_decision_rows(manifest),
            decision_columns=MASK_CANDIDATE_DECISION_COLUMNS,
            sweep_rows=page_sweep_rows(layout),
            sweep_columns=PAGE_SWEEP_COLUMNS,
        )

        self.assertEqual(report["status"], "not_ready")
        self.assertIn("all_candidates_resolved", report["failed_checks"])
        self.assertIn("all_page_sweeps_completed", report["failed_checks"])

    def test_compile_requires_reviewed_candidate_and_page_sweep(self):
        layout, manifest = _layout_and_manifest()
        decisions = candidate_decision_rows(manifest)
        decisions[0].update(
            {
                "decision_status": "accepted",
                "reviewer": "reviewer",
                "reviewed_at": "2026-08-02T00:00:00Z",
                "notes": "red marker",
            }
        )
        sweeps = page_sweep_rows(layout)
        sweeps[0].update(
            {
                "sweep_status": "completed",
                "reviewer": "reviewer",
                "reviewed_at": "2026-08-02T00:00:00Z",
                "added_rectangles": '[{"left":0.1,"top":0.8,"right":0.2,"bottom":0.9}]',
            }
        )

        compiled = compile_approved_page_masks(
            base_layout=layout,
            base_layout_sha256=manifest["layout_sha256"],
            candidate_manifest=manifest,
            decision_rows=decisions,
            decision_columns=MASK_CANDIDATE_DECISION_COLUMNS,
            sweep_rows=sweeps,
            sweep_columns=PAGE_SWEEP_COLUMNS,
            candidate_manifest_sha256="a" * 64,
            decision_sha256="b" * 64,
            sweep_sha256="c" * 64,
        )

        masks = compiled["page_groups"][0]["page_masks"]
        self.assertEqual(len(masks), 1)
        self.assertEqual(len(masks[0]["rectangles"]), 2)
        self.assertEqual(compiled["grading_mask_review"]["candidate_count"], 1)

    def test_provenance_binds_compiled_layout_to_review_files(self):
        layout, manifest = _layout_and_manifest()
        decisions = candidate_decision_rows(manifest)
        decisions[0].update(
            {
                "decision_status": "accepted",
                "reviewer": "reviewer",
                "reviewed_at": "2026-08-02T00:00:00Z",
                "notes": "red marker",
            }
        )
        sweeps = page_sweep_rows(layout)
        sweeps[0].update(
            {
                "sweep_status": "completed",
                "reviewer": "reviewer",
                "reviewed_at": "2026-08-02T00:00:00Z",
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base_layout_path = root / "base-layout.json"
            manifest_path = root / "candidate-manifest.json"
            decisions_path = root / "candidate-decisions.csv"
            sweeps_path = root / "page-sweeps.csv"
            base_layout_path.write_text(json.dumps(layout), encoding="utf-8")
            manifest["layout_sha256"] = _sha(base_layout_path)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            write_csv(
                decisions_path,
                columns=MASK_CANDIDATE_DECISION_COLUMNS,
                rows=decisions,
            )
            write_csv(sweeps_path, columns=PAGE_SWEEP_COLUMNS, rows=sweeps)
            compiled = compile_approved_page_masks(
                base_layout=layout,
                base_layout_sha256=_sha(base_layout_path),
                candidate_manifest=manifest,
                decision_rows=decisions,
                decision_columns=MASK_CANDIDATE_DECISION_COLUMNS,
                sweep_rows=sweeps,
                sweep_columns=PAGE_SWEEP_COLUMNS,
                candidate_manifest_sha256=_sha(manifest_path),
                decision_sha256=_sha(decisions_path),
                sweep_sha256=_sha(sweeps_path),
            )
            valid = validate_compiled_mask_provenance(
                layout=compiled,
                base_layout_path=base_layout_path,
                candidate_manifest_path=manifest_path,
                decision_path=decisions_path,
                sweep_path=sweeps_path,
            )
            decisions[0]["notes"] = "changed after compile"
            write_csv(
                decisions_path,
                columns=MASK_CANDIDATE_DECISION_COLUMNS,
                rows=decisions,
            )
            changed = validate_compiled_mask_provenance(
                layout=compiled,
                base_layout_path=base_layout_path,
                candidate_manifest_path=manifest_path,
                decision_path=decisions_path,
                sweep_path=sweeps_path,
            )

        self.assertEqual(valid["status"], "ready")
        self.assertEqual(changed["status"], "not_ready")
        self.assertIn("candidate_decisions_sha256_matches", changed["failed_checks"])

    def test_provenance_rejects_wrong_base_extra_masks_and_nonmask_tampering(self):
        layout, manifest = _layout_and_manifest()
        decisions = candidate_decision_rows(manifest)
        decisions[0].update(
            {
                "decision_status": "accepted",
                "reviewer": "reviewer",
                "reviewed_at": "2026-08-02T00:00:00Z",
                "notes": "red marker",
            }
        )
        sweeps = page_sweep_rows(layout)
        sweeps[0].update(
            {
                "sweep_status": "completed",
                "reviewer": "reviewer",
                "reviewed_at": "2026-08-02T00:00:00Z",
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base_layout_path = root / "base-layout.json"
            manifest_path = root / "candidate-manifest.json"
            decisions_path = root / "candidate-decisions.csv"
            sweeps_path = root / "page-sweeps.csv"
            base_layout_path.write_text(json.dumps(layout), encoding="utf-8")
            manifest["layout_sha256"] = _sha(base_layout_path)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            write_csv(
                decisions_path,
                columns=MASK_CANDIDATE_DECISION_COLUMNS,
                rows=decisions,
            )
            write_csv(sweeps_path, columns=PAGE_SWEEP_COLUMNS, rows=sweeps)
            compiled = compile_approved_page_masks(
                base_layout=layout,
                base_layout_sha256=_sha(base_layout_path),
                candidate_manifest=manifest,
                decision_rows=decisions,
                decision_columns=MASK_CANDIDATE_DECISION_COLUMNS,
                sweep_rows=sweeps,
                sweep_columns=PAGE_SWEEP_COLUMNS,
                candidate_manifest_sha256=_sha(manifest_path),
                decision_sha256=_sha(decisions_path),
                sweep_sha256=_sha(sweeps_path),
            )
            extra_mask = deepcopy(compiled)
            extra_mask["page_groups"][0]["page_masks"].append(
                {
                    "source_page": 1,
                    "reason": "unapproved_extra_mask",
                    "rectangles": [
                        {"left": 0.0, "top": 0.0, "right": 0.1, "bottom": 0.1}
                    ],
                }
            )
            nonmask_tamper = deepcopy(compiled)
            nonmask_tamper["assessment_id"] = "tampered-assessment"
            wrong_base = deepcopy(layout)
            wrong_base["assessment_id"] = "different-base"
            wrong_base_path = root / "wrong-base-layout.json"
            wrong_base_path.write_text(json.dumps(wrong_base), encoding="utf-8")

            extra_mask_report = validate_compiled_mask_provenance(
                layout=extra_mask,
                base_layout_path=base_layout_path,
                candidate_manifest_path=manifest_path,
                decision_path=decisions_path,
                sweep_path=sweeps_path,
            )
            nonmask_report = validate_compiled_mask_provenance(
                layout=nonmask_tamper,
                base_layout_path=base_layout_path,
                candidate_manifest_path=manifest_path,
                decision_path=decisions_path,
                sweep_path=sweeps_path,
            )
            wrong_base_report = validate_compiled_mask_provenance(
                layout=compiled,
                base_layout_path=wrong_base_path,
                candidate_manifest_path=manifest_path,
                decision_path=decisions_path,
                sweep_path=sweeps_path,
            )

        self.assertEqual(extra_mask_report["status"], "not_ready")
        self.assertIn(
            "compiled_layout_exactly_matches_reviewed_base",
            extra_mask_report["failed_checks"],
        )
        self.assertEqual(nonmask_report["status"], "not_ready")
        self.assertIn(
            "compiled_layout_exactly_matches_reviewed_base",
            nonmask_report["failed_checks"],
        )
        self.assertEqual(wrong_base_report["status"], "not_ready")
        self.assertIn("base_layout_sha256_matches", wrong_base_report["failed_checks"])

    def test_artifact_manifest_detects_changed_output(self):
        layout, _manifest = _layout_and_manifest()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_path = root / "anonymized_pages" / "S001" / "S001-p01.png"
            pdf_path = root / "anonymized_pdfs" / "S001.pdf"
            image_path.parent.mkdir(parents=True)
            pdf_path.parent.mkdir(parents=True)
            image_path.write_bytes(b"synthetic image")
            pdf_path.write_bytes(b"synthetic pdf")
            artifact_manifest = build_artifact_manifest(
                output_root=root,
                layout=layout,
                render_spec_sha256="d" * 64,
            )
            ready = validate_artifact_manifest(
                output_root=root,
                layout=layout,
                manifest=artifact_manifest,
                render_spec_sha256="d" * 64,
            )
            image_path.write_bytes(b"changed")
            changed = validate_artifact_manifest(
                output_root=root,
                layout=layout,
                manifest=artifact_manifest,
                render_spec_sha256="d" * 64,
            )

        self.assertEqual(ready["status"], "ready")
        self.assertEqual(changed["status"], "not_ready")
        self.assertIn("prepared_output_hashes_match", changed["failed_checks"])

    def test_artifact_manifest_rejects_unreviewed_extra_output_file(self):
        layout, _manifest = _layout_and_manifest()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_path = root / "anonymized_pages" / "S001" / "S001-p01.png"
            pdf_path = root / "anonymized_pdfs" / "S001.pdf"
            image_path.parent.mkdir(parents=True)
            pdf_path.parent.mkdir(parents=True)
            image_path.write_bytes(b"synthetic image")
            pdf_path.write_bytes(b"synthetic pdf")
            artifact_manifest = build_artifact_manifest(
                output_root=root,
                layout=layout,
                render_spec_sha256="d" * 64,
            )
            extra_path = root / "anonymized_pages" / "S001" / "unreviewed-extra.png"
            extra_path.write_bytes(b"unexpected image")

            report = validate_artifact_manifest(
                output_root=root,
                layout=layout,
                manifest=artifact_manifest,
                render_spec_sha256="d" * 64,
            )

        self.assertEqual(report["status"], "not_ready")
        self.assertIn(
            "prepared_output_tree_matches_expected_paths", report["failed_checks"]
        )


def _layout_and_manifest() -> tuple[dict[str, object], dict[str, object]]:
    layout: dict[str, object] = {
        "schema_version": 1,
        "assessment_id": "synthetic",
        "source_sha256": "a" * 64,
        "expected_page_count": 1,
        "page_groups": [
            {"anonymous_id": "S001", "source_pages": [1], "page_masks": []}
        ],
        "excluded_pages": [],
    }
    layout_hash = canonical_json_sha256(layout)
    manifest = build_candidate_manifest(
        layout=layout,
        layout_sha256=layout_hash,
        candidates=[
            {
                "candidate_id": "C0001",
                "anonymous_id": "S001",
                "source_page": 1,
                "rectangles": [
                    {"left": 0.7, "top": 0.1, "right": 0.8, "bottom": 0.2}
                ],
                "detector": "synthetic",
                "confidence": 0.8,
                "rationale": "synthetic candidate",
            }
        ],
        detector={"name": "synthetic"},
    )
    return layout, manifest


def _sha(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
