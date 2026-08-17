# Model release policies

These public policy files make model-release choices explicit for future runs.
They do not alter historic run records or authorize a model call.

A runner can bind a policy with `--model-release-policy`. The policy hash and
the selected release channel are then recorded in private run metadata. A
provisional model requires an explicit `--allow-provisional-model` acknowledgement
so it cannot be mistaken for the current default.
