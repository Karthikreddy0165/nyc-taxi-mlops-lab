# 003: Runner credentials: EC2 instance profile vs static secrets

Stage: S0 · Date: 2026-11-21 · Author: karthik · Drafted by agent: yes

## Choice

Use the host's IAM instance profile (`LabInstanceProfile` with `LabRole`).

## Rejected alternative

Storing temporary AWS session credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`) as GitHub Actions secrets.

## Why

AWS Academy Learner Lab credentials expire every 4 hours, which would break automated deployments unless manually rotated in GitHub Secrets. The EC2 instance profile provides automatic, rotated, zero-maintenance credential retrieval via IMDSv2 directly on the host.

## What would show this was wrong

If runner jobs required AWS permissions outside the pre-attached `LabRole` policy boundaries.
