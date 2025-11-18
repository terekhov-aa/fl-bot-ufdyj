# Build Stage
FROM node:20-alpine AS builder
WORKDIR /app

# Install all dependencies (including dev) to build the TypeScript project
COPY package*.json ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY tsconfig.json ./
COPY src ./src

RUN npm run build

# Production Stage
FROM node:20-alpine AS production
WORKDIR /app
ENV NODE_ENV=production

COPY package*.json ./
RUN if [ -f package-lock.json ]; then npm ci --omit=dev; else npm install --omit=dev; fi

COPY --from=builder /app/dist ./dist

EXPOSE 3000
CMD ["node", "dist/server.js"]
