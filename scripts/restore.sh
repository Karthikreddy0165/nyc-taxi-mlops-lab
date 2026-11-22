#!/usr/bin/env bash
# scripts/restore.sh: restore lab services after an overnight pause or session timeout (S4).
# Starts stopped RDS and paused Redshift, updates laptop IP in tfvars if needed,
# and waits until health.sh exits 0.
set -euo pipefail

export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
export AWS_PAGER=""

root="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Checking AWS session credentials..."
if ! who=$(aws sts get-caller-identity --query Arn --output text 2>&1); then
  echo "FAIL: AWS credentials are not valid or expired." >&2
  echo "Please export fresh credentials from AWS Academy Learner Lab and re-run." >&2
  echo "$who" >&2
  exit 1
fi
echo "OK: Authenticated as ${who##*/}"

# 1. Update laptop IP in terraform.tfvars if changed
tfvars="$root/infra/live/terraform.tfvars"
if ip=$(curl -fsS -m 5 https://checkip.amazonaws.com 2>/dev/null); then
  if ! grep -q "\"$ip/32\"" "$tfvars" 2>/dev/null; then
    echo "==> Updating laptop IP ($ip/32) in $tfvars..."
    if grep -q "ingress_cidrs" "$tfvars"; then
      # If ingress_cidrs already exists, append or update with current IP
      if grep -q "0.0.0.0/0" "$tfvars"; then
        sed -i '' "s|ingress_cidrs = \[.*\]|ingress_cidrs = [\"0.0.0.0/0\", \"$ip/32\"]|" "$tfvars" 2>/dev/null || \
        sed -i "s|ingress_cidrs = \[.*\]|ingress_cidrs = [\"0.0.0.0/0\", \"$ip/32\"]|" "$tfvars"
      else
        sed -i '' "s|ingress_cidrs = \[.*\]|ingress_cidrs = [\"$ip/32\"]|" "$tfvars" 2>/dev/null || \
        sed -i "s|ingress_cidrs = \[.*\]|ingress_cidrs = [\"$ip/32\"]|" "$tfvars"
      fi
    else
      echo "ingress_cidrs = [\"0.0.0.0/0\", \"$ip/32\"]" >> "$tfvars"
    fi
    echo "OK: Laptop IP updated."
  else
    echo "OK: Laptop IP ($ip/32) is already present in $tfvars."
  fi
fi

# 2. Check and start EC2 instances if stopped
echo "==> Checking EC2 instances..."
stopped_instances=$(aws ec2 describe-instances \
  --filters Name=tag:project,Values=mlops-lab Name=instance-state-name,Values=stopped \
  --query 'Reservations[].Instances[].InstanceId' --output text 2>/dev/null || echo "")

if [[ -n "$stopped_instances" && "$stopped_instances" != "None" ]]; then
  echo "Starting stopped EC2 instances: $stopped_instances"
  # shellcheck disable=SC2086
  aws ec2 start-instances --instance-ids $stopped_instances >/dev/null
  echo "Waiting for EC2 instances to become running..."
  # shellcheck disable=SC2086
  aws ec2 wait instance-running --instance-ids $stopped_instances
  echo "OK: EC2 instances are running."
else
  echo "OK: All EC2 instances are running."
fi

# 3. Check and start RDS
echo "==> Checking RDS instance 'lab'..."
rds_status=$(aws rds describe-db-instances --db-instance-identifier lab --query 'DBInstances[0].DBInstanceStatus' --output text 2>/dev/null || echo absent)
if [[ "$rds_status" == "stopped" ]]; then
  echo "RDS is stopped. Starting RDS instance 'lab' (typically takes 5-7 minutes)..."
  aws rds start-db-instance --db-instance-identifier lab >/dev/null
  echo "Waiting for RDS instance to be available..."
  aws rds wait db-instance-available --db-instance-identifier lab
  echo "OK: RDS instance is available."
elif [[ "$rds_status" == "starting" ]]; then
  echo "RDS is starting. Waiting for db-instance-available..."
  aws rds wait db-instance-available --db-instance-identifier lab
  echo "OK: RDS instance is available."
elif [[ "$rds_status" == "available" ]]; then
  echo "OK: RDS instance is already available."
else
  echo "Note: RDS status is '$rds_status'."
fi

# 4. Check and resume Redshift
echo "==> Checking Redshift cluster 'lab'..."
rs_status=$(aws redshift describe-clusters --cluster-identifier lab --query 'Clusters[0].ClusterStatus' --output text 2>/dev/null || echo absent)
if [[ "$rs_status" == "paused" ]]; then
  echo "Redshift is paused. Resuming Redshift cluster 'lab' (typically takes ~3 minutes)..."
  aws redshift resume-cluster --cluster-identifier lab >/dev/null
  echo "Waiting for Redshift cluster to be available..."
  aws redshift wait cluster-available --cluster-identifier lab
  echo "OK: Redshift cluster is available."
elif [[ "$rs_status" == "resuming" ]]; then
  echo "Redshift is resuming. Waiting for cluster-available..."
  aws redshift wait cluster-available --cluster-identifier lab
  echo "OK: Redshift cluster is available."
elif [[ "$rs_status" == "available" ]]; then
  echo "OK: Redshift cluster is already available."
else
  echo "Note: Redshift status is '$rs_status'."
fi

# 5. Run health check
echo "==> Verifying overall system health via scripts/health.sh..."
"$root/scripts/health.sh"
echo "==> Service restore complete and verified!"
