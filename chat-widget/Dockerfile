FROM nginx:alpine
# Copy the built output from Vite (you would run `npm run build` beforehand in CI or host)
# Since we are building via docker-compose, we can multi-stage build it.

# But wait, let's use a multi-stage Dockerfile here:
FROM node:18-alpine as builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
# Also copy a simple html test file if needed, or rely on nginx serving the dir contents
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
