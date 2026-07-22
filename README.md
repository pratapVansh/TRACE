# TRACE

### Technical Records & Asset Compliance Engine

> An AI-powered Industrial Knowledge Intelligence Platform that transforms scattered, unstructured industrial documents into a unified, searchable **Industrial Knowledge Brain** — with semantic search, knowledge graphs, and multi-agent AI orchestration.

[![Status](https://img.shields.io/badge/status-milestone--3--4--5--active-blue)]()
[![License](https://img.shields.io/badge/license-proprietary-lightgrey)]()

---

## Overview

TRACE ingests engineering drawings, P&IDs, SOPs, maintenance logs, inspection reports, OEM manuals, safety manuals, spreadsheets, scanned images, and email threads — then transforms them into a single intelligence layer using OCR, document parsing, embedding vectors, a knowledge graph, and orchestrated AI agents. Engineers, operators, and inspectors can ask natural-language questions and receive grounded answers with citations, asset insights, and compliance-aware reasoning.

---

## Key Features

| Feature | Description | Status |
| --- | --- | --- |
| **Smart Document Ingestion** | Upload PDF, DOCX, PPTX, XLSX, TXT, PNG, JPG with automatic classification and text extraction | ✅ |
| **OCR Pipeline** | Tesseract-based OCR for scanned PDFs and images | ✅ |
| **Semantic Search** | Embedding-based vector search (Sentence Transformers + Qdrant) with keyword and hybrid modes | ✅ |
| **Knowledge Graph** | Neo4j-powered entity extraction, relationship mapping, and graph traversal | ✅ |
| **Hybrid RAG** | Retrieval-Augmented Generation combining vector similarity + graph facts | ✅ |
| **AI Agent Framework** | 10+ specialized agents (Document, Graph, Maintenance, Compliance, Asset Intelligence, RCA, Report, Workspace, Conversation, Search) | ✅ |
| **Multi-Agent Orchestration** | Automatic agent routing, chaining, parallel execution, collaboration, and fallback | ✅ |
| **AI Copilot Chat** | Conversational UI with streaming responses, citations, conversation history, and snapshots | ✅ |
| **Role-Based Access Control** | SuperAdmin, Admin, Engineer, Operator, Viewer with fine-grained permissions | ✅ |
| **JWT Authentication** | Register, login, refresh with rotation, logout, protected routes | ✅ |
| **Admin User Management** | Create, update roles, reset passwords, activate/deactivate users | ✅ |
| **Executive Dashboard** | KPIs, document counts, graph stats, recent activity, compliance overview | ✅ |
| **Enterprise UI** | Dark industrial theme, responsive layout, skeleton loaders, protected pages | ✅ |
| **Observability** | Agent/tool latency histograms, memory hit rates, hallucination tracking, citation coverage, Prometheus metrics | ✅ |
| **Audit Logging** | Full audit trail for all user actions | ✅ |
| **Rate Limiting** | Per-endpoint rate limiting for auth, upload, chat, search, RAG | ✅ |
| **Long-Term Memory** | User-specific memory with embedding, importance scoring, and consolidation | ✅ |
| **Investigation Records** | Root Cause Analysis persistence with confidence tracking | ✅ |

---

## System Architecture

```mermaid
flowchart TB
    subgraph Client["Frontend — Next.js + TypeScript + Tailwind + shadcn/ui"]
        UI["Copilot UI / Search / Dashboard / Knowledge Graph / Agents"]
    end

    subgraph API["Backend — FastAPI"]
        GW["REST API Gateway"]
        AUTH["Auth & Authorization"]
        DOC["Document Service"]
        PROC["Processing Pipeline"]
    end

    subgraph AI["AI Layer"]
        ORCH["AI Orchestrator"]
        AGENTS["10+ Specialized Agents<br/>(Document, Graph, Maintenance,<br/>Compliance, Asset, RCA, Report,<br/>Workspace, Conversation, Search)"]
        RAG["Hybrid RAG Service"]
        RET["Hybrid Retriever<br/>(Vector + Graph)"]
        EMB["Sentence Transformers"]
        LLM["Groq LLM<br/>(Llama 3.3 70B)"]
    end

    subgraph Data["Data & Knowledge Stores"]
        PG[("PostgreSQL<br/>Documents, Users,<br/>Conversations, Memories")]
        NEO[("Neo4j Knowledge Graph<br/>Entities, Relationships,<br/>Asset Hierarchy")]
        VEC[("Qdrant Vector Store<br/>Document Chunk Embeddings")]
        FS[("Local Filesystem<br/>Document Storage")]
    end

    UI -->|HTTP / SSE| GW
    GW --> AUTH
    GW --> DOC
    GW --> PROC
    GW --> ORCH
    GW --> RAG
    ORCH --> AGENTS
    AGENTS -->|Tool Calls| RET
    AGENTS --> LLM
    RET --> VEC
    RET --> NEO
    RAG --> RET
    RAG --> LLM
    DOC --> PG
    DOC --> FS
    PROC --> FS
    PROC --> VEC
    PROC --> NEO
    ORCH --> PG
```

---

## Tech Stack

### Frontend

| Technology | Purpose |
| --- | --- |
| **Next.js 16** | React framework, App Router, streaming UI |
| **TypeScript** | Type-safe frontend development |
| **TailwindCSS v4** | Utility-first styling |
| **shadcn/ui** | Accessible, composable component library |
| **Axios** | HTTP client with JWT refresh interceptor |
| **React Hook Form + Zod** | Form validation |
| **vis-network** | Knowledge graph visualization |
| **Lucide React** | Icon library |

### Backend

| Technology | Purpose |
| --- | --- |
| **FastAPI** | High-performance Python REST API & orchestration gateway |
| **SQLAlchemy 2 (async)** | ORM with async PostgreSQL access |
| **Alembic** | Schema migrations (18+ migration files) |
| **passlib + bcrypt** | Password hashing |
| **python-jose** | JWT access and refresh tokens |
| **Pydantic v2** | Data validation and settings management |
| **httpx** | Async HTTP client |
| **pytest** | Testing framework |

### AI / Intelligence

| Technology | Purpose |
| --- | --- |
| **LangChain Text Splitters** | Document chunking |
| **Sentence Transformers** | Embedding generation (`all-MiniLM-L6-v2`) |
| **Qdrant** | Vector similarity search |
| **Neo4j** | Knowledge graph (entities, relationships, asset hierarchy) |
| **Groq** | LLM inference (Llama 3.3 70B) |
| **Tesseract (pytesseract)** | OCR for scanned documents |
| **PyMuPDF** | PDF text extraction |
| **python-docx / python-pptx / openpyxl** | Office document parsing |
| **langdetect** | Language detection |

### Infrastructure

| Technology | Purpose |
| --- | --- |
| **PostgreSQL 15+** | Primary database |
| **Docker** | Containerized deployment (planned) |
| **OpenTelemetry** | Distributed tracing (optional) |
| **Vault** | Secret management (optional) |

---

## Folder Structure

```text
TRACE/
├── ai/                              # AI pipeline (placeholder for future expansion)
├── backend/                         # FastAPI service
│   ├── app/
│   │   ├── agents/                  # AI agent framework
│   │   │   └── framework/
│   │   │       ├── agents/          # 10+ specialized agent implementations
│   │   │       ├── tools/           # Agent tool definitions
│   │   │       ├── memory/          # Long-term memory management
│   │   │       ├── collaboration/   # Multi-agent collaboration
│   │   │       ├── workflow/        # Multi-agent workflow schemas
│   │   │       ├── planner/         # Agent planning and routing
│   │   │       ├── orchestrator.py  # AIOrchestrator (single & multi-agent)
│   │   │       ├── base.py          # BaseAgent abstract class
│   │   │       ├── registry.py      # Agent registry
│   │   │       └── context.py       # Agent execution context
│   │   ├── ai/                      # LLM provider abstraction
│   │   │   ├── base.py              # LLMProvider interface
│   │   │   └── groq_provider.py     # Groq LLM implementation
│   │   ├── api/routes/              # 17 API route modules
│   │   ├── core/                    # Config, security, auth, middleware
│   │   ├── db/                      # Database session and base
│   │   ├── graph/                   # Neo4j graph store & queries
│   │   ├── middleware/              # Correlation, rate limit, security headers
│   │   ├── models/                  # 13 SQLAlchemy models
│   │   ├── processing/              # Document processing pipeline
│   │   │   ├── ocr/                # OCR engine & preprocessing
│   │   │   ├── processors/         # PDF, DOCX, PPTX, XLSX, image processors
│   │   │   └── service.py          # Processing queue service
│   │   ├── repositories/           # Data access layer (8 repositories)
│   │   ├── schemas/                # Pydantic DTOs (21 schema modules)
│   │   ├── services/               # Business logic (45+ service modules)
│   │   └── tasks/                  # Background workers
│   ├── alembic/versions/           # 18 database migrations
│   └── scripts/                    # Utility scripts
├── datasets/                        # Sample datasets (placeholder)
├── docs/                            # Architecture & planning documentation
├── frontend/                        # Next.js application
│   ├── app/                         # 16+ route pages
│   │   ├── copilot/                 # AI Copilot chat interface
│   │   ├── knowledge-graph/         # Interactive graph visualization
│   │   ├── documents/              # Document management & upload
│   │   ├── search/                 # Semantic search interface
│   │   ├── dashboard/              # Executive dashboard
│   │   ├── assets/                 # Asset hierarchy & views
│   │   ├── compliance/             # Compliance overview
│   │   ├── maintenance/            # Maintenance workflows
│   │   ├── sop-library/            # SOP library
│   │   ├── ai-agents/              # AI agent hub & chat
│   │   ├── audit-logs/             # Audit trail viewer
│   │   ├── settings/               # System settings, users, roles
│   │   └── access-denied/          # Permission denied page
│   ├── components/                 # Reusable UI components
│   │   ├── ai-workspace/           # Copilot, agents, knowledge graph
│   │   ├── dashboard/              # Dashboard widgets
│   │   ├── knowledge/              # Documents, search, upload
│   │   ├── operations/             # Assets, compliance, maintenance, SOP
│   │   ├── administration/         # Users, roles, settings
│   │   ├── layout/                 # Sidebar, topbar, auth shell
│   │   ├── auth/                   # Login, register forms
│   │   └── ui/                     # shadcn/ui primitives
│   ├── lib/                        # API clients, auth, utilities
│   ├── hooks/                      # Custom React hooks
│   ├── types/                      # TypeScript type definitions
│   └── stores/                     # Zustand stores (scaffolded)
├── scripts/                         # Database initialization
├── .env.example                     # Environment template
└── README.md
```

---

## AI / Agent Workflow

```mermaid
flowchart LR
    User["User Question"] --> ORCH["AI Orchestrator"]
    ORCH --> ROUTER["Agent Router"]
    ROUTER --> AGENTS["Specialized Agents"]
    
    subgraph Agents["Agent Pool"]
        DA["Document Agent<br/>Search, Summarize, Compare"]
        GA["Graph Agent<br/>Search, Neighbors, Paths"]
        MA["Maintenance Agent<br/>Checklists, History, Risk"]
        CA["Compliance Agent<br/>Checks, Gaps, Recommendations"]
        AAA["Asset Agent<br/>Search, Relationships, Risk"]
        RCA["RCA Agent<br/>Evidence, Root Cause, Similar"]
        RA["Report Agent<br/>Generate, Summarize"]
        WA["Workspace Agent<br/>Files, Charts, Python"]
    end
    
    AGENTS --> DA
    AGENTS --> GA
    AGENTS --> MA
    AGENTS --> CA
    AGENTS --> AAA
    AGENTS --> RCA
    AGENTS --> RA
    AGENTS --> WA

    DA & GA & MA & CA & AAA & RCA --> RET["Hybrid Retriever"]
    RET --> VEC[(Vector Store)]
    RET --> KG[(Knowledge Graph)]
    
    DA & GA & MA & CA & AAA & RCA --> LLM["Groq LLM"]
    
    ORCH --> MEM["Long-Term Memory<br/>Store & Retrieve"]
    MEM --> PG[(PostgreSQL)]
    
    ORCH --> RESP["Response<br/>+ Citations<br/>+ Confidence"]
    RESP --> User
```

### How it works

1. **Question** enters via the Copilot chat or agent API
2. **Orchestrator** selects the best agent(s) automatically or by explicit request
3. **Agents** use tools to search documents, query the knowledge graph, analyze assets, check compliance, and generate reports
4. **Hybrid Retriever** combines vector similarity search (Qdrant) with graph facts (Neo4j)
5. **LLM** synthesizes retrieved context into a grounded answer with citations
6. **Long-Term Memory** stores user interactions and consolidates important information
7. **Confidence Scoring** evaluates answer reliability based on evidence strength, source agreement, and LLM certainty

### Available Agents

| Agent | Tools | Purpose |
| --- | --- | --- |
| **DocumentAgent** | Search, Summary, Metadata, Comparison | Analyze and compare documents |
| **KnowledgeGraphAgent** | Search, Neighbor, Path, Statistics | Explore entity relationships |
| **MaintenanceAgent** | Search, Recommendation, History, Checklist, Risk | Maintenance planning and analysis |
| **ComplianceAgent** | Search, Check, Gap, Recommendation | Identify compliance gaps |
| **AssetIntelligenceAgent** | Search, Relationship, Risk, Maintenance, Summary | Asset-centric intelligence |
| **RootCauseAnalysisAgent** | Incident Search, Evidence, Root Cause, Similar Incidents | Investigate failures |
| **ReportGenerationAgent** | Generate, Executive Summary, Markdown | Generate structured reports |
| **WorkspaceAgent** | File ops, SQL, CSV, Excel, Python, Charts, Email, REST, PI Historian, SAP | Multi-tool workspace |
| **ConversationAgent** | Conversation history | Context-aware conversation |
| **SearchAgent** | Hybrid search | General purpose search |

---

## Installation

### Prerequisites

- **Node.js 20+**
- **Python 3.11+**
- **PostgreSQL 15+** (local or remote)
- **Qdrant** (optional — for vector search)
- **Neo4j** (optional — for knowledge graph)
- **Tesseract OCR** (optional — for scanned document OCR)
- **Groq API key** (optional — for AI features)

### 1. Environment Setup

```bash
cp .env.example .env
```

Edit `.env` with your credentials. Key variables:

```bash
# PostgreSQL
POSTGRES_USER=trace
POSTGRES_PASSWORD=trace
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=trace
DATABASE_URL=postgresql+asyncpg://trace:trace@localhost:5432/trace

# JWT
JWT_SECRET_KEY=your-secret-key-here

# Qdrant (optional)
QDRANT_URL=http://localhost:6333

# Groq (optional)
GROQ_API_KEY=gsk-...

# Neo4j (optional)
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password

# Bootstrap SuperAdmin
SUPER_ADMIN_EMAIL=admin@company.com
SUPER_ADMIN_PASSWORD=secure-password
SUPER_ADMIN_FULL_NAME=Admin User
```

Also create the frontend env file:

```bash
# frontend/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 2. Database Setup

```bash
# Create database (as postgres superuser)
psql -U postgres -f scripts/init-db.sql

# Apply migrations
cd backend
.venv\Scripts\activate    # Windows
alembic upgrade head
```

### 3. Bootstrap SuperAdmin

```bash
cd backend
.venv\Scripts\activate
python scripts/create_super_admin.py
```

This creates the first SuperAdmin user. Registration via the API always creates **Viewer**-role users.

### 4. Install Dependencies

```bash
# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Frontend
cd frontend
npm install
```

---

## Running the Project

### Backend

```bash
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm run dev
```

### Services (Optional)

```bash
# Qdrant (Docker)
docker run -p 6333:6333 qdrant/qdrant

# Neo4j (Docker)
docker run -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:5

# Start Tesseract OCR (install system package)
```

### Access

| Service | URL |
| --- | --- |
| **Frontend** | http://localhost:3000 |
| **Backend API** | http://localhost:8000 |
| **Swagger UI** | http://localhost:8000/docs |
| **Health Check** | http://localhost:8000/api/health |

---

## API Overview

| Prefix | Routes | Description |
| --- | --- | --- |
| `GET /api/health` | 1 | Service health check |
| `POST /api/auth/*` | 5 | Register, login, refresh, logout, me |
| `GET/POST/PATCH/DELETE /api/documents/*` | 6 | Document CRUD, upload, download |
| `GET /api/documents/{id}/processing-status` | 1 | Document processing status |
| `GET/POST/PATCH /api/admin/users/*` | 5 | Admin user management |
| `GET /api/search` | 1 | Semantic, keyword, hybrid, ranked search |
| `POST /api/rag/*` | 3 | RAG retrieve, query, graph-enhanced query |
| `POST /api/chat/*` | 14 | Chat, stream, conversations, snapshots |
| `GET/POST/PATCH/DELETE /api/graph/*` | 9 | Graph health, entities, neighbors, paths |
| `POST /api/agents/*` | 3 | Single & multi-agent execution, streaming |
| `GET/POST /api/processing/*` | 5 | Processing job management |
| `GET /api/vector/health` | 1 | Vector store health |
| `GET /api/llm/health` | 1 | LLM provider health |
| `GET /api/dashboard` | 1 | Executive dashboard data |
| `GET /api/observability/dashboard` | 1 | Monitoring and metrics dashboard |
| `GET/POST /api/metrics` | 2 | Prometheus & JSON metrics |
| `GET/POST/PATCH/DELETE /api/chunks` | 1 | Document chunks |
| `GET /api/demo/admin` | 1 | Demo admin access test |

Full API specification is available at `/docs` (Swagger) when the backend is running.

---

## Database Overview

### PostgreSQL Models (13 tables)

| Table | Purpose |
| --- | --- |
| `users` | User accounts with role FK and password hashes |
| `roles` | Role definitions (SuperAdmin, Admin, Engineer, Operator, Viewer) |
| `refresh_tokens` | JWT refresh token tracking with rotation |
| `documents` | Document metadata, status, classification, department |
| `document_versions` | Versioned document storage with checksums |
| `document_extracted_text` | Extracted text content per version |
| `document_chunks` | Chunked document content with embeddings |
| `ingestion_jobs` | Document ingestion job tracking |
| `processing_jobs` | Processing pipeline job lifecycle |
| `audit_logs` | Full audit trail of user actions |
| `conversations` | Chat conversation sessions |
| `messages` | Individual chat messages with citations |
| `conversation_snapshots` | Working memory snapshots per turn |
| `memories` | Long-term user memories with embeddings |
| `investigations` | Root cause analysis investigation records |

### Neo4j Knowledge Graph

- **Entity nodes** with types (Asset, Compressor, Pump, Valve, Failure, Cause, etc.)
- **Relationship edges** connecting entities
- Supported queries: entity search, neighbor traversal, shortest path, batch neighbor fetch, schema introspection

### Qdrant Vector Store

- Collection: `document_chunks`
- Full-text index for keyword search
- Hybrid search combining vector similarity + keyword matching
- Filterable by document_id, filename, language, document_type, date range

---

## Project Workflow

```mermaid
flowchart TD
    UPLOAD["Upload Document"] --> CLASSIFY["Classify Document Type"]
    CLASSIFY --> PROCESS["Process Document"]
    
    subgraph Processing["Document Processing Pipeline"]
        EXTRACT["Text Extraction<br/>PDF / DOCX / PPTX / XLSX / TXT / Image"]
        OCR["OCR (if scanned)"]
        DETECT["Language Detection"]
        META["Metadata Extraction"]
        CHUNK["Chunking"]
        GRAPH["Graph Entity Extraction"]
        EMBED["Embedding Generation"]
        INDEX["Vector Indexing"]
    end
    
    PROCESS --> EXTRACT
    EXTRACT --> OCR
    OCR --> DETECT
    DETECT --> META
    META --> CHUNK
    CHUNK --> GRAPH
    GRAPH --> EMBED
    EMBED --> INDEX
    
    INDEX --> SEARCHABLE[(Searchable<br/>Knowledge Brain)]
    
    SEARCHABLE --> SEARCH["Semantic / Hybrid Search"]
    SEARCHABLE --> RAG["RAG Query"]
    SEARCHABLE --> CHAT["AI Copilot"]
    SEARCHABLE --> KG["Knowledge Graph"]
    SEARCHABLE --> AGENTS["AI Agents"]
```

---

## Screenshots

> Screenshots go here — add images to `docs/assets/screenshots/`

| Screen | Path | Status |
| --- | --- | --- |
| Login | `docs/assets/screenshots/login.png` | Pending |
| Dashboard | `docs/assets/screenshots/dashboard.png` | Pending |
| Copilot Chat | `docs/assets/screenshots/copilot.png` | Pending |
| Knowledge Graph | `docs/assets/screenshots/knowledge-graph.png` | Pending |
| Documents | `docs/assets/screenshots/documents.png` | Pending |
| Search | `docs/assets/screenshots/search.png` | Pending |

---

## Current Status

### Implemented

- **User Authentication**: Full JWT auth with registration, login, refresh token rotation, logout
- **Role-Based Access**: 5 roles with granular permissions across all modules
- **User Management**: Admin CRUD, role assignment, password reset, status management
- **Document Management**: Upload, versioning, download, update, soft-delete
- **Document Processing Pipeline**: PDF, DOCX, PPTX, XLSX, TXT, image processing with OCR fallback
- **Chunking & Embedding**: Smart document chunking with Sentence Transformers embeddings
- **Vector Search**: Qdrant-powered semantic, keyword, hybrid, and ranked search modes
- **Knowledge Graph**: Neo4j entity extraction, neighbor/path queries, batch operations
- **Hybrid RAG**: Combined vector + graph retrieval with LLM-based answer generation
- **AI Agent Framework**: 10+ specialized agents with tool-based execution
- **Multi-Agent Orchestration**: Automatic routing, chaining, parallel execution, collaboration
- **AI Copilot**: Streaming chat with conversation management, snapshots, citations
- **Executive Dashboard**: Real-time KPIs, document/graph stats, activity feed
- **Compliance & Asset Modules**: Dedicated pages for compliance, assets, maintenance, SOP library
- **Admin UI**: User management, role management, system settings
- **Observability**: Agent/tool latency tracking, memory efficiency, hallucination rate, Prometheus metrics
- **Audit Logging**: Full audit trail for document and user operations
- **Long-Term Memory**: Per-user memory storage with embedding and importance scoring
- **Root Cause Analysis**: Investigation records with evidence tracking
- **Rate Limiting**: Configurable per-endpoint rate limiting
- **Enterprise UI**: Dark industrial theme, responsive layout, permission-gated pages

### In Progress / Next

- AI pipeline refinements and agent accuracy improvements
- Testing coverage expansion
- Deployment and CI/CD configuration
- Performance optimization at scale

---

## Future Roadmap

Based on existing project structure and planned documentation:

| Area | Planned |
| --- | --- |
| **Universal Ingestion** | Enhanced support for additional document formats |
| **Advanced OCR** | Improved scanned document handling |
| **Compliance Module** | Deeper regulatory compliance checking |
| **Asset Hierarchy** | Rich asset tree browsing and management |
| **Notifications** | Alert system for document processing and compliance events |
| **Deployment** | Docker compose, CI/CD pipelines |
| **Performance** | Caching, query optimization, horizontal scaling |
| **Evaluation** | Automated RAG evaluation and agent benchmarking |

---

## Documentation Index

| Document | Description |
| --- | --- |
| [`docs/00_OFFICIAL_PROBLEM_STATEMENT.md`](docs/00_OFFICIAL_PROBLEM_STATEMENT.md) | Official Problem Statement 8 brief |
| [`docs/01_PROBLEM_STATEMENT.md`](docs/01_PROBLEM_STATEMENT.md) | Problem context, challenges, and expected solution |
| [`docs/02_PRODUCT_REQUIREMENTS.md`](docs/02_PRODUCT_REQUIREMENTS.md) | Product vision, requirements, metrics, user stories |
| [`docs/03_SYSTEM_ARCHITECTURE.md`](docs/03_SYSTEM_ARCHITECTURE.md) | High-level system architecture |
| [`docs/04_DATABASE_ARCHITECTURE.md`](docs/04_DATABASE_ARCHITECTURE.md) | PostgreSQL schema design |
| [`docs/05_FRONTEND_ARCHITECTURE.md`](docs/05_FRONTEND_ARCHITECTURE.md) | Next.js frontend architecture |
| [`docs/06_BACKEND_ARCHITECTURE.md`](docs/06_BACKEND_ARCHITECTURE.md) | FastAPI backend architecture |
| [`docs/07_UI_UX_DESIGN.md`](docs/07_UI_UX_DESIGN.md) | UI/UX design system |
| [`docs/08_AI_ARCHITECTURE.md`](docs/08_AI_ARCHITECTURE.md) | AI layer architecture |
| [`docs/09_AGENT_ARCHITECTURE.md`](docs/09_AGENT_ARCHITECTURE.md) | Agent designs and framework |
| [`docs/10_RAG_PIPELINE.md`](docs/10_RAG_PIPELINE.md) | RAG pipeline design |
| [`docs/11_KNOWLEDGE_GRAPH.md`](docs/11_KNOWLEDGE_GRAPH.md) | Neo4j knowledge graph design |
| [`docs/12_DOCUMENT_PIPELINE.md`](docs/12_DOCUMENT_PIPELINE.md) | Document ingestion pipeline |
| [`docs/13_API_SPECIFICATION.md`](docs/13_API_SPECIFICATION.md) | REST API specification |
| [`docs/14_IMPLEMENTATION_ROADMAP.md`](docs/14_IMPLEMENTATION_ROADMAP.md) | 20-day implementation plan |
| [`docs/15_AI_DEVELOPMENT_RULES.md`](docs/15_AI_DEVELOPMENT_RULES.md) | AI engineering rules |
| [`docs/16_TESTING_STRATEGY.md`](docs/16_TESTING_STRATEGY.md) | Testing strategy |
| [`docs/17_PRESENTATION_GUIDE.md`](docs/17_PRESENTATION_GUIDE.md) | Demo and presentation guide |

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

Please ensure your code passes linting and existing tests.

---

## License

Proprietary — All rights reserved.

---

## Acknowledgements

- Problem Statement 8 — Industrial Knowledge Intelligence (challenge brief)
- [LangGraph](https://langchain-ai.github.io/langgraph/) — Agent orchestration framework
- [LangChain](https://python.langchain.com/) — LLM tooling and integrations
- [Neo4j](https://neo4j.com/) — Graph database
- [Qdrant](https://qdrant.tech/) — Vector search engine
- [Groq](https://groq.com/) — High-speed LLM inference
- [Sentence Transformers](https://www.sbert.net/) — Embedding models
- [FastAPI](https://fastapi.tiangolo.com/) — Backend framework
- [Next.js](https://nextjs.org/) — Frontend framework
- [shadcn/ui](https://ui.shadcn.com/) — UI component library
