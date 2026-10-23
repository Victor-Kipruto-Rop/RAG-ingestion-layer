FROM node:22-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm install --no-audit --no-fund
COPY . .
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM nginx:1.27-alpine AS runtime
RUN addgroup -S app && adduser -S app -G app
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html
RUN chown -R app:app /usr/share/nginx/html /var/cache/nginx /var/run /var/log/nginx && touch /var/run/nginx.pid && chown app:app /var/run/nginx.pid
USER app
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
