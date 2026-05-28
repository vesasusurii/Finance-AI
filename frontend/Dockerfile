# Build context: repo root (see docker-compose.yml)
# Branding lives at /branding so Vite alias @brand → ../DOCS/branding resolves in the container.

FROM node:20-alpine

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY frontend/ ./
COPY DOCS/branding/ /branding/

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
