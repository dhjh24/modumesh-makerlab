# syntax=docker/dockerfile:1
FROM node:22-alpine AS builder
RUN addgroup -S modumesh && adduser -S -G modumesh modumesh
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
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ARG API_INTERNAL_URL=http://api:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV API_INTERNAL_URL=$API_INTERNAL_URL
RUN npm run build --workspace=@modumesh/web

FROM node:22-alpine
RUN addgroup -S modumesh && adduser -S -G modumesh modumesh
WORKDIR /app
ENV NODE_ENV=production
ENV HOSTNAME=0.0.0.0
# Copy the full standalone output (it includes server.js + node_modules at correct relative paths)
COPY --from=builder /app/apps/web/.next/standalone/ ./
# Copy static assets to where server.js expects them
COPY --from=builder /app/apps/web/.next/static ./apps/web/.next/static
# Copy public assets
COPY --from=builder /app/apps/web/public ./apps/web/public
RUN chown -R modumesh:modumesh /app
USER modumesh
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
