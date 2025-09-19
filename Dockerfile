# ---------- Stage 1: Frontend build ----------
FROM node:20-alpine AS webbuild
WORKDIR /app
COPY package.json ./
RUN npm set fund false && npm set audit false
RUN npm i
COPY public ./public
COPY src ./src
COPY scripts ./scripts
RUN node scripts/build.mjs

# ---------- Stage 2: Python API ----------
FROM python:3.11-slim AS api
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/*

# Python-Dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# App-Code + gebautes Frontend
COPY . ./
COPY --from=webbuild /app/dist ./dist

ENV PORT=8080
EXPOSE 8080

# PATH-agnostisch starten
CMD ["python","-m","uvicorn","main:app","--host","0.0.0.0","--port","8080"]
