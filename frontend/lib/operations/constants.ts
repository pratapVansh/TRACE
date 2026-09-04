// The audit action vocabulary, taken from every `action="…"` passed to
// AuditService.log() in backend/app/services/. Adding a new audit call site
// means adding its action here, or it will be unreachable from the filter.
export const AUDIT_ACTIONS = [
  "login",
  "logout",
  "failed_login",
  "token_refreshed",
  "user_registered",
  "user_created",
  "user_role_assigned",
  "user_status_updated",
  "user_password_reset",
  "document_uploaded",
  "document_viewed",
  "document_updated",
  "document_downloaded",
  "document_deleted",
  "ocr_processing_started",
  "ocr_processing_finished",
  "processing_retry_scheduled",
] as const;

export const AUDIT_ACTION_LABELS: Record<string, string> = {
  login: "Login",
  logout: "Logout",
  failed_login: "Failed login",
  token_refreshed: "Token refreshed",
  user_registered: "User registered",
  user_created: "User created",
  user_role_assigned: "Role assigned",
  user_status_updated: "Status updated",
  user_password_reset: "Password reset",
  document_uploaded: "Document uploaded",
  document_viewed: "Document viewed",
  document_updated: "Document updated",
  document_downloaded: "Document downloaded",
  document_deleted: "Document deleted",
  ocr_processing_started: "OCR started",
  ocr_processing_finished: "OCR finished",
  processing_retry_scheduled: "Retry scheduled",
};

export const AUDIT_ACTION_FILTER_OPTIONS = [
  { value: "all", label: "All actions" },
  ...AUDIT_ACTIONS.map((action) => ({
    value: action,
    label: AUDIT_ACTION_LABELS[action] ?? action,
  })),
];

export const AUDIT_LOG_DEFAULT_FILTERS = {
  action: "all",
  dateFrom: "",
  dateTo: "",
};

export type AuditLogFilterValues = typeof AUDIT_LOG_DEFAULT_FILTERS;
