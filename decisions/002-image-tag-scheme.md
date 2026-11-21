# 002: Image tag scheme for GHCR container images

Stage: S0 · Date: 2026-11-21 · Author: karthik · Drafted by agent: yes

## Choice

Tag images with the short 7-character Git commit SHA: `sha-${GITHUB_SHA::7}`.

## Rejected alternative

Mutable tags like `:latest` or manual semantic versioning tags (`:v1.0.0`).

## Why

Short Git SHAs provide serialized, human-trackable, 1-to-1 immutable mapping between a deployed container and the exact git commit that built it. Rolling back simply means redeploying the short SHA of the previously healthy commit.

## What would show this was wrong

If multi-team release workflows require human-readable semantic version milestones (e.g. `v1.2.0`) to coordinate breaking API deprecations.
