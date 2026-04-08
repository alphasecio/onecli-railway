FROM ghcr.io/onecli/onecli
 
USER root
RUN apk add --no-cache caddy

COPY Caddyfile /etc/caddy/Caddyfile
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh
