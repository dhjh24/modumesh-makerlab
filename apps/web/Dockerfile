# syntax=docker/dockerfile:1
FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
COPY apps/web/package.json apps/web/tsconfig.json apps/web/next.config.js ./apps/web/
COPY packages/plugin-sdk/package.json packages/plugin-sdk/tsconfig.json ./packages/plugin-sdk/
COPY packages/shared-types/package.json packages/shared-types/tsconfig.json ./packages/shared-types/
COPY packages/viewer/package.json packages/viewer/tsconfig.json ./packages/viewer/
COPY packages/ui/package.json packages/ui/tsconfig.json ./packages/ui/
RUN npm ci
COPY apps/web/ ./apps/web/
COPY packages/ ./packages/
RUN npm run build --workspace=@modumesh/web && \
    mkdir -p /app/standalone/.next && \
    cp -r apps/web/.next/standalone/. /app/standalone/ && \
    cp -r apps/web/.next/static /app/standalone/.next/static && \
    if [ -d apps/web/public ]; then cp -r apps/web/public /app/standalone/public; fi

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/standalone ./
EXPOSE 3000
CMD ["node", "server.js"]
