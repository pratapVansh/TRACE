import re

from app.extraction.types import EntityType

# ── Shared chemical list (M21 — single source of truth) ───────────────
CHEMICAL_NAMES = (
    r"hydrochloric\s+acid|sulfuric\s+acid|nitric\s+acid|phosphoric\s+acid"
    r"|acetic\s+acid|hydrofluoric\s+acid"
    r"|sodium\s+hydroxide|potassium\s+hydroxide|calcium\s+hydroxide"
    r"|ammonia|chlorine|hydrogen|oxygen|nitrogen"
    r"|methane|ethane|propane|butane|ethylene|propylene"
    r"|benzene|toluene|xylene|methanol|ethanol|acetone|phenol"
    r"|caustic\s+soda|soda\s+ash|sodium\s+hypochlorite|hydrogen\s+peroxide"
    r"|natural\s+gas|carbon\s+dioxide|carbon\s+monoxide"
    r"|hydrogen\s+sulfide|sulfur\s+dioxide|sulfur\s+trioxide"
    r"|sulfuric|nitric|phosphoric"
)

CHEMICAL_FORMULAS = (
    r"HCl|H2SO4|HNO3|H3PO4|NaOH|KOH|NH3|Cl2|H2|O2|N2"
    r"|CH4|C2H6|C3H8|C4H10|C2H4|C3H6"
    r"|C6H6|C7H8|C8H10|CH3OH|C2H5OH"
    r"|CO2|CO|H2S|SO2|SO3|NaCl|NaOCl|H2O2|CaOH"
)

CHEMICAL = rf"(?:{CHEMICAL_NAMES}|{CHEMICAL_FORMULAS})"

# ── Equipment tag: P-101, V-202, TK-305, E-410, M-101, FT-201 ──────
EQUIPMENT_TAG = re.compile(
    r"\b(?P<tag>(?:[A-Z]{2,4}\s*[-–—/]\s*\d{2,6}"
    r"|[A-Z]{1,4}\s*\d{3,6}"
    r"|[A-Z]\s*[-–—/]\s*\d{3,6}"
    r"|[A-Z]{2,3}\d{2,6}"
    r"))\b",
    re.IGNORECASE,
)

# H8 + H23: prefix → type mapping (longest prefix first)
_TAG_PREFIX_ENTRIES: list[tuple[str, EntityType, float]] = [
    # Instrument — 3-char
    ("FIC", EntityType.INSTRUMENT, 0.95),
    ("PIC", EntityType.INSTRUMENT, 0.95),
    ("LIC", EntityType.INSTRUMENT, 0.95),
    ("TIC", EntityType.INSTRUMENT, 0.95),
    ("PCV", EntityType.VALVE, 0.95),
    ("PSV", EntityType.VALVE, 0.95),
    ("BDV", EntityType.VALVE, 0.90),
    ("PDT", EntityType.INSTRUMENT, 0.90),
    ("FDT", EntityType.INSTRUMENT, 0.90),
    ("FCV", EntityType.VALVE, 0.90),
    ("LCV", EntityType.VALVE, 0.90),
    ("HCV", EntityType.VALVE, 0.85),
    # Instrument — 2-char
    ("FT", EntityType.INSTRUMENT, 0.95),
    ("PT", EntityType.INSTRUMENT, 0.95),
    ("LT", EntityType.INSTRUMENT, 0.95),
    ("TT", EntityType.INSTRUMENT, 0.95),
    ("FV", EntityType.VALVE, 0.95),
    ("PV", EntityType.VALVE, 0.95),
    ("XV", EntityType.VALVE, 0.95),
    ("HV", EntityType.VALVE, 0.90),
    ("PI", EntityType.INSTRUMENT, 0.90),
    ("FI", EntityType.INSTRUMENT, 0.90),
    ("LI", EntityType.INSTRUMENT, 0.90),
    ("TI", EntityType.INSTRUMENT, 0.90),
    ("PD", EntityType.INSTRUMENT, 0.85),
    ("FD", EntityType.INSTRUMENT, 0.85),
    ("PL", EntityType.PIPELINE, 0.90),
    # Valves — 2-char (additional)
    ("TCV", EntityType.VALVE, 0.85),
    # Equipment — 2-char
    ("TK", EntityType.TANK, 0.95),
    ("HX", EntityType.HEAT_EXCHANGER, 0.90),
    # Procedure — 2-char
    ("WI", EntityType.PROCEDURE, 0.85),
    # Equipment — 1-char
    ("P", EntityType.PUMP, 0.95),
    ("V", EntityType.VALVE, 0.95),
    ("T", EntityType.TANK, 0.85),
    ("E", EntityType.HEAT_EXCHANGER, 0.95),
    ("M", EntityType.MOTOR, 0.95),
    ("L", EntityType.PIPELINE, 0.85),
    ("C", EntityType.COMPRESSOR, 0.95),
    # 3-char procedure
    ("SOP", EntityType.PROCEDURE, 0.90),
]

