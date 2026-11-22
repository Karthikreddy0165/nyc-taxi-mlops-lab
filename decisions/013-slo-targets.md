# 013: SLO targets for availability, latency, and model output ratio

Stage: S5 · Date: 2026-11-22 · Author: karthik · Drafted by agent: yes

## Choice

Set the production Service Level Objectives (SLOs) for the rider-facing ride quote service (`/predict`) as:
1. **Predict Availability:** 99.1% of requests answered with HTTP 2xx over a 1-hour rolling window.
2. **Predict Latency:** 95.0% of requests completed in under 250ms (`le="0.25"`).
3. **Model Quote Ratio:** 96.0% of predictions answered by the live ML model (`source="model"`), permitting at most 4.0% fallback quotes (`source="fallback"`).

Multi-window burn-rate alerts are configured on 1-hour and 5-minute windows to page on rapid budget consumption.

## Rejected alternative

- Stricter availability (99.9% / three nines), 99.0% latency under 100ms, and 99.0% model quote ratio.
- More lenient targets (e.g. 95% availability, 90% latency under 500ms).

## Why

1. **Availability at 99.1%:** Setting an internal target higher than a typical 99.0% contractual agreement ensures an engineering safety margin to detect and resolve degradation before an external SLA breach occurs. While 99.9% allows only 3.6 seconds of downtime per hour (which would falsely trigger during blue-green deployment switches or container reloads), 99.1% provides a 0.9% error budget (~32.4 seconds per hour), accommodating zero-downtime traffic transitions while aggressively catching real outages.
2. **Latency at 95% < 250ms:** LightGBM model inference takes <15ms, but Traefik reverse-proxy routing, ASGI deserialization, and occasional Python garbage collection introduce tail latencies on shared Graviton `t4g.large` instances. 95% < 250ms guarantees snappy rider responsiveness while avoiding alert fatigue from non-impacting $p99$ blips.
3. **Model Ratio at 96%:** When `serving-champion` is reloading or temporarily unreachable, the app falls back to the static 12.25-minute median quote. Requiring 96% of quotes to come from the ML model ensures high pricing accuracy without paging during normal model hot-reloads.

## What would show this was wrong

- Frequent false-positive alerts during automated blue-green deployments would show 99.1% is too tight for the deployment architecture.
- Rider complaints or uncaptured degraded states during fallback bursts would show 96% model ratio is too lenient.
