FROM node:20-alpine

# Set work directory
WORKDIR /app

# Install dependencies needed for node-gyp if required by some node modules 
# (alpine doesn't have them by default, though usually Vite is fine)
RUN apk add --no-cache bash

# Copy package.json and package-lock.json first to leverage caching
COPY package*.json ./
RUN npm install

# As with the backend, we omit copying the source code since we rely on 
# docker-compose volume mounts for hot-reloading.

EXPOSE 5173

CMD ["npm", "run", "dev"]
