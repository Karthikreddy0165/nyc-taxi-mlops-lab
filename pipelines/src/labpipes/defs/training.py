"""S2: training_set, trained_model, eval_report, the challenger gate and the challenger asset.

- training_set: UNLOAD a window of staging.trip_features (and the holdout month) to the artifact bucket.
  The zone-pair distance lookup (contracts/features.yaml, est_distance_miles) comes from the window only.
- trained_model: fit tripmodel.LightGBMModel (the given v2), log it to MLflow as a pyfunc with
  tripmodel.model_signature() and the tripmodel package bundled, register a version of the model named
  in contracts/mlflow.yaml, and tag it as that contract says.
- eval_report: tripmodel.evaluate the new version and the champion (or the v1 baseline before there is
  one) on the same holdout; log the metrics.
- beats_champion: blocking check guarding the challenger asset.
- challenger: sets the challenger alias in MLflow. The pipeline never moves champion.
"""

import os
from pathlib import Path
import subprocess

import dagster as dg
import tripmodel
from tripmodel import (
    REQUIRED,
    BaselineModel,
    LightGBMModel,
    evaluate,
    model_signature,
)

from ..contracts import mlflow_contract
from ..resources import ArtifactBucket, MlflowTracking, RedshiftData

PROMOTION_MARGIN_MIN = 0.10  # Decision 008: candidate must beat champion by at least 6 seconds
LATENCY_BUDGET_MS = 10.0     # Decision 008: p95 latency under 10 ms


def _get_git_sha() -> str:
    for env_key in ("GIT_COMMIT_SHA", "GITHUB_SHA"):
        val = os.environ.get(env_key)
        if val:
            return val
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unknown"


@dg.asset(
    deps=["trip_features"],
    group_name="model",
    kinds={"redshift", "s3"},
    pool="redshift",
    description="UNLOAD the 3-month training window and holdout month from Redshift to the artifact bucket",
)
def training_set(context: dg.AssetExecutionContext, redshift: RedshiftData, artifacts: ArtifactBucket) -> dg.MaterializeResult:
    train_sql = (
        f"unload ('select pickup_zone_id, dropoff_zone_id, pickup_hour, pickup_dow, duration_min "
        f"from staging.trip_features where trip_month in (''2024-01'', ''2024-02'', ''2024-03'')') "
        f"to 's3://{artifacts.bucket}/training/train' iam_role default format as parquet allowoverwrite"
    )
    holdout_sql = (
        f"unload ('select pickup_zone_id, dropoff_zone_id, pickup_hour, pickup_dow, duration_min "
        f"from staging.trip_features where trip_month in (''2024-04'')') "
        f"to 's3://{artifacts.bucket}/training/holdout' iam_role default format as parquet allowoverwrite"
    )
    dist_sql = (
        f"unload ('select pickup_zone_id, dropoff_zone_id, median(trip_distance) as est_distance_miles "
        f"from staging.stg_trips where trip_month in (''2024-01'', ''2024-02'', ''2024-03'') "
        f"and duration_min > 0 and duration_min <= 180 and trip_distance > 0 group by 1, 2') "
        f"to 's3://{artifacts.bucket}/training/distances' iam_role default format as parquet allowoverwrite"
    )
    redshift.execute(train_sql, holdout_sql, dist_sql)

    counts = redshift.query(
        "select sum(case when trip_month in ('2024-01', '2024-02', '2024-03') then 1 else 0 end) as train, "
        "sum(case when trip_month = '2024-04' then 1 else 0 end) as holdout from staging.trip_features"
    )
    train_rows = int(counts[0]["train"]) if counts and counts[0].get("train") else 0
    holdout_rows = int(counts[0]["holdout"]) if counts and counts[0].get("holdout") else 0

    return dg.MaterializeResult(
        metadata={
            "training_window": "2024-01..2024-03",
            "holdout_month": "2024-04",
            "train_rows": dg.MetadataValue.int(train_rows),
            "holdout_rows": dg.MetadataValue.int(holdout_rows),
        }
    )


