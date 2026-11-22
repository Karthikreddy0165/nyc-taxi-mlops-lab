# 012: What to automate and what to leave as a documented step in restore

Stage: S4 · Date: 2026-11-22 · Author: karthik · Drafted by agent: yes

## Choice

An operator-triggered restore script (`scripts/restore.sh`) that automates starting RDS, resuming Redshift, synchronizing the laptop's public IP in `infra/live/terraform.tfvars`, verifying EC2 instances, and polling until `scripts/health.sh` exits 0.

Manual steps are strictly retained for:
1. Exporting fresh AWS Academy Learner Lab session tokens from the browser portal.
2. Starting the SageMaker notebook (left stopped by default to preserve learner credits).

## Rejected alternative

Fully automated host-boot initialization (e.g., an EC2 systemd service or cron job that automatically starts RDS and resumes Redshift upon EC2 boot).

## Why

In AWS Academy Learner Lab, credentials expire after 4 hours and must be manually retrieved by the student from the lab portal. Starting cloud infrastructure automatically on EC2 reboot without operator intent risks draining the strict lab budget ($100 learner credit) on idle RDS/Redshift clusters overnight. Furthermore, the EC2 instance profile (`LabRole`) lacks permission to start/stop certain root-level AWS resources across accounts or modify local laptop workstation configs. Having the operator run `scripts/restore.sh` once after exporting fresh credentials provides one-click restoration with complete visibility and budget safety.

## What would show this was wrong

If the lab transitions to persistent, non-learner cloud accounts with dedicated IAM roles, automated scheduling (e.g. EventBridge + Step Functions) would be preferred over a local script.
