HIKARI AI (光 AI)
A locally hosted AI assistant powered by Ollama, FastAPI and React.

HIKARI AI is an experimental full-stack AI assistant combining local language-model inference, a responsive chat interface, conversation history, persistent memory, and web-assisted research.
Status: v3.5.2 — under active development, intended for local use. The backend must not be exposed publicly without authentication, authorization, and security testing.

Features
- Local AI chat using Ollama and qwen2.5:7b.
- React chat interface with Markdown and GitHub-flavored Markdown rendering.
- Conversation history stored using SQLite; browser chat state also persists in localStorage.
- Persistent memory with backend memory endpoints.
- Web-assisted research with evidence-validation and response-quality helpers.
- User correction workflow with local approval endpoints.
- English, Hindi and Roman Hinglish response instructions.
- Browser speech capabilities where supported.
These features are under development; the project does not fine-tune or train its underlying language model.

Technology stack
Layer	Technologies
Frontend	React 19, Vite 8, JavaScript, CSS
Backend	Python, FastAPI, Uvicorn, Pydantic, HTTPX
Local LLM	Ollama, Qwen 2.5 7B
Storage	SQLite, browser localStorage
Web research	DDGS, Beautiful Soup, HTTPX
Markdown rendering	react-markdown, remark-gfm


Project structure
HIKARI-AI/
├── backend/
│   ├── main.py                # FastAPI app and chat logic
│   ├── web_search.py          # Web search and retrieval
│   ├── evidence_validator.py  # Evidence checks
│   ├── response_quality.py    # Answer-quality helpers
│   └── requirements.txt
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── App.css
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
├── .gitignore
└── README.md
Getting started on Windows
Requirements
- Git, Python and pip
- Node.js and npm compatible with Vite 8
- Ollama installed and running
1. Clone the repository
git clone https://github.com/raghavkuju/HIKARI-AI.git
cd HIKARI-AI
2. Download the local model
ollama pull qwen2.5:7b
Ollama should run locally on 127.0.0.1:11434. Model weights are not included in this repository.
3. Set up the backend
Run the following commands from the repository root:
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
python -m pip install beautifulsoup4 ddgs
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
Dependency note: The current backend/requirements.txt does not include beautifulsoup4 or ddgs, although backend/web_search.py imports them. The extra installation command is a temporary workaround until the requirements file is updated.
- Health check: http://127.0.0.1:8000/health
- Interactive API docs: http://127.0.0.1:8000/docs
4. Start the frontend
In a second terminal, starting from the repository root:
cd frontend
npm install
npm run dev
Open http://localhost:5173. The frontend currently sends requests to http://127.0.0.1:8000, so the backend must run on the same computer.
API overview
Method	Endpoint	Purpose
GET	/	App information
GET	/health	Health check
POST	/chat	Send a chat message
GET	/search	Web-assisted search
GET	/conversations/{conversation_id}	Retrieve messages
GET / POST	/memories	View and save memories
DELETE	/memories/{key}	Delete a memory
GET	/corrections/pending	Review pending corrections (local client check)
POST	/corrections/{correction_id}/approve	Approve a correction (local client check)


Security and privacy
Important: The current version is not safe for public deployment.
- Main conversation and memory APIs do not implement user authentication. Anyone who can reach the backend may be able to read or change stored information.
- Correction administration checks whether the client address is local, which is not a substitute for authentication.
- SQLite conversation and memory data should remain private and must not be committed.
- Browser localStorage contains chat state; avoid entering secrets on shared devices.
- Keep the server bound to 127.0.0.1 during local development. Do not change it to 0.0.0.0 without implementing and testing access controls.
- Never commit .env files, API keys, passwords, database files, virtual environments or model weights.
- Before internet deployment, add authentication, per-user authorization, rate limits, input-size limits, configuration management, and security tests.
A basic string-pattern scan does not guarantee that the repository or its commit history contains no secrets.
Development roadmap
- [ ] Add authentication and per-user data isolation
- [ ] Complete dependency manifest and setup automation
- [ ] Configure frontend API base URL via environment variables
- [ ] Add automated tests and continuous integration
- [ ] Include verified screenshots and demo instructions
- [ ] Design a secure deployment architecture
Author
Developed by Deepak Kujur.
HIKARI (光) is Japanese for light.
