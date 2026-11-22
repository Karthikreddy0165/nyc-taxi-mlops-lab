# Runbook: restore service after overnight shutdown

Owner: karthik · Last run: 2026-11-22 · Time to restore last run: 8 min

## When to use it

The app fails to quote trip durations (returns 500 or fallback 12.25 min), health checks fail on session or infrastructure states, or after a Learner Lab session expires / daily lab restart.

## Before you start

- AWS Academy Learner Lab credentials exported to terminal (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `AWS_REGION=us-east-1`).
- GitHub CLI authenticated (`gh auth status`).
- Terraform initialized in `infra/live`.

## Steps

One row per thing that was broken. Write the row while you fix it, not afterwards.

| # | Check (command) | Healthy looks like | If not: fix (command) | Took | Automated? |
| --- | --- | --- | --- | --- | --- |
| 1 | `aws sts get-caller-identity` | JSON with LabRole ARN | Export fresh AWS credentials from Learner Lab console | 1 min | no / operator must copy tokens |
| 2 | `curl -s https://checkip.amazonaws.com` & grep in `infra/live/terraform.tfvars` | Laptop IP present in `ingress_cidrs` | Update `ingress_cidrs` in `infra/live/terraform.tfvars` | 15s | yes / `scripts/restore.sh` |
| 3 | `aws ec2 describe-instances --filters Name=tag:project,Values=mlops-lab` | All EC2 instances (`platform`, `app`) `running` | `aws ec2 start-instances --instance-ids <ids>` | 1-2 min | yes / `scripts/restore.sh` |
| 4 | `aws rds describe-db-instances --db-instance-identifier lab` | `available` | `aws rds start-db-instance --db-instance-identifier lab` and wait | 6-7 min | yes / `scripts/restore.sh` |
| 5 | `aws redshift describe-clusters --cluster-identifier lab` | `available` | `aws redshift resume-cluster --cluster-identifier lab` and wait | 3 min | yes / `scripts/restore.sh` |
| 6 | `aws sagemaker describe-notebook-instance --notebook-instance-name lab` | `Stopped` or `InService` | Not required for serving/pipeline; start only when exploring | 0 min | no / left stopped to save credits |
| 7 | `gh api repos/<repo>/actions/runners` | `lab-platform` & `lab-app` `online` | systemd service on EC2 starts automatically on host boot | 30s | yes / systemd `actions.runner.*` on boot |
| 8 | `deploy/web.sh status` (app host) | `green` & `blue` running, live colour serving | `deploy/web.sh reload champion` or `docker compose up -d` | 20s | yes / Docker `restart: unless-stopped` |
| 9 | `curl -X POST http://<app_ip>/predict` | `{"alias": "champion", "version": "1"}` | Serving reloads champion model once MLflow/RDS is reachable | 15s | yes / automated in app retry/cache |
| 10 | `scripts/health.sh` | Exits 0, all lines `OK` | Check failed row above and fix | 10s | yes / `scripts/restore.sh` |

## Done when

- `curl -X POST http://<app_public_ip>/predict ...` answers with `"alias": "champion"` and the expected version.
- `scripts/health.sh` exits 0 with all components `OK`.
- GitHub Actions status workflow (`status.yaml`) runs and passes, reporting RDS and Redshift `available`.

## What we automated, and what we left as a step

See [decisions/012-restore-automation.md](../decisions/012-restore-automation.md).
- Automated: RDS start & wait, Redshift resume & wait, EC2 start check, laptop IP ingress synchronization, health check verification (`scripts/restore.sh`).
- Left manual: Refreshing Learner Lab session credentials from browser (cannot be automated without portal API access), starting SageMaker notebook (left stopped when not developing to prevent burning lab credits).
