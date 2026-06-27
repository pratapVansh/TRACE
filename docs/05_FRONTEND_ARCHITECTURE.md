# TRACE — Frontend Architecture

### Technical Records & Asset Compliance Engine · Problem Statement 8

---

## Table of Contents

1. [Overview](#1-overview)
2. [Folder Structure](#2-folder-structure)
3. [Pages](#3-pages)
4. [Components](#4-components)
5. [Layouts](#5-layouts)
6. [Authentication Flow](#6-authentication-flow)
7. [Dashboard](#7-dashboard)
8. [Asset Details](#8-asset-details)
9. [AI Copilot](#9-ai-copilot)
10. [Knowledge Graph](#10-knowledge-graph)
11. [Maintenance](#11-maintenance)
12. [Compliance](#12-compliance)
13. [Responsive Strategy](#13-responsive-strategy)
14. [References](#14-references)

---

## 1. Overview

The frontend is a **Next.js (App Router) + TypeScript** application styled with
**TailwindCSS** and built from **shadcn/ui** primitives. It delivers an enterprise Copilot
experience: conversational AI, semantic search, asset intelligence, knowledge-graph
exploration, maintenance, and compliance views.

| Concern | Approach |
| --- | --- |
| Rendering | Server Components for data-heavy pages; Client Components for interactivity |
| Data fetching | Server-side fetch + React Query (client cache) |
| Streaming | Server-Sent Events for Copilot token streaming |
| State | Local component state + lightweight global store (auth, theme) |
| Styling | Tailwind tokens + shadcn/ui + glassmorphism accents |
| Type safety | TypeScript end-to-end with shared API types |

```mermaid
flowchart LR
    Browser --> Next["Next.js App Router"]
    Next -->|RSC fetch| API["FastAPI"]
    Next -->|SSE| API
    Next --> RQ["React Query Cache"]
    Next --> UILIB["shadcn/ui + Tailwind"]
```

---

## 2. Folder Structure

```text
frontend/
├── app/                          # App Router
│   ├── (auth)/
│   │   ├── login/page.tsx
│   │   └── layout.tsx
│   ├── (dashboard)/
│   │   ├── layout.tsx            # Authenticated shell
│   │   ├── page.tsx              # Dashboard home
│   │   ├── copilot/page.tsx
│   │   ├── search/page.tsx
│   │   ├── assets/
│   │   │   ├── page.tsx          # Asset list
│   │   │   └── [assetId]/page.tsx
│   │   ├── graph/page.tsx
│   │   ├── maintenance/page.tsx
│   │   ├── compliance/page.tsx
│   │   ├── documents/page.tsx
│   │   └── admin/page.tsx
│   ├── layout.tsx                # Root layout (providers, theme)
│   └── globals.css
├── components/
│   ├── ui/                       # shadcn/ui primitives
│   ├── copilot/                  # Chat, message, citation
│   ├── assets/                   # Asset cards, tables
│   ├── graph/                    # Graph canvas, node panels
│   ├── charts/                   # Chart wrappers
│   ├── layout/                   # Sidebar, topbar, breadcrumbs
│   └── common/                   # Buttons, badges, empty states
├── lib/
│   ├── api/                      # Typed API client
│   ├── auth/                     # Session helpers, guards
│   ├── hooks/                    # React Query hooks
│   └── utils/                    # Formatters, helpers
├── stores/                       # Global state (auth, theme, ui)
├── types/                        # Shared TypeScript types
├── styles/                       # Tailwind config extensions
└── public/                       # Static assets
```

| Directory | Responsibility |
| --- | --- |
| `app/` | Routes, layouts, route groups |
| `components/ui/` | Generated shadcn/ui primitives |
| `components/*` | Feature components |
| `lib/api/` | Typed fetch client and API bindings |
| `lib/hooks/` | Data hooks (React Query) |
| `stores/` | Cross-cutting client state |
| `types/` | Shared DTO/types mirroring backend |

---

## 3. Pages

| Route | Page | Purpose | Rendering |
| --- | --- | --- | --- |
| `/login` | Login | Authentication | Client |
| `/` | Dashboard | KPIs, recent activity, quick ask | Server + Client |
| `/copilot` | Copilot | Conversational AI assistant | Client (SSE) |
| `/search` | Search | Semantic search results | Server + Client |
| `/assets` | Asset List | Browse/filter assets | Server |
| `/assets/[assetId]` | Asset Details | Full asset intelligence | Server + Client |
| `/graph` | Knowledge Graph | Interactive graph exploration | Client |
| `/maintenance` | Maintenance | Maintenance records & schedule | Server |
| `/compliance` | Compliance | Compliance status & evidence | Server |
| `/documents` | Documents | Upload & ingestion status | Client |
| `/admin` | Admin | Users, roles, ingestion control | Server + Client |

```mermaid
flowchart TD
    Login --> Dash["Dashboard"]
    Dash --> Copilot
    Dash --> Search
    Dash --> Assets
    Assets --> AssetDetails["Asset Details"]
    AssetDetails --> Graph
    AssetDetails --> Maintenance
    AssetDetails --> Compliance
    Dash --> Documents
    Dash --> Admin
```

---

## 4. Components

| Category | Components |
| --- | --- |
| Copilot | `ChatWindow`, `MessageBubble`, `CitationCard`, `SourceDrawer`, `PromptInput`, `StreamingIndicator` |
| Assets | `AssetCard`, `AssetTable`, `AssetHeader`, `AssetTimeline`, `TagBadge` |
| Graph | `GraphCanvas`, `NodeDetailsPanel`, `GraphLegend`, `GraphFilters` |
| Charts | `KpiCard`, `TrendChart`, `StatusDonut`, `BarChart` |
| Layout | `Sidebar`, `TopBar`, `Breadcrumbs`, `CommandPalette`, `ThemeToggle` |
| Common | `DataTable`, `EmptyState`, `LoadingSkeleton`, `ConfirmDialog`, `Toast` |

### Component composition example (Copilot)

```mermaid
flowchart TB
    ChatWindow --> PromptInput
    ChatWindow --> MessageList
    MessageList --> MessageBubble
    MessageBubble --> CitationCard
    CitationCard --> SourceDrawer
    ChatWindow --> StreamingIndicator
```

---

## 5. Layouts

| Layout | Used By | Contents |
| --- | --- | --- |
| Root Layout | All routes | Providers (theme, query, auth), fonts, global CSS |
| Auth Layout | `/login` | Minimal centered card, branding |
| Dashboard Layout | Authenticated routes | Sidebar, top bar, breadcrumbs, content slot |

```mermaid
flowchart LR
    Root["Root Layout"] --> Auth["Auth Layout"]
    Root --> Dashboard["Dashboard Layout"]
    Dashboard --> SB["Sidebar"]
    Dashboard --> TB["Top Bar"]
    Dashboard --> Content["Page Content"]
```

---

## 6. Authentication Flow

```mermaid
sequenceDiagram
    actor User
    participant FE as Next.js
    participant API as FastAPI
    User->>FE: Enter credentials
    FE->>API: POST /auth/login
    API-->>FE: Access + refresh tokens
    FE->>FE: Store session (httpOnly cookie)
    User->>FE: Navigate to protected route
    FE->>FE: Middleware checks session
    alt Valid
        FE-->>User: Render page
    else Expired
        FE->>API: POST /auth/refresh
        API-->>FE: New access token
    end
```

| Aspect | Approach |
| --- | --- |
| Token storage | httpOnly secure cookies |
| Route protection | Next.js middleware + server-side guards |
| Role gating | Conditional rendering by role claims |
| Refresh | Silent token refresh on expiry |
| Logout | Clear cookies, invalidate session |

---

## 7. Dashboard

The dashboard is the operational landing surface: KPIs, recent activity, quick Copilot
access, and alerts.

```mermaid
flowchart TB
    subgraph Dashboard
        KPI["KPI Cards - Assets, Docs, Open Compliance, Incidents"]
        QA["Quick Ask Copilot"]
        ACT["Recent Activity Feed"]
        ALERT["Compliance & Safety Alerts"]
        TREND["Trend Charts"]
    end
```

| Widget | Content |
| --- | --- |
| KPI Cards | Total assets, documents ingested, open compliance items, recent incidents |
| Quick Ask | Inline Copilot prompt |
| Activity Feed | Recent uploads, queries, status changes |
| Alerts | Overdue compliance, critical incidents |
| Trends | Ingestion volume, query volume over time |

---

## 8. Asset Details

```mermaid
flowchart TB
    Header["Asset Header - Tag, Type, Status, Location"]
    Tabs{"Tabs"}
    Header --> Tabs
    Tabs --> Overview
    Tabs --> Docs["Linked Documents"]
    Tabs --> Maint["Maintenance History"]
    Tabs --> Insp["Inspections"]
    Tabs --> Inc["Incidents"]
    Tabs --> Comp["Compliance"]
    Tabs --> GraphView["Graph Neighborhood"]
```

| Section | Content |
| --- | --- |
| Header | Tag, name, type, status badge, location |
| Overview | Summary, key metadata, AI-generated synopsis |
| Linked Documents | All documents referencing the asset, with citations |
| Maintenance | Chronological maintenance records |
| Inspections | Inspection results and findings |
| Incidents | Incident history with severity |
| Compliance | Applicable standards and status |
| Graph Neighborhood | Connected assets, procedures, incidents |

---

## 9. AI Copilot

```mermaid
flowchart LR
    Input["Prompt Input"] --> Send
    Send --> Stream["SSE Token Stream"]
    Stream --> Bubble["Assistant Message"]
    Bubble --> Cites["Citation Cards"]
    Cites --> Drawer["Source Drawer - opens document at page"]
    Bubble --> FB["Feedback (up/down)"]
```

| Capability | Behavior |
| --- | --- |
| Streaming | Tokens render incrementally via SSE |
| Citations | Inline citation chips linking to sources |
| Source drawer | Opens the cited document at the referenced page |
| Multi-turn | Maintains conversation context |
| Suggestions | Context-aware follow-up prompts |
| Feedback | Thumbs up/down captured for metrics |

---

## 10. Knowledge Graph

```mermaid
flowchart TB
    Canvas["Graph Canvas"] --> Nodes["Nodes: Assets, Docs, Incidents, Standards"]
    Canvas --> Edges["Edges: references, governs, caused_by"]
    Canvas --> Filters["Filters by type/relation"]
    Nodes --> Panel["Node Details Panel"]
    Panel --> Jump["Jump to Asset / Document"]
```

| Feature | Description |
| --- | --- |
| Interactive canvas | Pan, zoom, expand/collapse nodes |
| Node types | Assets, documents, incidents, standards, procedures |
| Edge types | references, governs, caused_by, complies_with |
| Filtering | By node type, relation, or asset |
| Details panel | Metadata and quick navigation |

---

## 11. Maintenance

```mermaid
flowchart LR
    Filters["Filter by asset / date / technician"] --> Table["Maintenance Table"]
    Table --> Detail["Record Detail"]
    Detail --> Source["Source Document"]
    Table --> Schedule["Upcoming Schedule View"]
```

| Element | Content |
| --- | --- |
| Maintenance table | Asset, date, description, technician, source |
| Filters | Asset, date range, technician |
| Record detail | Full description with source citation |
| Schedule view | Upcoming/overdue maintenance |

---

## 12. Compliance

```mermaid
flowchart TB
    Overview["Compliance Overview - status donut"] --> Items["Compliance Items Table"]
    Items --> Status["Status: compliant / non-compliant / pending"]
    Items --> Evidence["Evidence Document"]
    Items --> Standard["Linked Standard"]
```

| Element | Content |
| --- | --- |
| Overview | Donut of compliant vs non-compliant vs pending |
| Items table | Standard, asset, requirement, status, due date |
| Evidence | Link to evidencing document |
| Filters | By standard, asset, status |

---

## 13. Responsive Strategy

| Breakpoint | Target | Layout Behavior |
| --- | --- | --- |
| `sm` (<640px) | Phones | Single column, collapsible sidebar drawer, bottom nav |
| `md` (≥768px) | Tablets | Two-column, icon sidebar |
| `lg` (≥1024px) | Laptops | Full sidebar, multi-column dashboard |
| `xl` (≥1280px) | Desktops | Expanded grids, side-by-side panels |
| `2xl` (≥1536px) | Large displays | Wide content, persistent panels |

```mermaid
flowchart LR
    Mobile["Mobile: Drawer + Bottom Nav"] --> Tablet["Tablet: Icon Sidebar"]
    Tablet --> Desktop["Desktop: Full Sidebar + Grid"]
    Desktop --> Wide["Wide: Multi-panel"]
```

| Principle | Approach |
| --- | --- |
| Mobile-first | Tailwind utilities scale up from base |
| Fluid grids | CSS grid/flex with responsive columns |
| Adaptive nav | Sidebar collapses to drawer on small screens |
| Touch targets | Minimum 44px interactive areas |
| Performance | Lazy-load heavy views (graph, charts) |

---

## 14. References

- [`03_SYSTEM_ARCHITECTURE.md`](03_SYSTEM_ARCHITECTURE.md)
- [`06_BACKEND_ARCHITECTURE.md`](06_BACKEND_ARCHITECTURE.md)
- [`07_UI_UX_DESIGN.md`](07_UI_UX_DESIGN.md)
- Next.js App Router — https://nextjs.org/docs/app
- shadcn/ui — https://ui.shadcn.com/
- TailwindCSS — https://tailwindcss.com/docs
- TanStack Query — https://tanstack.com/query
