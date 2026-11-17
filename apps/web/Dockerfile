# LearnLens web — Node 20 stub image (Next.js app lands in a later phase)

FROM node:20.19-alpine AS base
WORKDIR /app
ENV NODE_ENV=production
COPY package.json ./
RUN npm install --ignore-scripts --omit=dev 2>/dev/null || true
COPY . .
USER node
EXPOSE 3000
CMD ["node", "-e", "console.log('@learnlens/web scaffold — Next.js deferred')"]
