# Dockerfile for FIN_SPY Web - Next.js - for Railway live webpage proof for Paystack
# Context is repo root (Railway default), so copy from apps/web/
FROM node:20-alpine AS builder
WORKDIR /app
COPY apps/web/package.json ./
COPY apps/web/pnpm-lock.yaml* ./
COPY apps/web/yarn.lock* ./
RUN corepack enable && pnpm install --frozen-lockfile 2>/dev/null || npm install --legacy-peer-deps
COPY apps/web/ ./
RUN pnpm build 2>/dev/null || npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["npm", "start"]
