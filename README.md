<div align="center">
  <img src="./logo.jpeg" alt="Morpheus Logo" width="80" />
  <h1>MORPHEUS</h1>
  <p><strong>The Autonomous Multi-Agent Workflow Architect</strong></p>
  
  <p>
    <a href="#features">Features</a> •
    <a href="#architecture">Architecture</a> •
    <a href="#tech-stack">Tech Stack</a> •
    <a href="#installation">Installation</a> •
    <a href="#deployment">Deployment</a>
  </p>
</div>

---

**MORPHEUS** is a next-generation, AI-driven automation platform that dynamically constructs, debates, and executes complex enterprise workflows. Instead of relying on static, hardcoded logic, MORPHEUS uses a multi-agent **Architecture Court** to debate the best way to execute a user's business objective, compiling the consensus into a secure, executable state machine.

## ✨ Features

- 🏛️ **The Architecture Court**: A multi-agent debate system where an **Architect** agent proposes a workflow, and **Security**, **Efficiency**, and **Compliance** agents cross-examine and modify the proposal to ensure it meets strict enterprise standards.
- 🛡️ **Hallucination Firewall**: A rigorous execution gateway that verifies LLM-generated parameters against pre-registered, version-controlled OpenAPI schemas before any external API is called.
- 🧬 **Causal Graph & TRC Autopsy**: Integrates with Neo4j to build a causal graph of all decisions. If an execution fails or breaches SLA, the **Transparent Reasoning Court (TRC)** performs a 4-phase autopsy to autonomously patch the architecture.
- ⚡ **Real-Time Execution State**: Complete visibility into workflow execution, live agent debates, and firewall interceptions via an event-driven Server-Sent Events (SSE) pipeline.
- 🔄 **Unified Deployment**: A streamlined multi-stage Docker setup that compiles the React frontend and runs the Python FastAPI backend on a single unified port, perfect for one-click deployments.

## 🏗️ Architecture

1. **Convene (Draft Phase)**: The user provides a natural language business objective.
2. **Debate**: The Architecture Court runs a 3-round algorithmic debate using external LLMs (OpenRouter/Sarvam).
3. **Compile**: The approved node graph is compiled into a JSON State Machine.
4. **Execute**: The background worker executes nodes asynchronously. API calls must pass the Hallucination Firewall.
5. **Autopsy (Optional)**: If a node fails or an SLA breaches, the TRC rebuilds the causal chain and patches the node.

## 💻 Tech Stack

- **Frontend**: React, Vite, ReactFlow (for node graphing), Vanilla CSS (glassmorphism/dark mode aesthetics).
- **Backend**: FastAPI, Python 3.10+, SQLAlchemy, SQLite (state), Neo4j (causal graph logic).
- **AI Models**: OpenRouter API (`openrouter/free` fallback loops), Sarvam AI (for Indian compliance regulations).
- **Deployment**: Docker (Multi-stage build), Render.

## 🚀 Installation

### Prerequisites
- Python 3.10+
- Node.js 18+
- [Neo4j AuraDB](https://neo4j.com/cloud/aura/) (Free tier)
- [OpenRouter API Key](https://openrouter.ai/)

### 1. Clone & Set Up Backend

```bash
git clone https://github.com/lalith-l/pega.git
cd pega/backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

Create a `.env` file in the `backend/` directory:
```env
OPENROUTER_API_KEY=sk-or-v1-...
SARVAM_API_KEY=your_sarvam_key
NEO4J_URI=neo4j+s://your-db.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
```

### 2. Set Up Frontend

```bash
cd ../frontend
npm install
npm run dev
```

### 3. Run Locally

To run the unified server (serving both the backend API and the frontend build on port 8000):

```bash
# Build the frontend first
cd frontend
npm run build

# Run the FastAPI server
cd ../backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Open `http://localhost:8000` in your browser.

## ☁️ Deployment (Render)

MORPHEUS is configured for zero-downtime deployment on Render.

1. Connect your GitHub repository to Render as a **Web Service**.
2. Set the Runtime to **Docker**.
3. Render will automatically detect the `Dockerfile` at the root of the project.
4. Add the following **Environment Variables** in Render:
   - `OPENROUTER_API_KEY`
   - `SARVAM_API_KEY`
   - `NEO4J_URI`
   - `NEO4J_USERNAME`
   - `NEO4J_PASSWORD`
5. Deploy! The multi-stage Dockerfile will compile the React app and serve it directly from the FastAPI backend on a single URL.

## 📝 License

Proprietary / Internal Use Only.
