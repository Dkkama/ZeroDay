FROM node:20-alpine AS ui
WORKDIR /ui
COPY app/frontend/package.json app/frontend/package-lock.json* ./
RUN npm install
COPY app/frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir \
    fastapi uvicorn python-dotenv python-multipart pydantic google-genai google-cloud-firestore \
    pypdf python-docx openpyxl pypdfium2 pillow
COPY app/backend /app/app/backend
COPY sdoc_eval /app/sdoc_eval
COPY sdoc-hackathon-docker /app/sdoc-hackathon-docker
COPY hackathon /app/hackathon
COPY --from=ui /ui/dist /app/app/frontend/dist
ENV PYTHONPATH=/app/app/backend
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--app-dir", "app/backend"]
