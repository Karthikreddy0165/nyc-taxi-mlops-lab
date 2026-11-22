# 010: Model pickup via atomic reload endpoint

Stage: S3 · Date: 2026-11-22 · Author: karthik · Drafted by agent: yes

## Choice

Model serving picks up a new champion via an internal `POST /reload` HTTP endpoint on the running `serving-champion` container. The container loads the new model artifacts from MLflow into memory, warms it up, and atomically swaps the active model reference. Riders continue receiving predictions from the existing champion with zero downtime while the new model loads.

## Rejected alternative

Restarting the `serving-champion` container on alias update (e.g. `docker compose restart serving-champion`) to load the new champion at container start-up.

## Why

Downloading and unpickling MLflow model artifacts and initializing LightGBM trees takes 5 to 15 seconds. If the container is restarted, it cannot answer `/predict` during that initialization window, forcing the app to drop predictions or fall back to quoting the static 12.25-minute median to active riders. The in-process `POST /reload` endpoint guarantees seamless zero-downtime model promotion: the existing model continues serving incoming requests until the new model is fully validated in memory, eliminating customer-facing disruption.

## What would show this was wrong

If repeated in-memory model reloads cause cumulative memory fragmentation or memory leaks in the Python serving process, exhausting host RAM over multiple retrains and requiring container restarts anyway.
