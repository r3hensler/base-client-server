# -- Dev stage ────────────────────────────────────────────────
FROM node:22-slim AS dev
RUN apt-get update && apt-get install -y --no-install-recommends wget && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --legacy-peer-deps
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev"]

# -- Build stage ──────────────────────────────────────────────
FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --legacy-peer-deps
COPY . .
RUN npm run build

# -- Prod stage — serve static files via Caddy ───────────────
FROM caddy:2-alpine AS prod
COPY --from=build /app/dist /srv
COPY <<EOF /etc/caddy/Caddyfile
:5173 {
    root * /srv
    file_server
    try_files {path} /index.html
}
EOF
EXPOSE 5173
