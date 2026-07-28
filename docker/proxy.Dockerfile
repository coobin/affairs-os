ARG NODE_BASE_IMAGE=node:22.16.0-alpine
ARG NGINX_BASE_IMAGE=nginx:1.27.4-alpine

FROM ${NODE_BASE_IMAGE} AS frontend-builder
WORKDIR /app
ARG NPM_REGISTRY=https://registry.npmjs.org
COPY frontend/package*.json ./
RUN npm config set registry "${NPM_REGISTRY}" && npm ci
COPY frontend/ .
RUN npm run build

FROM ${NGINX_BASE_IMAGE}
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend-builder /app/dist /usr/share/nginx/html
HEALTHCHECK --interval=15s --timeout=5s --retries=3 CMD nginx -t >/dev/null 2>&1 && kill -0 1
