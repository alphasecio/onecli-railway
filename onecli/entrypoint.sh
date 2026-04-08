#!/bin/sh
set -e

export CADDY_PORT="${PORT}"
export PORT=10254

/app/entrypoint.sh &

sleep 5

exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
