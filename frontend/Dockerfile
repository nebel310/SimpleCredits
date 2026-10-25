# Сборка
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# Адрес API для браузера. /api проксирует nginx (см. nginx.conf)
ARG VITE_API_URL=/api
ARG VITE_ADMIN_EMAIL=admin@admin.com
ARG VITE_ADMIN_PASSWORD=admin
ENV VITE_API_URL=$VITE_API_URL VITE_ADMIN_EMAIL=$VITE_ADMIN_EMAIL VITE_ADMIN_PASSWORD=$VITE_ADMIN_PASSWORD
RUN npm run build

# Раздача статики и прокси на бэкенд
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK CMD wget -qO- http://localhost/ >/dev/null || exit 1