@dg.asset(
    deps=["training_set"],
    group_name="model",
    kinds={"mlflow", "python"},
    description="Train LightGBM model on training_set and register version in MLflow with required tags",
)
def trained_model(context: dg.AssetExecutionContext, artifacts: ArtifactBucket, tracking: MlflowTracking) -> dg.MaterializeResult:
    import mlflow

    train = artifacts.read_parquet("training/train")
    distances = artifacts.read_parquet("training/distances")
    train[REQUIRED] = train[REQUIRED].astype("int64")

    contract = mlflow_contract()
    model = LightGBMModel().fit(train, distances, num_rounds=200)

    mlflow.set_tracking_uri(tracking.tracking_uri)
    mlflow.set_experiment(contract["experiment"])

    code_dir = str(Path(tripmodel.__file__).parent)
    with mlflow.start_run(run_name="train_model") as run:
        info = mlflow.pyfunc.log_model(
            name="model",
            python_model=model,
            signature=model_signature(),
            code_paths=[code_dir],
            registered_model_name=contract["registered_model"],
        )
        run_id = run.info.run_id

    version = str(info.registered_model_version)
    client = tracking.client()
    tags = {
        "training_window": "2024-01..2024-03",
        "holdout_month": "2024-04",
        "features_version": "1",
        "git_sha": _get_git_sha(),
    }
    for k, v in tags.items():
        client.set_model_version_tag(contract["registered_model"], version, k, str(v))

    return dg.MaterializeResult(
        metadata={
            "registered_model": contract["registered_model"],
            "version": version,
            "run_id": run_id,
            "train_rows": dg.MetadataValue.int(len(train)),
            **{k: dg.MetadataValue.text(v) for k, v in tags.items()},
        }
    )


@dg.asset(
    deps=["trained_model"],
    group_name="model",
    kinds={"mlflow", "python"},
    description="Evaluate candidate model against champion (or baseline) on holdout and log metrics",
)
def eval_report(
    context: dg.AssetExecutionContext,
    artifacts: ArtifactBucket,
    tracking: MlflowTracking,
    redshift: RedshiftData,
) -> dg.MaterializeResult:
    import mlflow

    holdout = artifacts.read_parquet("training/holdout")
    holdout[REQUIRED] = holdout[REQUIRED].astype("int64")

    borough_rows = redshift.query("select location_id, borough from ingest.taxi_zones")
    boroughs = {int(r["location_id"]): r["borough"] for r in borough_rows}

    contract = mlflow_contract()
    client = tracking.client()
    versions = client.search_model_versions(f"name = '{contract['registered_model']}'")
    candidate_mv = max(versions, key=lambda v: int(v.version))
    candidate_version = str(candidate_mv.version)

    mlflow.set_tracking_uri(tracking.tracking_uri)
    mlflow.set_experiment(contract["experiment"])

    candidate_model = mlflow.pyfunc.load_model(f"models:/{contract['registered_model']}/{candidate_version}")
    candidate_metrics = evaluate(candidate_model.predict, holdout, boroughs, latency_samples=200)

    # Compare against champion if exists, else compare against v1 BaselineModel
    champ_mae = None
    try:
        champ_mv = client.get_model_version_by_alias(contract["registered_model"], "champion")
        champ_model = mlflow.pyfunc.load_model(f"models:/{contract['registered_model']}@{champ_mv.alias}")
        champ_metrics = evaluate(champ_model.predict, holdout, boroughs, latency_samples=200)
        champ_mae = champ_metrics["mae_min"]
    except Exception:
        distances = artifacts.read_parquet("training/distances")
        train = artifacts.read_parquet("training/train")
        train[REQUIRED] = train[REQUIRED].astype("int64")
        v1 = BaselineModel().fit(train, distances)
        v1_metrics = evaluate(lambda df: v1.predict(None, df), holdout, boroughs, latency_samples=200)
        champ_mae = v1_metrics["mae_min"]

    metrics = {
        "mae_min": float(candidate_metrics["mae_min"]),
        "p95_latency_ms": float(candidate_metrics["p95_latency_ms"]),
        "champion_mae_min": float(champ_mae),
        "mae_min.airport": float(candidate_metrics.get("mae_min.airport", 0.0)),
        "mae_min.manhattan": float(candidate_metrics.get("mae_min.manhattan", 0.0)),
        "mae_min.outer": float(candidate_metrics.get("mae_min.outer", 0.0)),
        "mae_min.night": float(candidate_metrics.get("mae_min.night", 0.0)),
    }

    # Set required metric tags on model version as specified in contracts/mlflow.yaml
    for tag_name in ("mae_min", "p95_latency_ms", "champion_mae_min"):
        client.set_model_version_tag(contract["registered_model"], candidate_version, tag_name, str(round(metrics[tag_name], 4)))

    if candidate_mv.run_id:
        with mlflow.start_run(run_id=candidate_mv.run_id):
            mlflow.log_metrics(metrics)

    return dg.MaterializeResult(
        metadata={
            "version": candidate_version,
            **{k: dg.MetadataValue.float(v) for k, v in metrics.items()},
        }
    )


