from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
import sqlite3
from pathlib import Path
from io import BytesIO
import fitz
from docx import Document
import requests
import os

app = FastAPI()


@app.get("/")
def home():
    return FileResponse("index.html")

# SQLite database initialization
DB_PATH = Path(__file__).parent / "ai_projects.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

# Initialize database on startup
init_db()

@app.get("/")
def read_root():
    return {
        "message": "Welcome to AI Projects API",
        "version": "1.0.0",
        "endpoints": [
            {"path": "/", "method": "GET", "description": "Simple HTML homepage"},
            {"path": "/health", "method": "GET", "description": "Health check endpoint"},
            {"path": "/users", "method": "GET", "description": "Get all users from database"}
        ]
    }


@app.post("/upload-resume")
async def upload_resume(file: UploadFile = File(...)):
    filename = file.filename or ""
    extension = Path(filename).suffix.lower()

    if extension not in [".pdf", ".docx"]:
        raise HTTPException(
            status_code=400,
            detail="Only PDF and DOCX files are supported."
        )

    content = await file.read()

    if not content:
        raise HTTPException(status_code=400, detail="File is empty.")

    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail="File must be smaller than 5 MB."
        )

    try:
        if extension == ".pdf":
            pdf = fitz.open(stream=content, filetype="pdf")
            text = "\n".join(page.get_text() for page in pdf)
            pdf.close()

        else:
            document = Document(BytesIO(content))
            text = "\n".join(
                paragraph.text for paragraph in document.paragraphs
            )

        if not text.strip():
            raise HTTPException(
                status_code=400,
                detail="No readable text found in resume."
            )

        return {
            "success": True,
            "filename": filename,
            "characters_extracted": len(text),
            "extracted_text": text
        }

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Could not read this resume."
        )

@app.get("/health")
def health_check():
    return{"status":"ok"}


@app.post("/analyze-resume")
async def analyze_resume(resume_text: str):
    prompt = f"""
You are an expert AI Resume Analyzer.

Analyze this resume:
{resume_text}

Provide:
1. Resume score out of 100
2. Strengths
3. Weaknesses
4. Missing skills
5. Improvement suggestions
"""

   
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    response = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent",
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json"
        },
        json={
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 1024
            }
        },
        timeout=120
    )

    response.raise_for_status()
    result = response.json()

    analysis = result["candidates"][0]["content"]["parts"][0]["text"]

    return {"analysis": analysis}


