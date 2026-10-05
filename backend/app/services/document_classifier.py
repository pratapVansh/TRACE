"""Automatic document classification and metadata inference."""

import re
from typing import NamedTuple

EQUIPMENT_PATTERN = re.compile(
    r"\b(?:P|V|B|C|T|E|M|L|CT|FC|TK|PU|CP|HT|CL|DR|FN|HV|SW|PSV|PI|FI|LIC|XV|FY|TY|PDT|FCV|PCV|MOV|SDV|BD|SP|AG|CL)\s*-?\s*\d{2,4}\b",
    re.IGNORECASE,
)


class DocumentClassification(NamedTuple):
    department: str
    category: str
    document_type: str
    equipment_ids: list[str]


FILENAME_CATEGORY_PATTERNS: list[tuple[re.Pattern, str, str, str]] = [
    (re.compile(r"^SOP[-_]", re.IGNORECASE), "Operations", "SOP", "sop"),
    (re.compile(r"^MAN[-_]", re.IGNORECASE), "Maintenance", "OEM Manual", "manual"),
    (re.compile(r"^MNT[-_]", re.IGNORECASE), "Maintenance", "Maintenance Report", "maintenance_log"),
    (re.compile(r"^INS[-_]", re.IGNORECASE), "Inspection", "Inspection Report", "inspection_report"),
    (re.compile(r"^INC[-_]", re.IGNORECASE), "HSE", "Incident Report", "incident_report"),
    (re.compile(r"^LOG[-_]", re.IGNORECASE), "Operations", "Shift Log", "maintenance_log"),
    (re.compile(r"^SCN[-_]", re.IGNORECASE), "Safety", "Safety", "safety_manual"),
    (re.compile(r"^PPT[-_]", re.IGNORECASE), "Training", "Presentation", "presentation"),
    (re.compile(r"(?:resume|curriculum[ _-]*vitae|\bcv\b)", re.IGNORECASE), "General", "Resume", "resume"),
    (re.compile(r"^Equipment_Register", re.IGNORECASE), "Engineering", "Spreadsheet", "spreadsheet"),
    (re.compile(r"^Maintenance_Schedule", re.IGNORECASE), "Maintenance", "Spreadsheet", "spreadsheet"),
    (re.compile(r"^Spare_Parts", re.IGNORECASE), "Stores", "Spreadsheet", "spreadsheet"),
]


CONTENT_CATEGORY_PATTERNS: list[tuple[re.Pattern, str, str, str]] = [
    (re.compile(r"standard\s*operating\s*proced", re.IGNORECASE), "Operations", "SOP", "sop"),
    (re.compile(r"\bOEM\s+Manual\b|operator.{0,20}manual", re.IGNORECASE), "Maintenance", "OEM Manual", "manual"),
    (re.compile(r"preventive\s+maintenance|bearing\s+replacement|seal\s+leakage|\bmaintenance\b.{0,30}report|corrective\s+action", re.IGNORECASE), "Maintenance", "Maintenance Report", "maintenance_log"),
    (re.compile(r"inspection\s+report|vibration\s+analysis|pressure\s+vessel\s+inspection|boiler\s+inspection", re.IGNORECASE), "Inspection", "Inspection Report", "inspection_report"),
    (re.compile(r"\bincident\b.{0,30}report|root\s+cause|near.miss", re.IGNORECASE), "HSE", "Incident Report", "incident_report"),
    (re.compile(r"shift\s+log|handover\s+notes", re.IGNORECASE), "Operations", "Shift Log", "maintenance_log"),
    (re.compile(r"safety\s+inspection|confined\s+space|\bPPE\b", re.IGNORECASE), "Safety", "Safety", "safety_manual"),
    (re.compile(r"\bp[&\s]?id\b.*cooling", re.IGNORECASE), "Engineering", "P&ID", "engineering_drawing"),
    (re.compile(r"equipment\s+register|maintenance\s+schedule|spare\s+parts", re.IGNORECASE), "General", "Spreadsheet", "spreadsheet"),
    (re.compile(r"safety\s+training|plant\s+overview", re.IGNORECASE), "General", "Presentation", "presentation"),
    (re.compile(r"\b(?:education|academic)\b[\s\S]{0,1500}\b(?:experience|projects?)\b", re.IGNORECASE), "General", "Resume", "resume"),
]


EXTENSION_CATEGORY: dict[str, tuple[str, str, str]] = {
    "xlsx": ("General", "Spreadsheet", "spreadsheet"),
    "pptx": ("General", "Presentation", "presentation"),
    "pdf": ("General", "General", "document"),
    "docx": ("General", "General", "document"),
    "txt": ("General", "General", "document"),
    "png": ("General", "Image", "image"),
    "jpg": ("General", "Image", "image"),
    "jpeg": ("General", "Image", "image"),
}


def classify_document(
    filename: str,
    content_text: str | None = None,
) -> DocumentClassification:
    department = "General"
    category = "General"
    document_type = "document"
    equipment_ids: list[str] = []

    found_via_filename = False
    for pattern, dept, cat, semantic_type in FILENAME_CATEGORY_PATTERNS:
        if pattern.search(filename):
            department = dept
            category = cat
            document_type = semantic_type
            found_via_filename = True
            break

    if content_text and not found_via_filename:
        for pattern, dept, cat, semantic_type in CONTENT_CATEGORY_PATTERNS:
            if pattern.search(content_text):
                department = dept
                category = cat
                document_type = semantic_type
                break

    if not found_via_filename and not content_text:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext in EXTENSION_CATEGORY:
            department, category, document_type = EXTENSION_CATEGORY[ext]

    if content_text:
        found_ids = EQUIPMENT_PATTERN.findall(content_text)
        seen: set[str] = set()
        for eid in found_ids:
            normalized = eid.strip().upper().replace(" ", "")
            if normalized not in seen:
                seen.add(normalized)
                equipment_ids.append(normalized)

    if not equipment_ids and filename:
        found_ids = EQUIPMENT_PATTERN.findall(filename)
        seen = set()
        for eid in found_ids:
            normalized = eid.strip().upper().replace(" ", "")
            if normalized not in seen:
                seen.add(normalized)
                equipment_ids.append(normalized)

    return DocumentClassification(
        department=department,
        category=category,
        document_type=document_type,
        equipment_ids=equipment_ids,
    )
