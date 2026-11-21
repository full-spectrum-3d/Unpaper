# Spec §11.1
FROM node:24-alpine3.22 AS build
WORKDIR /app
COPY package*.json ./
# Cache npm poza warstwą: zmiana package-lock.json nie pobiera ponownie wszystkich paczek.
RUN --mount=type=cache,target=/root/.npm npm ci
COPY . .
RUN npm run build

FROM nginx:1.28-alpine3.23
COPY nginx.conf /etc/nginx/nginx.conf
COPY --from=build /app/dist/coi-cf-frontend/browser /usr/share/nginx/html
USER nginx
EXPOSE 8080