@dg.asset_check(
    asset=eval_report,
    blocking=True,
    description="Verify candidate model beats champion/baseline by margin within latency budget",
)
def beats_champion(context: dg.AssetCheckExecutionContext) -> dg.AssetCheckResult:
    event = context.instance.get_latest_materialization_event(dg.AssetKey("eval_report"))
    md = event.asset_materialization.metadata if event and event.asset_materialization else {}

    mae = float(md["mae_min"].value) if "mae_min" in md else 999.0
    champ_mae = float(md["champion_mae_min"].value) if "champion_mae_min" in md else 0.0
    latency = float(md["p95_latency_ms"].value) if "p95_latency_ms" in md else 999.0

    passed_mae = mae <= (champ_mae - PROMOTION_MARGIN_MIN)
    passed_latency = latency <= LATENCY_BUDGET_MS
    passed = passed_mae and passed_latency

    issues = []
    if not passed_mae:
        issues.append(
            f"MAE {mae:.3f} did not beat target {champ_mae - PROMOTION_MARGIN_MIN:.3f} "
            f"(champion: {champ_mae:.3f}, margin: {PROMOTION_MARGIN_MIN:.2f})"
        )
    if not passed_latency:
        issues.append(f"p95 latency {latency:.2f}ms exceeded budget {LATENCY_BUDGET_MS:.1f}ms")

    return dg.AssetCheckResult(
        passed=passed,
        severity=dg.AssetCheckSeverity.ERROR,
        description="Candidate beats champion/baseline within latency budget" if passed else "; ".join(issues),
        metadata={
            "mae_min": dg.MetadataValue.float(mae),
            "champion_mae_min": dg.MetadataValue.float(champ_mae),
            "p95_latency_ms": dg.MetadataValue.float(latency),
            "margin_min": dg.MetadataValue.float(PROMOTION_MARGIN_MIN),
            "latency_budget_ms": dg.MetadataValue.float(LATENCY_BUDGET_MS),
        },
    )


@dg.asset(
    deps=[eval_report],
    group_name="model",
    kinds={"mlflow"},
    description="Promote evaluated model version to challenger alias in MLflow",
)
def challenger(context: dg.AssetExecutionContext, tracking: MlflowTracking) -> dg.MaterializeResult:
    contract = mlflow_contract()
    client = tracking.client()
    versions = client.search_model_versions(f"name = '{contract['registered_model']}'")
    latest_version = max(versions, key=lambda v: int(v.version))
    version_str = str(latest_version.version)

    client.set_registered_model_alias(contract["registered_model"], "challenger", version_str)
    context.log.info(f"Assigned alias 'challenger' to {contract['registered_model']} version {version_str}")

    return dg.MaterializeResult(
        metadata={
            "registered_model": contract["registered_model"],
            "version": version_str,
            "alias": "challenger",
        }
    )


train_model = dg.define_asset_job(
    "train_model",
    selection=dg.AssetSelection.assets(training_set, trained_model, eval_report, challenger) | dg.AssetSelection.checks(beats_champion),
    description="Trains LightGBM model on window and promotes to challenger alias if gate check passes",
)
