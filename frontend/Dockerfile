# Сборка
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# VITE_API_MODE=http — работать с бэкендом; по умолчанию мок в браузере
ARG VITE_API_MODE=mock
ARG VITE_API_URL=/api
ENV VITE_API_MODE=$VITE_API_MODE VITE_API_URL=$VITE_API_URL
RUN npm run build

# Раздача статики
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK CMD wget -qO- http://localhost/ >/dev/null || exit 1
