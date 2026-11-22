# 014: Prometheus metrics series budget and relabelling strategy

Stage: S5 · Date: 2026-11-22 · Author: karthik · Drafted by agent: yes

## Choice

Implement aggressive metric and label filtering in `observability/alloy/budget.alloy`:
1. **Container Relabelling:** Retain only container memory working set, CPU usage, network I/O, and start time; **drop ephemeral labels (`id` container cgroup hash and `container_label_*`)**. Drop metrics for unnamed cgroups (`name=""`).
2. **Host Relabelling:** Keep core system metrics (`node_cpu_seconds_total`, memory totals/available, root filesystem space, and network interface `eth0`); drop virtual network interfaces (`veth*`, `br-*`, `docker*`) and non-physical filesystems (`tmpfs`, `overlay`).
3. **Service Metrics:** Retain all `lab_*` and `traefik_service_*` metrics specified in `contracts/metrics.yaml`.

Target: Maintain active series at ~600–800 series per host (~1,800–2,400 across all three hosts `app`, `platform`, `llm`), preserving over 70% of the 10,000 Grafana Cloud free-tier series limit.

## Rejected alternative

Permissive relabelling (retaining all cAdvisor container metrics and dropping only virtual network interfaces), which emits 2,500–4,000 series per host.

## Why

1. **The Container ID Multiplier:** Every time a container restarts or deploys via blue-green CD, Docker assigns a new 64-character container hash (`id`). Because Prometheus treats every unique combination of label values as a distinct time series, keeping `id` multiplies container series by $N$ deployments, rapidly exhausting the 10,000 limit. Dropping `id` while preserving `name` ensures series continuity across deployments.
2. **Free-Tier Protection:** Grafana Cloud hard-caps free tier at 10,000 active series, dropping samples when exceeded. Dropping unneeded OS internals (thermal zones, softnet, per-core interrupts) and container block-I/O statistics reduces series volume by >75% with zero impact on dashboarding, SLO monitoring, or incident response.

## What would show this was wrong

Needing to diagnose deep OS-level kernel network buffer drops or container disk throttling from Grafana Cloud without having SSH/SSM terminal access to the EC2 instances.
