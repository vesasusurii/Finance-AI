# Deployment-only single-origin reverse proxy for Azure Container Apps.
# Routes /api -> backend:8000 and everything else -> frontend-prod:80.
# TLS is terminated by the Container Apps ingress; this listens on plain :80.
FROM nginx:1.27-alpine

COPY gateway.nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
