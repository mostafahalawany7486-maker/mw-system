# ---- Base: install deps ----
FROM node:20-alpine AS base
WORKDIR /app
COPY package.json ./
RUN npm install

# ---- Dev target: used by docker-compose (runs `npm run dev`) ----
FROM base AS dev
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# ---- Build stage: compiles static assets for production ----
FROM base AS build
COPY . .
RUN npm run build

# ---- Production target: static files served by nginx ----
FROM nginx:1.27-alpine AS production
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
