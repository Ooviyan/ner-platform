# NER Driver PWA — build from the REPO ROOT, not from driver-app/:
#   docker build -f driver-app/Dockerfile -t ner-driver-app .
#   docker run --rm -p 3001:3001 ner-driver-app
#
# The build context is the repo root because the shared fixtures in
# ../mock-data are baked into the image so the PWA runs with no backend.

# ---------- build ----------
FROM node:22-alpine AS build
WORKDIR /app

# Install deps first so this layer caches across source edits.
COPY driver-app/package.json driver-app/package-lock.json ./
RUN npm ci

COPY driver-app/ ./
# vite.config.js copies ../mock-data into dist/, so it must sit one level up.
COPY mock-data/ /mock-data/

# Point at a real backend at build time with:
#   --build-arg VITE_API_URL=http://backend:8000 --build-arg VITE_WS_URL=ws://backend:8000/ws/mesh
ARG VITE_API_URL=/mock-data
ARG VITE_WS_URL=
ARG VITE_VEHICLE_ID=AS-01-EG-4417
ENV VITE_API_URL=$VITE_API_URL \
    VITE_WS_URL=$VITE_WS_URL \
    VITE_VEHICLE_ID=$VITE_VEHICLE_ID

RUN npm run build

# ---------- serve ----------
FROM nginx:1.27-alpine AS runtime
COPY driver-app/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 3001
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
  CMD wget -qO- http://localhost:3001/ >/dev/null || exit 1

CMD ["nginx", "-g", "daemon off;"]
