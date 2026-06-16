# Multi-stage: build the React app, then serve it from nginx with an API proxy.
# Build context must be the repo's `app/` directory.

FROM node:18-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
# REACT_APP_API_URL is intentionally unset → same-origin relative API calls.
RUN npm run build

FROM nginx:1.27-alpine
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build /usr/share/nginx/html
EXPOSE 80
