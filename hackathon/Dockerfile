FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn google-genai

# Copy test_gemini.py into /app/test_gemini.py inside the container
COPY test_gemini.py .

EXPOSE 8080

# Point Uvicorn to test_gemini:app instead of main:app
CMD ["uvicorn", "test_gemini:app", "--host", "0.0.0.0", "--port", "8080"]