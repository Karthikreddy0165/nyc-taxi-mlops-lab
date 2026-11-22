# 011: Automated smoke test trigger for blue-green switch

Stage: S3 · Date: 2026-11-22 · Author: karthik · Drafted by agent: yes

## Choice

The blue-green traffic switch is automated in CD: after deploying the new app container to the idle colour (e.g. green while blue is live), the CD pipeline runs automated smoke tests against the idle colour (`/version` matching the expected git SHA and `/predict` answering a valid duration), and upon passing, immediately executes `deploy/web.sh switch <idle_colour>`.

## Rejected alternative

A manual approval gate or manual command trigger before executing the blue-green switch, requiring a human operator to inspect the idle colour and approve the traffic shift.

## Why

The app host runs two independent colours behind Traefik. Deploying to the idle colour has zero impact on live rider traffic. Automated smoke tests (`deploy/web.sh smoke <colour> <sha>`) deterministically verify application boot, routing, git SHA alignment, and quote generation within seconds. Requiring manual approval for standard app deployments adds unnecessary developer toil and slows down deployment frequency, without providing safety beyond what deterministic automated smoke tests already verify. If smoke tests fail, the CD pipeline aborts, leaving the live colour completely untouched.

## What would show this was wrong

If a faulty build passes basic smoke tests on `/version` and a single synthetic `/predict` payload, but fails under live production traffic patterns (e.g. edge-case payloads, concurrency locks), indicating that smoke tests alone were insufficient to authorize a 100% traffic flip.
