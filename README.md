# AutoJobAI - Autonomous Job Hunter & CV Matcher (Python Edition)

This is the standalone Python project for **AutoJobAI**, utilizing **LangGraph**, **RAG**, **FastAPI**, **Streamlit**, and **Gemini LLM**.

---

## 🚀 Quick Start in VS Code

### 1. Open in VS Code
Open VS Code, click **File > Open Folder...**, and select this folder (`python_project`).

### 2. Create and Activate a Virtual Environment
Open the built-in terminal (`Ctrl + ` ` or `` Cmd + ` ``):

**On Windows (PowerShell or Command Prompt):**
```bash
python -m venv venv
venv\Scripts\activate
```

**On macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. (Optional) Set Your Gemini API Key
Create a `.env` file (or copy `.env.example`):
```bash
GEMINI_API_KEY="your-gemini-api-key-here"
```
*(If you do not provide an API key, the system automatically uses its built-in heuristic algorithms and vector similarity fallbacks without crashing).*

---

## 🖥️ Running the Application

### Option A: Launch the Streamlit Interactive Dashboard
Run:
```bash
streamlit run streamlit_app.py
```
This automatically opens the browser at `http://localhost:8501`. You can:
- Upload your CV (PDF, DOCX, TXT) or use pre-loaded samples
- Toggle Zero-Trust PII Redaction
- Execute the LangGraph StateGraph pipeline
- View scraped jobs, match scores, and skill gap breakdowns
- Generate tailored ATS cover letters
- Configure automated daily email alerts

---

### Option B: Launch the High-Performance FastAPI Backend
Run:
```bash
uvicorn main:app --reload --port 8000
```
Then visit:
- **Interactive Swagger API Docs**: `http://127.0.0.1:8000/docs`
- **ReDoc Schema**: `http://127.0.0.1:8000/redoc`

---

## 🧪 Running the Automated Unit Test Suite
To verify RAG chunking, PII sanitization, vector similarity, scraper filtering, and the LangGraph workflow, run:
```bash
python -m unittest test_ai_pipeline.py
```
Expected output:
```
.....
----------------------------------------------------------------------
Ran 5 tests in 1.2s

OK
```

---

## 📂 Project Structure

- `main.py`: FastAPI server with async endpoints, auth tokens, and audit logs.
- `streamlit_app.py`: Streamlit multi-tab candidate dashboard.
- `langgraph_pipeline.py`: LangGraph multi-agent StateGraph flow (6 state nodes).
- `rag_engine.py`: Vector chunking, cosine similarity retrieval, and PII masking.
- `job_scrapers.py`: Multi-portal job aggregator (RemoteOK, Arbeitnow, LinkedIn, Indeed).
- `schemas.py`: Pydantic data models for CV, jobs, fit breakdowns, and letters.
- `test_ai_pipeline.py`: Comprehensive test suite.
- `requirements.txt`: Python package requirements.
