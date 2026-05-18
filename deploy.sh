#!/usr/bin/env bash
# Idempotent deploy script for Ubuntu (ARM or x86).
# Installs Docker if missing, builds the bot image, and starts it under systemd
# (via docker compose with restart=unless-stopped) so it survives reboots.
#
# Usage:
#   sudo bash deploy.sh
#
# Requires a populated .env file alongside this script with:
#   DISCORD_BOT_TOKEN, DISCORD_SIGNAL_CHANNEL_ID,
#   TWELVEDATA_API_KEY (optional), TIMEZONE, etc.

set -euo pipefail

cd "$(dirname "$0")"

log() { echo -e "\033[1;32m[deploy]\033[0m $*"; }
warn() { echo -e "\033[1;33m[deploy]\033[0m $*" >&2; }
err() { echo -e "\033[1;31m[deploy]\033[0m $*" >&2; }

if [[ "${EUID}" -ne 0 ]]; then
    err "Run with sudo: sudo bash $(basename "$0")"
    exit 1
fi

if [[ ! -f .env ]]; then
    err "No .env file found in $(pwd). Create one from .env.example first."
    exit 1
fi

# --- 1. Install Docker if missing ---
if ! command -v docker >/dev/null 2>&1; then
    log "Installing Docker Engine + Compose plugin"
    apt-get update -qq
    apt-get install -y -qq ca-certificates curl gnupg lsb-release ufw
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
        | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    arch="$(dpkg --print-architecture)"
    codename="$(. /etc/os-release && echo "${VERSION_CODENAME}")"
    echo \
        "deb [arch=${arch} signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${codename} stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable --now docker
fi

log "Docker version: $(docker --version)"

# --- 2. Open the healthcheck port (best effort) ---
if command -v ufw >/dev/null 2>&1; then
    if ufw status | grep -qi inactive; then
        log "Leaving ufw inactive (Oracle relies on Security List rules)"
    else
        ufw allow 8080/tcp || true
    fi
fi

# Oracle's default Ubuntu image enables iptables and blocks inbound by default.
# Add explicit ACCEPT rules for the healthcheck port if iptables is enforced.
if command -v iptables >/dev/null 2>&1; then
    if iptables -L INPUT -n 2>/dev/null | grep -q "policy DROP\|REJECT"; then
        log "Adding iptables ACCEPT rule for tcp/8080"
        iptables -I INPUT 1 -p tcp --dport 8080 -m state --state NEW,ESTABLISHED -j ACCEPT || true
        if command -v netfilter-persistent >/dev/null 2>&1; then
            netfilter-persistent save || true
        fi
    fi
fi

# --- 3. Build and start ---
log "Building image (this can take a few minutes on first run)"
docker compose build --pull

log "Starting bot (detached)"
docker compose up -d

sleep 3
log "Container status:"
docker compose ps

log "Recent logs:"
docker compose logs --tail 30

log ""
log "Deployment complete."
log "Tail logs:    docker compose logs -f"
log "Restart:      docker compose restart"
log "Stop:         docker compose down"
log "Health:       curl http://localhost:8080/health"
