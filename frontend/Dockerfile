# Spec §11.1. Obrazy bazowe: oficjalne, wersja + digest (bez `latest`).
FROM node:24-alpine3.22@sha256:191c9f0080fcbbc6547a85dc0ff7988072214a355aabdc1d2ec55a7dae5eea8a AS build
WORKDIR /app
COPY package*.json ./
# Cache npm poza warstwą: zmiana package-lock.json nie pobiera ponownie wszystkich paczek.
RUN --mount=type=cache,target=/root/.npm npm ci
COPY . .
RUN npm run build

FROM nginx:1.28-alpine3.23@sha256:a8b39bd9cf0f83869a2162827a0caf6137ddf759d50a171451b335cecc87d236
COPY nginx.conf /etc/nginx/nginx.conf
COPY --from=build /app/dist/coi-cf-frontend/browser /usr/share/nginx/html
USER nginx
EXPOSE 8080
# Bez skryptów /docker-entrypoint.d: piszą do /etc/nginx/conf.d, a system plików jest tylko do odczytu.
ENTRYPOINT ["nginx", "-g", "daemon off;"]
CMD []
