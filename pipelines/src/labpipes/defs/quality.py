"""S1: data-quality checks on stg_trips (nulls, ranges, duplicates, row counts)."""

import dagster as dg

from ..partitions import trip_months
from ..resources import RedshiftData


@dg.asset_check(
    asset="stg_trips",
    name="plausible_row_count",
    partitions_def=trip_months,
    blocking=True,
    description="Monthly row count must be between 1,000,000 and 10,000,000 to catch truncated files.",
)
def plausible_row_count(context: dg.AssetCheckExecutionContext, redshift: RedshiftData) -> dg.AssetCheckResult:
    month = context.partition_key
    rows = int(redshift.scalar(f"select count(*) from staging.stg_trips where trip_month = '{month}'"))
    passed = 1_000_000 <= rows <= 10_000_000
    return dg.AssetCheckResult(
        passed=passed,
        severity=dg.AssetCheckSeverity.ERROR,
        description=f"Row count {rows:,} is within expected monthly bounds" if passed else f"Unexpected row count: {rows:,}",
        metadata={"rows": dg.MetadataValue.int(rows)},
    )


@dg.asset_check(
    asset="stg_trips",
    name="valid_timestamps",
    partitions_def=trip_months,
    blocking=False,
    description="Pickups and dropoffs must be non-null with pickup <= dropoff.",
)
def valid_timestamps(context: dg.AssetCheckExecutionContext, redshift: RedshiftData) -> dg.AssetCheckResult:
    month = context.partition_key
    invalid = int(
        redshift.scalar(
            f"select count(*) from staging.stg_trips where trip_month = '{month}' and "
            "(pickup_at is null or dropoff_at is null or pickup_at > dropoff_at)"
        )
    )
    passed = invalid == 0
    return dg.AssetCheckResult(
        passed=passed,
        severity=dg.AssetCheckSeverity.WARN,
        description=f"{invalid} trips with invalid timestamps" if not passed else "All timestamps valid",
        metadata={"invalid_timestamp_count": dg.MetadataValue.int(invalid)},
    )
