"""S1: the S3 sensor and the ingest_month job it starts."""

import json

import dagster as dg

from ..partitions import trip_months
from ..resources import DataBucket

ingest_month = dg.define_asset_job(
    "ingest_month",
    selection=dg.AssetSelection.assets("trip_files", "raw_trips", "stg_trips", "trip_features", "zone_hour_stats"),
    partitions_def=trip_months,
    description="Loads one month of trip data from S3, checks schema, and populates the mart.",
)


@dg.sensor(job=ingest_month, minimum_interval_seconds=60)
def trip_files_sensor(context: dg.SensorEvaluationContext, data_bucket: DataBucket):
    seen = set(json.loads(context.cursor or "[]"))
    files = data_bucket.trip_files()
    new_files = [f for f in files if f.month not in seen]
    if not new_files:
        return dg.SkipReason("No new trip files found in data bucket")

    new_months = [f.month for f in new_files]
    return dg.SensorResult(
        run_requests=[dg.RunRequest(partition_key=f.month, run_key=f"{f.month}:{f.etag}") for f in new_files],
        dynamic_partitions_requests=[trip_months.build_add_request(new_months)],
        cursor=json.dumps(sorted(seen | set(new_months))),
    )
