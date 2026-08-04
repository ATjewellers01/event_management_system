FROM node:20-alpine AS scanner-build
# No build args needed: the scanner talks to this app's own API, not Apps Script.
WORKDIR /app/BotivateScanner
COPY BotivateScanner/package*.json ./
RUN npm install
COPY BotivateScanner/ ./
RUN npm run build

FROM python:3.10-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# uv resolves and installs considerably faster than pip, which matters on a
# t-class instance where the image rebuild is the slowest part of a deploy.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install into the system environment rather than a venv: the container is
# already an isolated environment, so a venv only adds an activation step.
ENV UV_SYSTEM_PYTHON=1
ENV UV_COMPILE_BYTECODE=0
ENV UV_LINK_MODE=copy

COPY requirements.txt /app/requirements.txt
RUN uv pip install --system --no-cache -r /app/requirements.txt

COPY backend /app/backend
COPY frontend /app/frontend
COPY run.py /app/run.py
COPY --from=scanner-build /app/BotivateScanner/dist /app/BotivateScanner/dist

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
