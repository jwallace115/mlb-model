#!/bin/bash
# Add (or replace) a login for iamnotuncertain.net. Run on the VM as root:
#   bash /root/mlb-model/site/ops/add_site_user.sh <name>
# Prints the new password ONCE to this terminal. It is not written anywhere else.
set -eu
NAME=${1:?usage: add_site_user.sh <name>}
[[ "$NAME" =~ ^[a-z][a-z0-9_-]{1,30}$ ]] || { echo "name: lowercase letters/digits/_-"; exit 2; }
USERS=/etc/caddy/iamnotuncertain.users
PW=$(openssl rand -base64 18 | tr -d '/+=' | cut -c1-20)
HASH=$(caddy hash-password --plaintext "$PW")
touch "$USERS"; chmod 640 "$USERS"; chgrp caddy "$USERS" 2>/dev/null || true
grep -v "^$NAME " "$USERS" > "$USERS.tmp" || true
echo "$NAME $HASH" >> "$USERS.tmp"
mv "$USERS.tmp" "$USERS"; chmod 640 "$USERS"; chgrp caddy "$USERS" 2>/dev/null || true
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null && systemctl reload caddy
echo "login for https://iamnotuncertain.net  user: $NAME  password: $PW"
