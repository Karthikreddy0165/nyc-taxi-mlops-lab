# 007: What stays in the notebook vs. what moves into the pipeline

Stage: S2 · Date: 2026-11-21 · Author: karthik · Drafted by agent: yes

## Choice

Exploratory data analysis, ad-hoc distribution profiling, slice visual inspections, and candidate model experimentation stay in the SageMaker notebook (logging only to ephemeral experiment `trip-duration-notebook`). Automated ETL, feature extraction & contract validation (`staging.trip_features`, `feature_contract`), scheduled training (`training_set`, `trained_model`), model packaging (`pyfunc`), holdout evaluation against champion (`eval_report`, `beats_champion`), MLflow model registry versioning, and `challenger` alias promotion belong strictly in the Dagster pipeline.

## Rejected alternative

Training and registering production candidate models directly from the SageMaker notebook, or manually moving the `challenger` alias in MLflow from the notebook.

## Why

Notebooks are exploratory and iterative environments with mutable cell states and non-deterministic execution orders. Allowing models to be registered or promoted to `challenger` from a notebook risks untracked dependencies, missing code artifacts, schema mismatch, unvalidated target leakage, and human error. In contrast, Dagster orchestrates reproducible assets with strict input/label validation (`feature_contract`), automated holdout gate checks (`beats_champion`), and audited MLflow version tagging without manual intervention.

## What would show this was wrong

If data scientists find the pipeline transition too rigid for hyperparameter exploration, or if simple feature experiments take excessive engineering turnaround time to test in the pipeline before any exploratory signal is visible.
