# TRACE — AI Architecture

### Technical Records & Asset Compliance Engine · Problem Statement 8

> **Current implementation (2 October 2026).** TRACE uses a single explicit hybrid-RAG
> path: query understanding → Qdrant/Neo4j retrieval → cross-encoder reranking → prompt
> construction → Groq `openai/gpt-oss-120b` → lexical evidence classification. The former
> LangGraph multi-agent framework was removed after execution testing and is not a deferred
> runtime component. Conversation persistence and per-user long-term memory live in
> PostgreSQL.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Design Philosophy](#2-design-philosophy)
3. [AI Stack Overview](#3-ai-stack-overview)
4. [LLM](#4-llm)
5. [Embeddings](#5-embeddings)
6. [Retriever](#6-retriever)
7. [Vector Database](#7-vector-database)
8. [Knowledge Graph](#8-knowledge-graph)
9. [Prompt Flow](#9-prompt-flow)
10. [Confidence Score](#10-confidence-score)
11. [Memory](#11-memory)
12. [Hallucination Prevention](#12-hallucination-prevention)
13. [References](#13-references)

---

## 1. Overview

The AI layer is the **reasoning core** of TRACE. It transforms ingested industrial documents
into grounded, auditable intelligence — not open-ended chat. Every AI operation is anchored
to **source documents, asset context, and compliance obligations**.

TRACE does not behave like ChatGPT. It behaves like an **industrial operating system**:
deterministic where possible, evidence-backed always, and role-aware in every response.

| Principle | Meaning |
| --- | --- |
| **Grounded by default** | No answer without retrieved evidence |
| **Asset-centric** | Reasoning is scoped to assets, tags, and procedures |
| **Auditable** | Every claim is traceable to a source |
| **Agentic, not chatty** | Multi-step planning, not single-shot generation |
| **Fail safely** | Decline or flag when evidence is insufficient |

---

## 2. Design Philosophy

```mermaid
flowchart LR
    subgraph ChatGPT["Generic Chatbot"]
        Q1["Question"] --> LLM1["LLM"]
        LLM1 --> A1["Unverified Answer"]
    end
    subgraph TRACE["Industrial OS"]
        Q2["Question"] --> PLAN["Plan"]
        PLAN --> RET["Retrieve"]
        RET --> VERIFY["Verify"]
        VERIFY --> A2["Grounded Answer + Citations"]
    end
```

| Dimension | Generic LLM Chat | TRACE Industrial OS |
| --- | --- | --- |
| Knowledge source | Model weights | Ingested documents + graph |
| Answer style | Conversational | Operational, procedural |
| Provenance | None | Mandatory citations |
| Scope | Open domain | Industrial assets & compliance |
| Failure mode | Hallucinate | Decline / flag uncertainty |
| Memory | Session chat | Structured operational memory |

---

## 3. AI Stack Overview

```mermaid
flowchart TB
    subgraph Input
        Q["User Query"]
        CTX["Session / Asset Context"]
    end

    subgraph Intelligence["AI Intelligence Layer"]
        LG["Chat / RAG Orchestrator"]
        AG["Retrieval / Prompt / Grounding Services"]
        LC["Hybrid Retriever + Reranker"]
        EMB["Sentence Transformers"]
        LLM["LLM Provider"]
    end

    subgraph Stores["Knowledge Stores"]
        VEC[("Qdrant Vector Store")]
        NEO[("Neo4j Knowledge Graph")]
        PG[("PostgreSQL Metadata")]
    end

    subgraph Output
        ANS["Grounded Answer"]
        CIT["Citations"]
        CONF["Confidence Score"]
    end

    Q --> LG
    CTX --> LG
    LG --> AG
    AG --> LC
    LC --> EMB
    LC --> VEC
    AG --> NEO
    AG --> PG
    AG --> LLM
    LLM --> ANS
    LC --> CIT
    AG --> CONF
```

| Component | Technology | Role |
| --- | --- | --- |
| Orchestration | Application RAG services | Explicit, testable retrieval and generation flow |
| Retrieval tooling | Application services | Query understanding, fusion, reranking, deduplication |
| Embeddings | Sentence Transformers | Semantic vector generation |
| Vector search | Qdrant | Vector, keyword, and filtered retrieval |
| Graph reasoning | Neo4j | Asset/procedure/incident relationships |
| Metadata | PostgreSQL | Document, chunk, audit references |
| Generation | LLM | Synthesis grounded in retrieved context |

---

## 4. LLM

The LLM is the **synthesis engine** — it generates language from retrieved context. It is
never the primary knowledge source.

### Role in TRACE

| Function | Description |
| --- | --- |
| Answer synthesis | Compose grounded responses from retrieved chunks |
| Query decomposition | Break complex questions into sub-queries |
| Entity interpretation | Normalize tags, asset names, procedure references |
| Summarization | Condense multi-document evidence |
| Verification | Self-check claims against provided context |

### LLM constraints

```mermaid
flowchart TD
    CTX["Retrieved Context ONLY"] --> LLM["LLM"]
    LLM --> OUT["Structured Output"]
    OUT --> CHECK{"All claims\nin context?"}
    CHECK -->|Yes| PASS["Release answer"]
    CHECK -->|No| REJECT["Revise or decline"]
```

| Constraint | Enforcement |
| --- | --- |
| Context-only generation | System prompt forbids external knowledge |
| Structured output | JSON schema for answers, citations, confidence |
| Temperature control | Low temperature for factual/procedural answers |
| Token budget | Context window managed by retriever |
| Role conditioning | Prompts scoped to industrial domain |

### LLM selection criteria

| Criterion | Requirement |
| --- | --- |
| Context window | Sufficient for multi-chunk retrieval |
| Instruction following | Strong adherence to system prompts |
| Structured output | JSON / function-calling support |
| Self-hostable option | Data privacy for enterprise deployment |
| Latency | Supports streaming for Copilot UX |

---

## 5. Embeddings

Embeddings convert text chunks into dense vectors that capture **semantic meaning**, enabling
similarity search beyond keyword matching.

```mermaid
flowchart LR
    CHK["Text Chunks"] --> ST["Sentence Transformers"]
    ST --> VEC["384-dim Vectors"]
    VEC --> IDX["Qdrant Collection"]
    Q["Query"] --> ST2["Same Model"]
    ST2 --> QV["Query Vector"]
    QV --> IDX
    IDX --> TOP["Top-K Results"]
```

| Aspect | Specification |
| --- | --- |
| Model | Sentence Transformers (e.g. `all-MiniLM-L6-v2` or domain-fine-tuned) |
| Dimension | Model-dependent (typically 384–768) |
| Normalization | L2-normalized for cosine similarity |
| Batch size | Configurable for ingestion throughput |
| Caching | Content-hash keyed embedding cache |

### Embedding lifecycle

| Stage | Action |
| --- | --- |
| Ingestion | Embed every chunk after parsing |
| Query time | Embed user question with same model |
| Re-embedding | Triggered on model upgrade |
| Invalidation | On document re-ingestion or revision |

---

## 6. Retriever

The retriever is a **hybrid search engine** combining vector similarity, knowledge-graph
traversal, and metadata filtering.

```mermaid
flowchart TB
    Q["Query"] --> ROUTE{"Retrieval Router"}
    ROUTE -->|Semantic| VS["Vector Search - Qdrant"]
    ROUTE -->|Relational| GS["Graph Search - Neo4j"]
    ROUTE -->|Structured| MF["Metadata Filter - PostgreSQL"]
    VS --> MERGE["Result Fusion & Reranking"]
    GS --> MERGE
    MF --> MERGE
    MERGE --> TOP["Top-K Context Chunks"]
```

| Retrieval mode | Source | Use case |
| --- | --- | --- |
| Semantic | Qdrant | "What is the procedure for pump maintenance?" |
| Graph | Neo4j | "What incidents are linked to P-101?" |
| Metadata | PostgreSQL | "All inspection reports from 2024" |
| Hybrid | All three | "Safety steps for P-101 considering past incidents" |

### Reranking strategy

| Step | Description |
| --- | --- |
| Initial retrieval | Top-K from each source (K=20–50) |
| Deduplication | Remove overlapping chunks |
| Reranking | Cross-encoder or LLM-based relevance scoring |
| Context assembly | Select top-N (N=5–10) within token budget |
| Source tracking | Preserve chunk IDs for citation |

---

## 7. Vector Database

Qdrant serves as TRACE's **vector database**, storing document chunk embeddings and
filterable payloads and providing the full-text index used by hybrid retrieval.

```mermaid
flowchart LR
    subgraph Index["Qdrant Collection"]
        ID["Chunk UUID → Vector mapping"]
        IDX["IVF / HNSW Index Structure"]
    end
    EMB["Embedding Service"] --> ID
    Q["Query Vector"] --> IDX
    IDX --> RES["Similarity Results + Scores"]
    RES --> META["Join with PostgreSQL metadata"]
```

| Property | Design |
| --- | --- |
| Engine | Qdrant |
| Index type | Cosine vector collection plus payload/full-text indexes |
| ID mapping | Chunk UUID (shared with PostgreSQL) |
| Sharding | Partition by document type or facility |
| Persistence | Qdrant volume/cloud collection |
| Updates | Incremental upsert/delete on document ingestion lifecycle |

### Vector-store decision

| Option | Pros | Cons | TRACE choice |
| --- | --- | --- | --- |
| FAISS | Fast, self-hosted, no service | Manual persistence and filtering | Not used |
| pgvector | SQL-native, transactional | Slower at scale | Future option |
| Qdrant | Filtering, keyword indexes, persistent service | Additional service | **Selected** |

---

## 8. Knowledge Graph

The knowledge graph (Neo4j) models **relationships** that vector search alone cannot capture:
which assets reference which procedures, which incidents caused which failures, which
standards govern which equipment.

```mermaid
flowchart LR
    DOC["Document"] -->|REFERENCES| ASSET["Asset P-101"]
    ASSET -->|GOVERNED_BY| SOP["SOP-042"]
    ASSET -->|HAD_INCIDENT| INC["Incident #2024-017"]
    INC -->|CAUSED_BY| FAIL["Bearing Failure"]
    ASSET -->|COMPLIES_WITH| STD["ISO-55000"]
```

| Role | Description |
| --- | --- |
| Relationship traversal | Multi-hop queries across entities |
| Asset-centric views | Aggregate all knowledge for one asset |
| Compliance linking | Connect standards to assets and evidence |
| Reasoning input | Graph context fed to agents alongside vectors |
| Entity disambiguation | Resolve tag/name conflicts via graph |

> Full graph design: see [`11_KNOWLEDGE_GRAPH.md`](11_KNOWLEDGE_GRAPH.md)

---

## 9. Prompt Flow

Every AI interaction follows a structured prompt pipeline — not a free-form chat template.

```mermaid
flowchart TD
    SYS["System Prompt\n(role, constraints, output schema)"]
    CTX["Context Block\n(retrieved chunks + graph facts)"]
    MEM["Memory Block\n(session + asset context)"]
    USR["User Query"]
    SYS --> ASSEMBLE["Prompt Assembly"]
    CTX --> ASSEMBLE
    MEM --> ASSEMBLE
    USR --> ASSEMBLE
    ASSEMBLE --> LLM["LLM Generation"]
    LLM --> PARSE["Parse Structured Output"]
    PARSE --> VERIFY["Grounding Verification"]
    VERIFY --> OUT["Answer + Citations + Confidence"]
```

### Prompt layers

| Layer | Content | Purpose |
| --- | --- | --- |
| System | Role, domain, constraints, output schema | Set behavior boundaries |
| Context | Retrieved chunks with source IDs | Ground the answer |
| Graph facts | Relevant Neo4j triples | Add relational context |
| Memory | Session history, active asset | Maintain continuity |
| User | The actual question | Drive the response |

### System prompt principles

| Rule | Enforcement |
| --- | --- |
| Answer ONLY from provided context | Explicit instruction |
| Cite every factual claim | Output schema requires source IDs |
| Decline if insufficient evidence | Explicit fallback instruction |
| Use industrial terminology | Domain-conditioned language |
| Structured JSON output | Schema-validated response |

---

## 10. Confidence Score

Every answer carries a **confidence score** reflecting how well the retrieved evidence
supports the generated response.

```mermaid
flowchart LR
    RS["Retrieval Scores"] --> CALC["Confidence Calculator"]
    GS["Grounding Check"] --> CALC
    CS["Claim-Source Alignment"] --> CALC
    CALC --> SCORE["Confidence: 0.0 – 1.0"]
    SCORE --> DISPLAY["UI Badge: High / Medium / Low"]
    SCORE --> THRESH{"Below threshold?"}
    THRESH -->|Yes| FLAG["Flag uncertainty / decline"]
    THRESH -->|No| RELEASE["Release answer"]
```

| Factor | Weight | Description |
| --- | --- | --- |
| Retrieval relevance | 40% | Mean similarity score of top chunks |
| Source coverage | 25% | % of answer claims with matching sources |
| Graph support | 15% | Graph facts corroborating the answer |
| Source diversity | 10% | Multiple independent sources vs single |
| Claim specificity | 10% | Specific claims vs vague generalizations |

| Score range | Label | UI treatment |
| --- | --- | --- |
| 0.85 – 1.00 | High | Green badge, full answer |
| 0.60 – 0.84 | Medium | Amber badge, answer with caveat |
| 0.00 – 0.59 | Low | Red badge, decline or "insufficient evidence" |

---

## 11. Memory

TRACE keeps conversation history and extracted long-term memory in PostgreSQL.
Neither Redis nor process memory is a persistent memory store.

```mermaid
flowchart TB
    subgraph Request["Bounded Request Context"]
        CONV["Recent conversation turns"]
        EVIDENCE["Previous citations"]
        SNAP["Latest snapshot"]
    end
    subgraph LongTerm["Long-Term Memory (Persistent)"]
        PG[("PostgreSQL: conversations, messages, snapshots, memories")]
        NEO[("Neo4j: document graph + user-scoped facts")]
        VEC[("Qdrant: document embeddings")]
    end
    subgraph Retrieval["Per-Request Retrieval"]
        RET["Retrieved context buffer"]
        GRAPH["Graph facts"]
    end
    Request --> Retrieval
    LongTerm --> Retrieval
```

| Memory type | Scope | Storage | TTL |
| --- | --- | --- | --- |
| Conversation history | One user and conversation | PostgreSQL | Until explicit conversation deletion |
| Conversation snapshot | One user and conversation turn | PostgreSQL | Cascades with conversation deletion |
| Extracted memory | One user; optionally one source conversation | PostgreSQL | 365 days by default, then expiry and purge |
| User graph facts | One user | Neo4j | Durable user-level context |
| Request context | Query, retrieval results, grounding metadata | Typed service objects | Per request |
| Knowledge memory | All ingested documents | Qdrant + Neo4j + PostgreSQL | Permanent |

### Memory rules

| Rule | Description |
| --- | --- |
| No parametric memory | LLM weights are not the knowledge store |
| Session isolation | Users cannot see other users' sessions |
| History for continuity | Multi-turn questions use prior turns as context |
| Derived cleanup | Deleting a conversation cascades its messages, snapshots, and extracted memories |
| User graph lifetime | Conversation deletion does not remove user-level Neo4j facts; those require explicit user-memory cleanup |
| Bounded long-term retention | Extracted memories expire and a background worker purges inactive rows |

---

## 12. Hallucination Prevention

Hallucination prevention is a **multi-layer defense**, not a single prompt trick.

```mermaid
flowchart TD
    Q["User Query"] --> R["Retrieve Evidence"]
    R -->|No results| DECLINE["Decline: insufficient evidence"]
    R -->|Results found| GEN["Generate from context ONLY"]
    GEN --> VERIFY["Self-Verify Claims"]
    VERIFY -->|Unverified claim| REVISE["Revise or remove claim"]
    VERIFY -->|All verified| CITE["Attach Citations"]
    CITE --> CONF["Compute Confidence"]
    CONF -->|Below threshold| DECLINE
    CONF -->|Above threshold| RELEASE["Release Answer"]
```

| Layer | Mechanism |
| --- | --- |
| **Retrieval-first** | No generation without retrieved context |
| **Context-only prompt** | System prompt forbids external knowledge |
| **Structured output** | JSON schema requires source IDs per claim |
| **Self-verification** | Agent checks each claim against sources |
| **Confidence gating** | Low-confidence answers are blocked |
| **Citation requirement** | Every factual statement must cite a chunk |
| **Decline protocol** | Explicit "I don't have sufficient evidence" response |
| **Human feedback loop** | Thumbs down triggers review and re-indexing |
| **Audit trail** | Full retrieval + generation log for post-hoc review |

### Decline response template

When evidence is insufficient, TRACE responds with:

> "I don't have sufficient evidence in the ingested documents to answer this question
> confidently. Here is what I found that may be related: [partial results with citations].
> Consider uploading additional documents or refining your query."

This is fundamentally different from ChatGPT, which would generate a plausible-sounding
but unverified answer.

---

## 13. References

- [`03_SYSTEM_ARCHITECTURE.md`](03_SYSTEM_ARCHITECTURE.md)
- [`09_AGENT_ARCHITECTURE.md`](09_AGENT_ARCHITECTURE.md)
- [`10_RAG_PIPELINE.md`](10_RAG_PIPELINE.md)
- [`11_KNOWLEDGE_GRAPH.md`](11_KNOWLEDGE_GRAPH.md)
- [`12_DOCUMENT_PIPELINE.md`](12_DOCUMENT_PIPELINE.md)
- Lewis, P. et al. *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*, NeurIPS 2020.
- LangChain — https://python.langchain.com/
- Sentence Transformers — https://www.sbert.net/
- Qdrant — https://qdrant.tech/documentation/
- Neo4j — https://neo4j.com/docs/
