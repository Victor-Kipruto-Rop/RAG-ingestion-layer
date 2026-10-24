FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# The API origin is baked in at build time. Pass an absolute URL (e.g. https://api.example.com),
# or an empty value to call the API on the same origin through your own reverse proxy.
ARG VITE_API_BASE_URL
RUN [ -n "${VITE_API_BASE_URL+x}" ] || { echo "Build argument VITE_API_BASE_URL is required (use --build-arg VITE_API_BASE_URL=https://api.example.com)" >&2; exit 1; }
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
