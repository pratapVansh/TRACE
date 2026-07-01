import type { RoleDefinition, SettingsSectionData } from "@/types/administration";
import { ROLE_DESCRIPTIONS } from "@/lib/administration/constants";

export const ROLE_DEFINITIONS: RoleDefinition[] = [
  { role: "Admin", description: ROLE_DESCRIPTIONS.Admin, userCount: 1 },
  { role: "Engineer", description: ROLE_DESCRIPTIONS.Engineer, userCount: 5 },
  { role: "Operator", description: ROLE_DESCRIPTIONS.Operator, userCount: 2 },
  { role: "Viewer", description: ROLE_DESCRIPTIONS.Viewer, userCount: 2 },
];

export const SYSTEM_SETTINGS: SettingsSectionData[] = [
  {
    id: "company",
    title: "Company",
    description: "Organization profile and facility configuration.",
    fields: [
      { id: "org-name", label: "Organization name", value: "Northfield Refinery Complex", type: "text" },
      { id: "facility-id", label: "Facility ID", value: "NFR-001-IN", type: "text" },
      { id: "timezone", label: "Timezone", value: "Asia/Kolkata (IST)", type: "select", options: ["Asia/Kolkata (IST)", "UTC"] },
      { id: "locale", label: "Locale", value: "English (India)", type: "select", options: ["English (India)", "English (US)"] },
    ],
  },
  {
    id: "security",
    title: "Security",
    description: "Authentication policies and session controls.",
    fields: [
      { id: "mfa", label: "Require MFA for Admin roles", value: "", type: "toggle", enabled: true },
      { id: "session-timeout", label: "Session timeout", value: "60 minutes", type: "select", options: ["30 minutes", "60 minutes", "120 minutes"] },
      { id: "password-policy", label: "Password policy", value: "Enterprise (min 8 chars, bcrypt)", type: "text" },
      { id: "ip-allowlist", label: "IP allowlist", value: "Disabled", type: "toggle", enabled: false },
    ],
  },
  {
    id: "notifications",
    title: "Notifications",
    description: "Alert delivery and escalation preferences.",
    fields: [
      { id: "email-alerts", label: "Email alerts", value: "", type: "toggle", enabled: true },
      { id: "compliance-deadlines", label: "Compliance deadline reminders", value: "", type: "toggle", enabled: true },
      { id: "maintenance-overdue", label: "Overdue maintenance alerts", value: "", type: "toggle", enabled: true },
      { id: "digest", label: "Daily digest time", value: "07:00 IST", type: "select", options: ["07:00 IST", "08:00 IST", "09:00 IST"] },
    ],
  },
  {
    id: "ai",
    title: "AI",
    description: "Copilot, RAG, and agent configuration defaults.",
    fields: [
      { id: "copilot-enabled", label: "Copilot enabled", value: "", type: "toggle", enabled: true },
      { id: "embedding-model", label: "Embedding model", value: "sentence-transformers/all-MiniLM-L6-v2", type: "text" },
      { id: "max-tokens", label: "Max response tokens", value: "4096", type: "text" },
      { id: "citation-required", label: "Require citations in responses", value: "", type: "toggle", enabled: true },
    ],
  },
  {
    id: "database",
    title: "Database",
    description: "Connected data stores and ingestion pipeline status.",
    fields: [
      { id: "postgres", label: "PostgreSQL", value: "Connected — trace@localhost:5432", type: "text" },
      { id: "neo4j", label: "Neo4j (Knowledge Graph)", value: "Not configured", type: "text" },
      { id: "faiss", label: "FAISS vector index", value: "Not configured", type: "text" },
      { id: "backup", label: "Automated backups", value: "", type: "toggle", enabled: false },
    ],
  },
  {
    id: "appearance",
    title: "Appearance",
    description: "UI theme and display preferences.",
    fields: [
      { id: "theme", label: "Theme", value: "Industrial Dark (default)", type: "select", options: ["Industrial Dark (default)", "Industrial Light"] },
      { id: "density", label: "Table density", value: "Comfortable", type: "select", options: ["Compact", "Comfortable", "Spacious"] },
      { id: "sidebar", label: "Collapsed sidebar by default", value: "", type: "toggle", enabled: false },
    ],
  },
];