# Sorted by prefix length descending (longest match first)
_TAG_PREFIX_ENTRIES.sort(key=lambda x: len(x[0]), reverse=True)

TAG_PREFIX_TYPE: dict[str, EntityType] = {p: t for p, t, _ in _TAG_PREFIX_ENTRIES}
TAG_PREFIX_CONFIDENCE: dict[str, float] = {p: c for p, _, c in _TAG_PREFIX_ENTRIES}


# ── Named entity patterns (high confidence) ──────────────────────────
NAMED_PATTERNS: list[tuple[re.Pattern[str], EntityType, float]] = [
    # Pump
    (re.compile(
        r"\b(?:centrifugal|positive\s+displacement|diaphragm|gear|screw|peristaltic|submersible|booster|vacuum|reciprocating|axial\s+flow|mixed\s+flow)"
        r"\s+pump\b", re.IGNORECASE,
    ), EntityType.PUMP, 0.90),
    (re.compile(
        r"\bpump\s+([A-Z]{1,3}\s*[-–—/]?\s*\d{2,6})\b", re.IGNORECASE,
    ), EntityType.PUMP, 0.85),
    # Valve
    (re.compile(
        r"\b(gate|globe|ball|butterfly|check|plug|needle|pinch|diaphragm|safety|relief|control"
        r"|pressure\s+reducing|pressure\s+safety|isolation|shut[- ]off|swing|double\s+block[- ]+bleed)"
        r"\s+valve\b", re.IGNORECASE,
    ), EntityType.VALVE, 0.90),
    # Pipeline (M23)
    (re.compile(
        r"\b(?:pipeline|pipe)\s+(?:line\s+)?([A-Z]{1,3}\s*[-–—/]?\s*\d{2,6})\b", re.IGNORECASE,
    ), EntityType.PIPELINE, 0.85),
    (re.compile(
        r"\bpipeline\s+\d{3,6}\b", re.IGNORECASE,
    ), EntityType.PIPELINE, 0.75),
    (re.compile(
        r"\b(?:pipe\s+)?spool\s+\d{3,6}\b", re.IGNORECASE,
    ), EntityType.PIPELINE, 0.70),
    # Tank
    (re.compile(
        r"\b(storage|buffer|surge|day|feed|product|atmospheric|pressurized|cryogenic|settling|mixing)"
        r"\s+tank\b", re.IGNORECASE,
    ), EntityType.TANK, 0.85),
    # Instrument (M23 — expanded)
    (re.compile(
        r"\b(transmitter|pressure\s+gauge|temperature\s+gauge|level\s+indicator|flow\s+indicator"
        r"|controller|sensor|switch|analyzer|transducer|detector|gauge)"
        r"\s+([A-Z]{1,3}\s*[-–—/]?\s*\d{2,6})\b", re.IGNORECASE,
    ), EntityType.INSTRUMENT, 0.85),
    # Motor
    (re.compile(
        r"\b(electric\s+motor|induction\s+motor|synchronous\s+motor|dc\s+motor"
        r"|variable\s+frequency\s+drive|vfd|servo\s+motor|stepper\s+motor)"
        r"(?:\s+[A-Z]?\d*)?\b", re.IGNORECASE,
    ), EntityType.MOTOR, 0.85),
    # Heat Exchanger
    (re.compile(
        r"\b(shell\s+(and|&)\s+tube|plate|double\s+pipe|air\s+cooled|spiral)"
        r"\s+heat\s+exchanger\b", re.IGNORECASE,
    ), EntityType.HEAT_EXCHANGER, 0.90),
    (re.compile(
        r"\b(condenser|reboiler|chiller|cooler|heater|furnace|boiler|steam\s+generator"
        r"|heat\s+exchanger)\b", re.IGNORECASE,
    ), EntityType.HEAT_EXCHANGER, 0.80),
    # Column / Reactor (M20)
    (re.compile(
        r"\b(distillation|fractionation|absorption|stripping|extraction)\s+column\b",
        re.IGNORECASE,
    ), EntityType.UNIT, 0.85),
    (re.compile(
        r"\b(reactor|vessel|column|tower)\s+([A-Z]{1,3}\s*[-–—/]?\s*\d{2,6})\b",
        re.IGNORECASE,
    ), EntityType.UNIT, 0.80),
    # Unit
    (re.compile(
        r"\b(?:unit|area|section|train)\s+\d{1,3}\b", re.IGNORECASE,
    ), EntityType.UNIT, 0.70),
    (re.compile(
        r"\b(production|processing|separation|distillation|reactor|fractionation"
        r"|treatment|compression)\s+unit\b", re.IGNORECASE,
    ), EntityType.UNIT, 0.85),
    # Procedure
    (re.compile(
        r"\bSOP[-–—]?\d+|WI[-–—]?\d+\b", re.IGNORECASE,
    ), EntityType.PROCEDURE, 0.90),
    (re.compile(
        r"\b(?:work\s+instruction|operating\s+procedure|maintenance\s+procedure"
        r"|start[-–—]?up\s+procedure|standard\s+operating\s+procedure)"
        r"(?:\s+[A-Z]?\d[-/\w]*)?\b", re.IGNORECASE,
    ), EntityType.PROCEDURE, 0.75),
    # Standard
    (re.compile(
        r"\bAPI\s+(?:spec\s+)?\d{2,4}[A-Z]?\b", re.IGNORECASE,
    ), EntityType.STANDARD, 0.95),
    (re.compile(
        r"\bISO\s+\d{4,6}(?:[-–—]\d{1,4})?\b", re.IGNORECASE,
    ), EntityType.STANDARD, 0.95),
    (re.compile(
        r"\bASME\s+[A-Z]+\d*\.?\d*[A-Z]?\b", re.IGNORECASE,
    ), EntityType.STANDARD, 0.95),
    (re.compile(
        r"\bASTM\s+[A-Z]\d{2,4}\b", re.IGNORECASE,
    ), EntityType.STANDARD, 0.95),
    (re.compile(
        r"\bNACE\s+(?:MR|TM|SP|RP)\d{3}\b", re.IGNORECASE,
    ), EntityType.STANDARD, 0.95),
    (re.compile(
        r"\bANSI\s+[A-Z]+\d*\.?\d*\b", re.IGNORECASE,
    ), EntityType.STANDARD, 0.90),
    (re.compile(
        r"\bIEC\s+\d{2,5}\b", re.IGNORECASE,
    ), EntityType.STANDARD, 0.90),
    # Chemical (M21 — uses shared constant)
    (re.compile(
        rf"\b({CHEMICAL_NAMES}|{CHEMICAL_FORMULAS})\b", re.IGNORECASE,
    ), EntityType.CHEMICAL, 0.90),
    (re.compile(
        rf"\b({CHEMICAL_FORMULAS})\b",
    ), EntityType.CHEMICAL, 0.85),
    # Compressor
    (re.compile(
        r"\b(centrifugal|reciprocating|screw|axial|scroll|rotary\s+screw"
        r"|centrifugal\s+gas|gas\s+turbine-driven|motor-driven)\s+compressor\b",
        re.IGNORECASE,
    ), EntityType.COMPRESSOR, 0.90),
    (re.compile(
        r"\bcompressor\s+([A-Z]{1,3}\s*[-–—/]?\s*\d{2,6})\b", re.IGNORECASE,
    ), EntityType.COMPRESSOR, 0.85),
    # Failure
    (re.compile(
        r"\b(oil\s+leakage|bearing\s+failure|cavitation|impeller\s+damage"
        r"|seal\s+failure|mechanical\s+seal\s+failure|shaft\s+misalignment"
        r"|coupling\s+failure|corrosion|erosion|overheating|excessive\s+vibration"
        r"|misalignment|thermal\s+fatigue|stress\s+corrosion\s+cracking"
        r"|fatigue\s+failure|creep|rupture|burst|leakage|fouling|scaling"
        r"|blockage|plugging|wear|pitting|spalling|abrasion|cracking"
        r"|weld\s+failure|gasket\s+failure|packing\s+failure|valve\s+failure"
        r"|pump\s+failure|motor\s+failure|compressor\s+failure|instrument\s+failure"
        r"|control\s+system\s+failure|power\s+failure|electrical\s+failure"
        r"|sensor\s+failure|actuator\s+failure)\b", re.IGNORECASE,
    ), EntityType.FAILURE, 0.90),
    (re.compile(
        r"\b(failure|fault|malfunction|breakdown|degradation|anomaly|defect)"
        r"\s+(?:mode\s+)?(?:of|in|on|at)\s+"
        r"(?:the\s+)?([A-Z]{1,3}\s*[-–—/]?\s*\d{2,6})\b", re.IGNORECASE,
    ), EntityType.FAILURE, 0.85),
    # Cause
    (re.compile(
        r"\b(fatigue|wear|corrosion|erosion|overpressure|thermal\s+shock"
        r"|misalignment|improper\s+lubrication|contamination|improper\s+installation"
        r"|lack\s+of\s+maintenance|ageing|aging|manufacturing\s+defect"
        r"|material\s+defect|design\s+flaw|operational\s+error|human\s+error"
        r"|electrical\s+surge|lightning\s+strike|water\s+hammer|slugging"
        r"|surge|flooding|dry\s+run|overload|overheating|freezing"
        r"|vibration|pulsation|resonance|cavitation|erosion)\b", re.IGNORECASE,
    ), EntityType.CAUSE, 0.85),
    # Operator
    (re.compile(
        r"\b(operator|technician|plant\s+operator|process\s+operator"
        r"|maintenance\s+technician|shift\s+supervisor|shift\s+lead"
        r"|area\s+operator|control\s+room\s+operator|board\s+operator"
        r"|field\s+operator|relief\s+operator|senior\s+operator"
        r"|process\s+engineer|maintenance\s+engineer|safety\s+officer"
        r"|plant\s+manager|operations\s+manager|maintenance\s+manager"
        r"|instrument\s+technician|electrical\s+technician|mechanical\s+technician)\b",
        re.IGNORECASE,
    ), EntityType.OPERATOR, 0.85),
    # Location
    (re.compile(
        r"\b(?:area|zone|sector|bay)\s+[A-Z]\d*\b", re.IGNORECASE,
    ), EntityType.LOCATION, 0.65),
    (re.compile(
        r"\b(?:control\s+room|workshop|lab(oratory)?|warehouse|terminal|platform|depot)"
        r"\s+[A-Z]?[\w\s]{1,20}?\b", re.IGNORECASE,
    ), EntityType.LOCATION, 0.60),
    # Document reference
    (re.compile(
        r"\b(?:doc|document|drawing|spec|specification|data\s+sheet"
        r"|report|manual|guideline)"
        r"\s+[-–]?\s*[A-Z]?\d[-–/.\w]{2,40}\b", re.IGNORECASE,
    ), EntityType.DOCUMENT, 0.50),
]

