# Starter frontend image — use after Vite scaffold exists (doc 4, doc 12)
# Enable with: docker compose --profile full up -d --build

FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
