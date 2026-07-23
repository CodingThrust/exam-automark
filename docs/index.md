---
title: Exam Automark Reproducible Test Hub
---

# Exam Automark Reproducible Test Hub

This GitHub Pages folder contains reviewer-facing instructions for reproducing
AI grading experiments without exposing private student data.

## Start Here

- [AI Grading Test Handoff](ai-grading-test-handoff.md)

The handoff page is written so an external AI assistant, Kimi Code, or Claude
Code can read it and immediately understand:

- how to invoke the cross-agent `run-submit-grading-benchmark` repository skill;
- how the agent proactively diagnoses and helps configure missing environment pieces;
- how the invited advisor-owned GitLab account can restore the private `Data/` folder from YY's HKUST-GZ GitLab repo;
- how to run matched Kimi/Claude text-only and multimodal arms;
- how successes and failures are validated and packaged;
- how a focused GitHub pull request is opened automatically;
- what privacy boundaries must not be crossed.
