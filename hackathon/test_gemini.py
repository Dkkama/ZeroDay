import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from google import genai
from google.genai import types

app = FastAPI(title="Gemini 3 Flash Service")

# Initialize client using global location
client = genai.Client(
    vertexai=True,
    project="hackathon-2026-509207",
    location="global"
)

class PromptRequest(BaseModel):
    prompt: str

# Health-check route for base URL access
@app.get("/")
def health_check():
    return {"status": "ok", "service": "Gemini 3 Flash Service"}

@app.post("/generate")
def generate(payload: PromptRequest):
    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=payload.prompt,
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_level="low")
            )
        )
        return {"response": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080)