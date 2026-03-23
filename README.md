# KYC Agent Suite

A multi-agent AI system for KYC compliance — document analysis, regulatory Q&A, and full customer risk assessment — powered by LangGraph, Gemini 3 Flash, and a RAG pipeline over MAS and FATF regulatory corpora.

## Documentation

📄 **[Link to Technical Documentation](https://docs.google.com/document/d/1L80y2Ef69Xyxz11QpwQnDzCgKkpizxqvl4_0mP9x9ew/edit?usp=sharing)**

This document contains details about the project architecture, agents, RAG pipeline, design decisions, and deployment details.

## Try It Live!

🌐 **[Link to Deployed App](http://13.212.149.181:3000)**

### Sample Questions to Try

**No documents needed**
- *"What are the CDD requirements under MAS Notice 626?"*
- *"What enhanced due diligence applies to PEPs in Singapore?"*
- *"What are the FATF grey-list criteria and consequences for a customer from a listed country?"*

**Attach a passport or ID image**
- *"What information is on this document?"*
- *"Are there any anomalies in this identity document?"*

**Attach identity documents + optionally fill in customer details**
- *"Perform a full KYC check on this customer who wants to open an investment account."*
- *"Run a KYC check and flag any enhanced due diligence requirements."*

## Running Application Locally

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker + Docker Compose
- Google AI Studio API key — [get one free](https://aistudio.google.com)


### Step 1 — Clone Repository

```bash
git clone https://github.com/agarwal-anjali/kyc-agent-suite.git
```

### Step 2 — Regulatory Corpus

Download the following public documents into `backend/data/regulatory_corpus/`:

| Document | Source |
|---|---|
| MAS Notice 626 — AML/CFT for Banks | [mas.gov.sg](https://www.mas.gov.sg/regulation/notices/notice-626) |
| MAS Notice 1014 — AML/CFT for Finance Companies | [mas.gov.sg](https://www.mas.gov.sg/regulation/notices/notice-1014) |
| MAS Technology Risk Management Guidelines | [mas.gov.sg](https://www.mas.gov.sg/regulation/guidelines) |
| MAS Guidelines on Individual Accountability | [mas.gov.sg](https://www.mas.gov.sg/regulation/guidelines) |
| FATF 40 Recommendations | [fatf-gafi.org](https://www.fatf-gafi.org/content/dam/fatf-gafi/recommendations/FATF%20Recommendations%202012.pdf) |
| FATF Guidance on PEPs (Rec 12 & 22) | [fatf-gafi.org](https://www.fatf-gafi.org/content/dam/fatf-gafi/guidance/Guidance-PEP-Rec12-22.pdf) |
| FATF High-Risk Jurisdictions | [fatf-gafi.org](https://www.fatf-gafi.org/en/topics/high-risk-and-other-monitored-jurisdictions.html) |



### Step 3 — Backend (API + Qdrant via Docker Compose)

The backend runs both the FastAPI server and Qdrant vector database together via Docker Compose.

```bash
cd kyc-agent-suite/backend

# Configure environment
cp .env.example .env

# Open .env and set GOOGLE_API_KEY to your actual key

# Start both Qdrant and the API
docker-compose up -d --build

# Verify both are running
docker-compose ps

# Perform health check to see backend api is available
curl http://localhost:8000/health
# {"status":"ok","timestamp":"...","active_sessions":0}
```

The API will be available at `http://localhost:8000`.

Qdrant will be available at `http://localhost:6333`.

---

### Step 4 — Corpus Ingestion

This step embeds the downloaded documents into Qdrant. Run it once after the backend is up.

```bash
# Activate virtual environment
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Run ingestion
python -m ingestion.ingest --corpus-dir data/regulatory_corpus
```

**Note:** 

Ingestion is additive — if you add new documents later, re-running the command will only embed the new files and skip everything already in Qdrant.

---

### Step 5 — Frontend

```bash
cd ../frontend

npm install

# Copy and configure environment
cp .env.example .env.development
# .env.development already has:
# VITE_API_URL=http://localhost:8000
# VITE_USE_MOCK=true

npm run dev
# Frontend running at http://localhost:5173
```

**Note:** 

Mock mode is enabled by default in local development (`VITE_USE_MOCK=true`). The UI returns realistic canned responses for all four suggestion cards without making any LLM or Qdrant calls — useful for UI development and testing without spending API credits.

To test against the real backend, set `VITE_USE_MOCK=false` in `.env.development`.

In production builds, mock mode is automatically disabled (`import.meta.env.DEV` is false).