# ── Context patterns (low confidence) ─────────────────────────────────
CONTEXT_PATTERNS: list[tuple[re.Pattern[str], EntityType, float]] = [
    (re.compile(
        r"\b(pump|centrifugal)\s+(?:is|was|has|with|rated|designed|operating|located|installed|used)\b",
        re.IGNORECASE,
    ), EntityType.PUMP, 0.30),
    (re.compile(
        r"\bvalve\s+(?:is|was|has|with|rated|located|installed|used|opens|closes|controls)\b",
        re.IGNORECASE,
    ), EntityType.VALVE, 0.30),
    (re.compile(
        r"\btank\s+(?:is|was|has|with|rated|designed|holds|contains|stores)\b",
        re.IGNORECASE,
    ), EntityType.TANK, 0.30),
    (re.compile(
        r"\bmotor\s+(?:is|was|has|with|rated|drives|operates)\b",
        re.IGNORECASE,
    ), EntityType.MOTOR, 0.30),
    # M20: pipeline context
    (re.compile(
        r"\b(pipeline|pipe|piping)\s+(?:is|was|has|runs|carries|transports|connects)\b",
        re.IGNORECASE,
    ), EntityType.PIPELINE, 0.30),
    # M20: instrument context
    (re.compile(
        r"\b(transmitter|gauge|indicator|controller|sensor|switch)\s+(?:is|was|has|reads|measures|indicates|controls)\b",
        re.IGNORECASE,
    ), EntityType.INSTRUMENT, 0.30),
    # M20: column / reactor context
    (re.compile(
        r"\b(column|tower|reactor|vessel)\s+(?:is|was|has|operates|runs|processes)\b",
        re.IGNORECASE,
    ), EntityType.UNIT, 0.30),
    # Compressor context
    (re.compile(
        r"\bcompressor\s+(?:is|was|has|operates|runs|delivers|discharges|compresses)\b",
        re.IGNORECASE,
    ), EntityType.COMPRESSOR, 0.35),
    # Failure context
    (re.compile(
        r"\b(?:failure|fault|leak|leakage|breakdown|malfunction)\s+"
        r"(?:occurred|happened|detected|observed|reported|found|noticed|caused|led|resulted|identified)\b",
        re.IGNORECASE,
    ), EntityType.FAILURE, 0.40),
    (re.compile(
        r"\b(?:had|experienced|suffered|developed|exhibited|showed)\s+"
        r"(?:a\s+)?(?:failure|fault|leak|leakage|breakdown|malfunction|problem|issue)\b",
        re.IGNORECASE,
    ), EntityType.FAILURE, 0.35),
    # Cause context
    (re.compile(
        r"\b(?:cause|causes|caused|causing)\s+(?:of|by|is|was|were|the)\b",
        re.IGNORECASE,
    ), EntityType.CAUSE, 0.30),
    (re.compile(
        r"\b(?:due\s+to|result\s+of|resulting\s+from|attributed\s+to|"
        r"stemming\s+from|because\s+of|as\s+a\s+result\s+of)\b",
        re.IGNORECASE,
    ), EntityType.CAUSE, 0.35),
    # Operator context
    (re.compile(
        r"\b(?:operator|technician|engineer)\s+(?:shall|must|should|will|may|can|"
        r"is\s+responsible|performs|conducts|carries\s+out|executes)\b",
        re.IGNORECASE,
    ), EntityType.OPERATOR, 0.35),
]
