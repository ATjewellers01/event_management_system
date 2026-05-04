FROM node:20-alpine AS scanner-build
WORKDIR /app/BotivateScanner
COPY BotivateScanner/package*.json ./
RUN npm install
COPY BotivateScanner/ ./
RUN npm run build

FROM python:3.10-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend /app/backend
COPY frontend /app/frontend
COPY run.py /app/run.py
COPY --from=scanner-build /app/BotivateScanner/dist /app/BotivateScanner/dist

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
