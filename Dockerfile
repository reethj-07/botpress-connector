FROM node:20-bookworm AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend ./
RUN npm run build

FROM python:3.11-slim AS backend
WORKDIR /app
COPY backend ./backend
COPY --from=frontend /app/backend/static ./backend/static
WORKDIR /app/backend
RUN pip install --no-cache-dir -e .
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

