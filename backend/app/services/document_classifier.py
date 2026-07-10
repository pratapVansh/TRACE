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
    equipment_ids: list[str]


FILENAME_CATEGORY_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"^SOP[-_]", re.IGNORECASE), "Operations", "SOP"),
    (re.compile(r"^MAN[-_]", re.IGNORECASE), "Maintenance", "OEM Manual"),
    (re.compile(r"^MNT[-_]", re.IGNORECASE), "Maintenance", "Maintenance Report"),
    (re.compile(r"^INS[-_]", re.IGNORECASE), "Inspection", "Inspection Report"),
    (re.compile(r"^INC[-_]", re.IGNORECASE), "HSE", "Incident Report"),
    (re.compile(r"^LOG[-_]", re.IGNORECASE), "Operations", "Shift Log"),
    (re.compile(r"^SCN[-_]", re.IGNORECASE), "Safety", "Safety"),
    (re.compile(r"^PPT[-_]", re.IGNORECASE), "Training", "Presentation"),
    (re.compile(r"^Equipment_Register", re.IGNORECASE), "Engineering", "Spreadsheet"),
    (re.compile(r"^Maintenance_Schedule", re.IGNORECASE), "Maintenance", "Spreadsheet"),
    (re.compile(r"^Spare_Parts", re.IGNORECASE), "Stores", "Spreadsheet"),
]


CONTENT_CATEGORY_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"standard\s*operating\s*proced", re.IGNORECASE), "Operations", "SOP"),
    (re.compile(r"\bOEM\s+Manual\b", re.IGNORECASE), "Maintenance", "OEM Manual"),
    (re.compile(r"operator.{0,20}manual", re.IGNORECASE), "Maintenance", "OEM Manual"),
    (re.compile(r"preventive\s+maintenance", re.IGNORECASE), "Maintenance", "Maintenance Report"),
    (re.compile(r"bearing\s+replacement", re.IGNORECASE), "Maintenance", "Maintenance Report"),
    (re.compile(r"seal\s+leakage", re.IGNORECASE), "Maintenance", "Maintenance Report"),
    (re.compile(r"\bmaintenance\b.{0,30}report", re.IGNORECASE), "Maintenance", "Maintenance Report"),
    (re.compile(r"inspection\s+report", re.IGNORECASE), "Inspection", "Inspection Report"),
    (re.compile(r"vibration\s+analysis", re.IGNORECASE), "Inspection", "Inspection Report"),
    (re.compile(r"pressure\s+vessel\s+inspection", re.IGNORECASE), "Inspection", "Inspection Report"),
    (re.compile(r"boiler\s+inspection", re.IGNORECASE), "Inspection", "Inspection Report"),
    (re.compile(r"\bincident\b.{0,30}report", re.IGNORECASE), "HSE", "Incident Report"),
    (re.compile(r"root\s+cause", re.IGNORECASE), "HSE", "Incident Report"),
    (re.compile(r"corrective\s+action", re.IGNORECASE), "Maintenance", "Maintenance Report"),
    (re.compile(r"shift\s+log", re.IGNORECASE), "Operations", "Shift Log"),
    (re.compile(r"handover\s+notes", re.IGNORECASE), "Operations", "Shift Log"),
    (re.compile(r"safety\s+inspection", re.IGNORECASE), "Safety", "Safety"),
    (re.compile(r"confined\s+space", re.IGNORECASE), "Safety", "Safety"),
    (re.compile(r"\bPPE\b", re.IGNORECASE), "Safety", "Safety"),
    (re.compile(r"near.miss", re.IGNORECASE), "HSE", "Incident Report"),
    (re.compile(r"\bp[&\s]?id\b.*cooling", re.IGNORECASE), "Engineering", "P&ID"),
    (re.compile(r"equipment\s+register", re.IGNORECASE), "Engineering", "Spreadsheet"),
    (re.compile(r"maintenance\s+schedule", re.IGNORECASE), "Maintenance", "Spreadsheet"),
    (re.compile(r"spare\s+parts", re.IGNORECASE), "Stores", "Spreadsheet"),
    (re.compile(r"maintenance\s+schedule", re.IGNORECASE), "Maintenance", "Spreadsheet"),
    (re.compile(r"equipment\s+register", re.IGNORECASE), "Engineering", "Spreadsheet"),
    (re.compile(r"safety\s+training", re.IGNORECASE), "Safety", "Presentation"),
    (re.compile(r"plant\s+overview", re.IGNORECASE), "Management", "Presentation"),
]


EXTENSION_CATEGORY: dict[str, tuple[str, str]] = {
    "xlsx": ("General", "Spreadsheet"),
    "pptx": ("General", "Presentation"),
    "pdf": ("General", "General"),
    "docx": ("General", "General"),
    "txt": ("General", "General"),
}


def classify_document(
    filename: str,
    content_text: str | None = None,
) -> DocumentClassification:
    department = "General"
    category = "General"
    equipment_ids: list[str] = []

    found_via_filename = False
    for pattern, dept, cat in FILENAME_CATEGORY_PATTERNS:
        if pattern.search(filename):
            department = dept
            category = cat
            found_via_filename = True
            break

    if content_text and not found_via_filename:
        for pattern, dept, cat in CONTENT_CATEGORY_PATTERNS:
            if pattern.search(content_text):
                department = dept
                category = cat
                break

    if not found_via_filename and not content_text:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext in EXTENSION_CATEGORY:
            department, category = EXTENSION_CATEGORY[ext]

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
        equipment_ids=equipment_ids,
    )
