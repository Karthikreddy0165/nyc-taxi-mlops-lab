# 001: Ingress scope for the app host

Stage: S0 · Date: 2026-11-21 · Author: karthik · Drafted by agent: yes

## Choice

Open port 80 to the public internet (`0.0.0.0/0`) via Traefik.

## Rejected alternative

Restricting port 80 to a single workstation IP (`<my-ip>/32`).

## Why

Traefik is the rider-facing entry point for trip duration quotes. Riders request trip quotes from variable networks (mobile cellular networks, home Wi-Fi, public hotspots). Security is maintained by keeping all internal services (FastAPI on 8000, model serving on 8001, MLflow on 5000, and RDS on 5432) isolated inside private security groups, with only Traefik exposed.

## What would show this was wrong

Unmitigated denial-of-service traffic or unauthorized endpoint abuse that requires placing an AWS CloudFront distribution or AWS WAF in front of Traefik.
