"""S2: the feature_contract check on trip_features."""

import dagster as dg

from ..contracts import features_contract
from ..partitions import check_month, trip_months
from ..resources import RedshiftData


@dg.asset_check(
    asset="trip_features",
    partitions_def=trip_months,
    blocking=True,
    description="Validate staging.trip_features schema, forbidden columns, and value ranges against contracts/features.yaml",
)
def feature_contract(context: dg.AssetCheckExecutionContext, redshift: RedshiftData) -> dg.AssetCheckResult:
    month = check_month(context.partition_key)
    contract = features_contract()
    expected_cols = {c["name"].lower() for c in contract["keys"] + contract["inputs"] + [contract["label"]]}
    forbidden_cols = {c.lower() for c in contract.get("forbidden", [])}

    cols_query = (
        "select column_name from information_schema.columns "
        "where table_schema = 'staging' and table_name = 'trip_features'"
    )
    cols = {r["column_name"].lower() for r in redshift.query(cols_query)}

    missing_cols = expected_cols - cols
    present_forbidden = forbidden_cols & cols

    issues = []
    if missing_cols:
        issues.append(f"missing expected columns: {sorted(missing_cols)}")
    if present_forbidden:
        issues.append(f"forbidden post-trip columns present (target leakage!): {sorted(present_forbidden)}")

    range_check = redshift.scalar(
        f"select count(*) from staging.trip_features "
        f"where trip_month = '{month}' and ("
        f"  duration_min <= 0 or duration_min > 180 "
        f"  or pickup_zone_id not between 1 and 263 "
        f"  or dropoff_zone_id not between 1 and 263 "
        f"  or pickup_hour not between 0 and 23 "
        f"  or pickup_dow not between 0 and 6"
        f")"
    )
    if int(range_check) > 0:
        issues.append(f"{range_check} rows outside valid feature/label ranges")

    total_rows = redshift.scalar(
        f"select count(*) from staging.trip_features where trip_month = '{month}'"
    )
    if int(total_rows) == 0:
        issues.append(f"0 rows found for month {month}")

    passed = len(issues) == 0
    return dg.AssetCheckResult(
        passed=passed,
        severity=dg.AssetCheckSeverity.ERROR,
        description="Features conform to contracts/features.yaml with zero forbidden columns" if passed else "; ".join(issues),
        metadata={
            "month": month,
            "total_rows": dg.MetadataValue.int(int(total_rows)),
            "out_of_bounds_rows": dg.MetadataValue.int(int(range_check)),
            "columns": dg.MetadataValue.json(sorted(cols)),
            "issues": dg.MetadataValue.json(issues),
        },
    )
