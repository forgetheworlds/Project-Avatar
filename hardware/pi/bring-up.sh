#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF' >&2
usage: bring-up.sh [--quick]

Runs hardware bring-up diagnostics and writes status to boot partition.

Options:
  --quick    Skip extended diagnostics, only check critical items
  -h, --help Show this help message

Status Levels:
  green  - All systems nominal, ready for flight
  yellow - Non-critical issues detected, may affect some operations
  red    - Critical issues detected, do not fly

Output:
  Writes status to /boot/firmware/avatar-status.txt (Bookworm)
  or /boot/avatar-status.txt (older releases)
EOF
}

QUICK_MODE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --quick)
      QUICK_MODE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage
      exit 2
      ;;
  esac
done

# Detect boot partition mount point
detect_boot_path() {
  if mountpoint -q /boot/firmware 2>/dev/null; then
    echo "/boot/firmware"
  elif mountpoint -q /boot 2>/dev/null; then
    echo "/boot"
  else
    echo "/tmp"  # Fallback for testing
  fi
}

BOOT_PATH=$(detect_boot_path)
STATUS_FILE="${BOOT_PATH}/avatar-status.txt"

# Diagnostic functions
check_pixhawk() {
  if [[ -e /dev/pixhawk ]]; then
    echo "OK: Pixhawk detected at /dev/pixhawk"
    return 0
  else
    echo "WARN: Pixhawk not found at /dev/pixhawk"
    return 1
  fi
}

check_mavsdk() {
  if [[ -x /opt/mavsdk/mavsdk_server ]]; then
    echo "OK: MAVSDK server installed"
    return 0
  else
    echo "WARN: MAVSDK server not installed"
    return 1
  fi
}

check_avatar() {
  if [[ -d /opt/avatar/.venv ]]; then
    echo "OK: Avatar software installed"
    return 0
  else
    echo "WARN: Avatar software not installed"
    return 1
  fi
}

check_network() {
  if ping -c 1 -W 2 8.8.8.8 &>/dev/null; then
    echo "OK: Network connectivity confirmed"
    return 0
  else
    echo "WARN: No network connectivity"
    return 1
  fi
}

check_time_sync() {
  if systemctl is-active systemd-timesyncd &>/dev/null; then
    echo "OK: Time synchronization active"
    return 0
  else
    echo "WARN: Time synchronization not active"
    return 1
  fi
}

check_disk_space() {
  local avail
  avail=$(df --output=avail / | tail -1 | tr -d ' ')
  if [[ "$avail" -gt 1048576 ]]; then  # > 1GB free
    echo "OK: Sufficient disk space"
    return 0
  else
    echo "WARN: Low disk space"
    return 1
  fi
}

check_temperature() {
  if [[ -f /sys/class/thermal/thermal_zone0/temp ]]; then
    local temp
    temp=$(cat /sys/class/thermal/thermal_zone0/temp)
    temp=$((temp / 1000))
    if [[ "$temp" -lt 70 ]]; then
      echo "OK: CPU temperature nominal (${temp}C)"
      return 0
    elif [[ "$temp" -lt 80 ]]; then
      echo "WARN: CPU temperature elevated (${temp}C)"
      return 1
    else
      echo "CRIT: CPU temperature critical (${temp}C)"
      return 2
    fi
  else
    echo "INFO: Cannot read CPU temperature"
    return 0
  fi
}

# Run diagnostics
echo "=== Avatar Hardware Bring-Up ==="
echo "Time: $(date -Iseconds)"
echo "Host: $(hostname)"
echo ""

CRITICAL_ISSUES=0
WARNINGS=0

# Critical checks
check_pixhawk || ((CRITICAL_ISSUES++))
check_avatar || ((CRITICAL_ISSUES++))
check_mavsdk || ((WARNINGS++))

# Extended checks (skip in quick mode)
if [[ "$QUICK_MODE" -eq 0 ]]; then
  check_network || ((WARNINGS++))
  check_time_sync || ((WARNINGS++))
  check_disk_space || ((WARNINGS++))
  check_temperature || temp_status=$?
  if [[ "${temp_status:-0}" -eq 2 ]]; then
    ((CRITICAL_ISSUES++))
  elif [[ "${temp_status:-0}" -eq 1 ]]; then
    ((WARNINGS++))
  fi
fi

echo ""
echo "=== Summary ==="
echo "Critical Issues: $CRITICAL_ISSUES"
echo "Warnings: $WARNINGS"

# Determine status
if [[ "$CRITICAL_ISSUES" -gt 0 ]]; then
  STATUS="red"
  REASON="Critical issues detected - do not fly"
elif [[ "$WARNINGS" -gt 0 ]]; then
  STATUS="yellow"
  REASON="Non-critical issues detected - review before flight"
else
  STATUS="green"
  REASON="All systems nominal - ready for flight"
fi

echo "Status: $STATUS"
echo "Reason: $REASON"

# Write status file
{
  echo "status=${STATUS}"
  echo "timestamp=$(date -Iseconds)"
  echo "hostname=$(hostname)"
  echo "critical_issues=${CRITICAL_ISSUES}"
  echo "warnings=${WARNINGS}"
  echo "reason=${REASON}"
} | sudo tee "$STATUS_FILE" > /dev/null

echo ""
echo "Status written to: $STATUS_FILE"

# Exit with appropriate code
if [[ "$STATUS" == "red" ]]; then
  exit 2
elif [[ "$STATUS" == "yellow" ]]; then
  exit 1
else
  exit 0
fi
