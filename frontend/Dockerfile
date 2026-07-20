# ORGuard frontend — build static assets with Vite, serve with nginx.
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
# VITE_API_BASE is baked in at build time:
#  - EMPTY  -> relative URLs; nginx proxies /api,/ws,/evidence (same-origin mode)
#  - <url>  -> browser calls that backend directly (split Cloud Run mode)
#    docker build --build-arg VITE_API_BASE=https://orguard-backend-xxx.run.app ...
ARG VITE_API_BASE=""
ENV VITE_API_BASE=$VITE_API_BASE
RUN npm run build

FROM nginx:alpine
# nginx.conf is an envsubst template; the official entrypoint renders
# /etc/nginx/templates/*.template -> /etc/nginx/conf.d/ at startup, substituting
# ${PORT} and ${BACKEND_URL}.
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

# Defaults; Cloud Run overrides PORT, docker-compose overrides BACKEND_URL.
ENV PORT=8080 \
    BACKEND_URL=http://backend:8080

EXPOSE 8080
# Base image's entrypoint runs envsubst then `nginx -g "daemon off;"`.
