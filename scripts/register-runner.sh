#!/usr/bin/env bash
# S0: register an EC2 host as a self-hosted GitHub Actions runner (label: lab-<role>).
#
# Usage:
#   scripts/register-runner.sh [app|platform]
#
# Decision point: instance profile vs static credentials (decisions/003-runner-credentials.md).
# Uses AWS SSM: no SSH or port 22 required.

set -euo pipefail
export AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1 AWS_PAGER=""

role="${1:-app}"
root="$(cd "$(dirname "$0")/.." && pwd)"

command -v gh >/dev/null || { echo "gh CLI not found" >&2; exit 1; }
repo=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || git remote get-url origin | sed -E 's/.*[:\/]([^/]+\/[^/]+)(\.git)?$/\1/' | sed 's/\.git$//')
iid=$(terraform -chdir="$root/infra/live" output -raw "${role}_instance_id")

echo "==> Registering EC2 host $iid ($role) as GitHub Actions runner for $repo..."

echo "==> Checking if instance has completed initial bootstrap..."
tries=0
while true; do
  ((++tries <= 30)) || { echo "Timed out waiting for instance bootstrap" >&2; exit 1; }
  check=$(aws ssm send-command --instance-ids "$iid" --document-name AWS-RunShellScript \
    --parameters '{"commands": ["test -f /var/lib/lab-setup-done && echo DONE || echo WAITING"]}' \
    --query Command.CommandId --output text)
  sleep 3
  status=$(aws ssm get-command-invocation --command-id "$check" --instance-id "$iid" --query StandardOutputContent --output text 2>/dev/null || echo "")
  if [[ "$status" =~ DONE ]]; then
    echo "==> Instance bootstrap complete."
    break
  fi
  echo "    Waiting for /var/lib/lab-setup-done ($tries/30)..."
  sleep 3
done

echo "==> Fetching GitHub Actions runner registration token..."
token=$(gh api --method POST "repos/$repo/actions/runners/registration-token" -q .token)

RUNNER_VERSION=$(gh api repos/actions/runner/releases/latest -q .tag_name 2>/dev/null | tr -d 'v' || echo "2.338.2")
[[ -n "$RUNNER_VERSION" ]] || RUNNER_VERSION="2.338.2"

echo "==> Using runner version: $RUNNER_VERSION"

ssm_script=$(cat <<EOF
set -euxo pipefail
cd /opt/actions-runner

if [ -f ./svc.sh ]; then
  ./svc.sh stop || true
  ./svc.sh uninstall || true
fi

# Clean and download runner package
current_ver=\$(./bin/Runner.Listener --version 2>/dev/null || echo "")
if [ "\$current_ver" != "${RUNNER_VERSION}" ]; then
  rm -rf /opt/actions-runner/* /opt/actions-runner/.* 2>/dev/null || true
  curl -fsSL -o actions-runner-linux-arm64.tar.gz \
    "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-arm64-${RUNNER_VERSION}.tar.gz"
  tar xzf actions-runner-linux-arm64.tar.gz
  rm -f actions-runner-linux-arm64.tar.gz
  chown -R runner:runner /opt/actions-runner
fi

sudo -u runner ./config.sh --url "https://github.com/$repo" \
  --token "$token" \
  --name "lab-$role" \
  --labels "lab-$role" \
  --unattended \
  --replace

./svc.sh install runner
./svc.sh start
EOF
)

params=$(jq -cn --arg cmd "$ssm_script" '{"commands": [$cmd]}')

echo "==> Sending configuration command to host via SSM..."
cmd_id=$(aws ssm send-command --instance-ids "$iid" --document-name AWS-RunShellScript \
  --parameters "$params" --comment "Register runner lab-$role" --query Command.CommandId --output text)

while true; do
  sleep 3
  status=$(aws ssm get-command-invocation --command-id "$cmd_id" --instance-id "$iid" --query Status --output text 2>/dev/null || echo Pending)
  if [[ "$status" == "Success" ]]; then
    echo "==> Runner successfully installed and started on lab-$role!"
    break
  elif [[ "$status" =~ ^(Failed|Cancelled|TimedOut)$ ]]; then
    echo "==> SSM Command failed with status: $status" >&2
    aws ssm get-command-invocation --command-id "$cmd_id" --instance-id "$iid" --query StandardErrorContent --output text >&2
    exit 1
  fi
done

echo "==> Verifying runner status with GitHub..."
gh api "repos/$repo/actions/runners" -q ".runners[] | select(.name==\"lab-$role\") | \"Runner \\(.name) is \\(.status)\""
