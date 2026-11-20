# LearnLens web — Next.js App Router (infra health shell)

FROM node:20.19-alpine AS deps
WORKDIR /app
COPY package.json ./
RUN npm install --ignore-scripts

FROM node:20.19-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
# Build-time default; runtime override via API_INTERNAL_URL for the health proxy.
ENV API_INTERNAL_URL=http://api:8000
RUN npm run build

FROM node:20.19-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    API_INTERNAL_URL=http://api:8000
RUN addgroup -S app && adduser -S app -G app \
    && apk add --no-cache curl
COPY --from=builder /app/package.json ./
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/next.config.ts ./
COPY --from=builder /app/public ./public
USER app
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
  CMD curl -fsS http://127.0.0.1:3000/ || exit 1
CMD ["npm", "run", "start"]
