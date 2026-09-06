# FloraSentry V2 frontend - development image (TRD 37.1).
# Runs the Vite dev server with hot reload. A production image would add a build
# stage and serve `dist/` from nginx; that lands with the deployment work in Phase 10.

FROM node:20-alpine

WORKDIR /srv/app

# Dependency layer first so source edits do not reinstall node_modules.
COPY package.json package-lock.json* ./
RUN npm ci || npm install

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
