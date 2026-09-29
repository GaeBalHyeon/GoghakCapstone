#!/usr/bin/env bash
set -euo pipefail

AGENT_DIR="$(cd "$(dirname "$0")" && pwd)"
AUTOSTART="$AGENT_DIR/autostart_agent.sh"
CRON_LINE="@reboot sleep 20 && $AUTOSTART"

chmod +x "$AUTOSTART"
current_cron="$(crontab -l 2>/dev/null || true)"
if ! printf '%s\n' "$current_cron" | grep -Fqx "$CRON_LINE"; then
  { printf '%s\n' "$current_cron"; printf '%s\n' "$CRON_LINE"; } | sed '/^[[:space:]]*$/d' | crontab -
fi

echo "Jetson reboot autostart installed."
echo "Registered entry: $CRON_LINE"
