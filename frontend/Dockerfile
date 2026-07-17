FROM node:20-alpine

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

EXPOSE 3000

ENV NODE_ENV=development

CMD ["node_modules/.bin/next", "dev", "--hostname", "0.0.0.0"]
