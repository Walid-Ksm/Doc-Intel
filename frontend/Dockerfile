# ==============================================================================
# Document Intelligence Frontend (Angular SPA)
# Multi-Stage Production Container Image
# ==============================================================================

# Stage 1: Build Angular application
FROM node:22-alpine AS builder

WORKDIR /app

# Cache node dependencies
COPY package*.json ./
RUN npm ci

# Copy source code and build production bundle
COPY . .
RUN npm run build

# Stage 2: Serve with lightweight, secure Nginx
FROM nginx:1.27-alpine AS runtime

# Remove default Nginx welcome site
RUN rm -rf /usr/share/nginx/html/*

# Copy built browser artifacts from the builder stage
COPY --from=builder /app/dist/frontend/browser /usr/share/nginx/html

# Copy custom Nginx configuration with SPA routing and security headers
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://127.0.0.1/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
