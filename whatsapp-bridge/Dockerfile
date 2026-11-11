FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY server.js ./server.js

EXPOSE 5005

CMD ["npm", "start"]
