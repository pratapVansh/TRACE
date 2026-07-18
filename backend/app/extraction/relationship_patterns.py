import re

from app.extraction.patterns import CHEMICAL
from app.extraction.relationship import RelationshipType

_TAG = r"[A-Z]{1,3}\s*[-–—/]?\s*\d{2,6}"
_FAILURE = (
    r"(?:oil\s+leakage|bearing\s+failure|cavitation|impeller\s+damage"
    r"|seal\s+failure|mechanical\s+seal\s+failure|shaft\s+misalignment"
    r"|coupling\s+failure|corrosion|erosion|overheating|excessive\s+vibration"
    r"|misalignment|thermal\s+fatigue|stress\s+corrosion\s+cracking"
    r"|fatigue\s+failure|creep|rupture|burst|leakage|fouling|scaling"
    r"|blockage|plugging|wear|pitting|spalling|abrasion|cracking"
    r"|weld\s+failure|gasket\s+failure|packing\s+failure|valve\s+failure"
    r"|pump\s+failure|motor\s+failure|compressor\s+failure|instrument\s+failure"
    r"|control\s+system\s+failure|power\s+failure|electrical\s+failure"
    r"|sensor\s+failure|actuator\s+failure|failure|fault|malfunction|"
    r"breakdown|degradation|anomaly|defect)"
)
_CAUSE = (
    r"(?:fatigue|wear|corrosion|erosion|overpressure|thermal\s+shock"
    r"|misalignment|improper\s+lubrication|contamination|improper\s+installation"
    r"|lack\s+of\s+maintenance|ageing|aging|manufacturing\s+defect"
    r"|material\s+defect|design\s+flaw|operational\s+error|human\s+error"
    r"|electrical\s+surge|lightning\s+strike|water\s+hammer|slugging"
    r"|surge|flooding|dry\s+run|overload|overheating|freezing"
    r"|vibration|pulsation|resonance|cavitation|erosion)"
)
_OPERATOR = (
    r"(?:operator|technician|plant\s+operator|process\s+operator"
    r"|maintenance\s+technician|shift\s+supervisor|shift\s+lead"
    r"|area\s+operator|control\s+room\s+operator|board\s+operator"
    r"|field\s+operator|relief\s+operator|senior\s+operator"
    r"|process\s+engineer|maintenance\s+engineer|safety\s+officer"
    r"|plant\s+manager|operations\s+manager|maintenance\s+manager"
    r"|instrument\s+technician|electrical\s+technician|mechanical\s+technician)"
)

_PUMP = (
    r"(?:centrifugal|positive\s+displacement|diaphragm|gear|screw|"
    r"peristaltic|submersible|booster|vacuum|reciprocating|"
    r"axial\s+flow|mixed\s+flow)\s+pumps?"
)
_VALVE = (
    r"(?:gate|globe|ball|butterfly|check|plug|needle|pinch|diaphragm|"
    r"safety|relief|control|pressure\s+reducing|pressure\s+safety|"
    r"isolation|shut[- ]off|swing|double\s+block[- ]+bleed)\s+valves?"
)
_TANK = (
    r"(?:storage|buffer|surge|day|feed|product|atmospheric|"
    r"pressurized|cryogenic|settling|mixing)\s+tanks?"
)
_HX = (
    r"(?:shell\s+(?:and|&)\s+tube|plate|double\s+pipe|"
    r"air\s+cooled|spiral)\s+heat\s+exchangers?"
)
_MOTOR = (
    r"(?:electric\s+motor|induction\s+motor|synchronous\s+motor|"
    r"dc\s+motor|variable\s+frequency\s+drive|vfd|"
    r"servo\s+motor|stepper\s+motor)s?"
)
_UNIT = r"(?:unit|area|section|train)\s+\d{1,3}"
_LOCATION = r"(?:area|zone|sector|bay)\s+(?:[A-Z]\d*|\d+)"
_STANDARD = r"(?:API|ASME|ASTM|ISO|ANSI|NACE|IEC)\s+[A-Z]?\d+(?:[-–—]\d+)?[A-Z]?"
_SOP_PROC = r"(?:SOP\s*[-–—]?\s*\d+|WI\s*[-–—]?\s*\d+)"
_PIPELINE = r"(?:pipeline|pipe\s+line|piping)\s+(?:line\s+)?[A-Z]{0,3}\d{2,6}"
_INSTRUMENT = (
    r"(?:transmitter|pressure\s+gauge|temperature\s+gauge|level\s+indicator|"
    r"flow\s+indicator|controller|sensor|switch|analyzer|transducer|detector|gauge)"
)

_COMPRESSOR = (
    r"(?:centrifugal|reciprocating|screw|axial|scroll|rotary\s+screw"
    r"|centrifugal\s+gas|gas\s+turbine-driven|motor-driven)\s+compressor"
)
_NAMED_EQUIP = rf"(?:{_PUMP}|{_VALVE}|{_TANK}|{_HX}|{_MOTOR}|{_COMPRESSOR})"


def _p(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE)


RELATIONSHIP_PATTERNS: list[tuple[re.Pattern, RelationshipType, float]] = [
    # ═══════════════════════════════════════════════════════
    # CONNECTED_TO
    # ═══════════════════════════════════════════════════════
    (
        _p(
            rf"\b(?P<src>{_TAG}|{_PIPELINE})\s+(?:is\s+|was\s+|are\s+|were\s+)?"
            r"(?:connected|tied|linked|attached|joined)\s+(?:to|with)\s+"
            rf"(?P<tgt>{_TAG}|{_PIPELINE})\b"
        ),
        RelationshipType.CONNECTED_TO,
        0.95,
    ),
    (
        _p(
            rf"(?:connection|link|tie-in)\s+(?:between|from)\s+"
            rf"(?P<src>{_TAG}|{_PIPELINE})\s+(?:and|to)\s+(?P<tgt>{_TAG}|{_PIPELINE})\b"
        ),
        RelationshipType.CONNECTED_TO,
        0.90,
    ),
    (
        _p(
            rf"\b(?P<src>{_TAG}|{_PIPELINE})\s+is\s+"
            r"(?:upstream|downstream|immediately\s+(?:upstream|downstream))\s+of\s+"
            rf"(?P<tgt>{_TAG}|{_PIPELINE})\b"
        ),
        RelationshipType.CONNECTED_TO,
        0.85,
    ),
    (
        _p(
            rf"\b(?P<src>{_TAG}|{_PIPELINE})\s+(?:connects?|ties?|links?)\s+(?:to|with)\s+"
            rf"(?P<tgt>{_TAG}|{_PIPELINE})\b"
        ),
        RelationshipType.CONNECTED_TO,
        0.85,
    ),
    (
        _p(
            rf"\b(?P<src>{_TAG}|{_PIPELINE})\s+(?:and|,)\s+"
            rf"(?P<tgt>{_TAG}|{_PIPELINE})\s+(?:are|were|both)\s+connected\b"
        ),
        RelationshipType.CONNECTED_TO,
        0.80,
    ),
    # ═══════════════════════════════════════════════════════
    # PART_OF
    # ═══════════════════════════════════════════════════════
    (
        _p(
            rf"\b(?P<src>{_TAG}|{_NAMED_EQUIP}|{_PIPELINE})\s+(?:is\s+|was\s+)?"
            r"(?:part|component|member|element)\s+of\s+(?:the\s+)?"
            rf"(?P<tgt>{_UNIT}|{_LOCATION}|{_NAMED_EQUIP}|{_TAG}|{_PIPELINE})\b"
        ),
        RelationshipType.PART_OF,
        0.90,
    ),
    (
        _p(
            rf"\b(?P<src>{_TAG}|{_NAMED_EQUIP}|{_PIPELINE})\s+"
            r"(?:belongs?|belong|assigned)\s+to\s+(?:the\s+)?"
            rf"(?P<tgt>{_TAG}|{_NAMED_EQUIP}|{_UNIT}|{_LOCATION}|{_PIPELINE}|"
            r".+(?:system|unit|area|section|train|assembly|package))\b"
        ),
        RelationshipType.PART_OF,
        0.85,
    ),
    (
        _p(
            rf"\b(?P<src>{_TAG}|{_PIPELINE})\s+(?:is\s+|was\s+)?"
            r"(?:installed|placed|situated|mounted)\s+in\s+(?:the\s+)?"
            rf"(?P<tgt>{_UNIT}|{_LOCATION})\b"
        ),
        RelationshipType.PART_OF,
        0.75,
    ),
    # ═══════════════════════════════════════════════════════
    # LOCATED_IN
    # ═══════════════════════════════════════════════════════
    (
        _p(
            rf"\b(?P<src>{_TAG}|{_NAMED_EQUIP}|{_PIPELINE}|{_INSTRUMENT})\s+"
            r"(?:is\s+|was\s+|are\s+)?"
            r"(?:located|situated|positioned|placed|installed|found)\s+"
            r"(?:in|at|on|within)\s+(?:the\s+)?"
            rf"(?P<tgt>{_LOCATION}|{_UNIT})\b"
        ),
        RelationshipType.LOCATED_IN,
        0.90,
    ),
    (
        _p(
            rf"\b(?P<src>{_TAG}|{_PIPELINE})\s+(?:is\s+|was\s+)?in\s+(?:the\s+)?"
            rf"(?P<tgt>{_LOCATION}|{_UNIT})\b"
        ),
        RelationshipType.LOCATED_IN,
        0.75,
    ),
    # ═══════════════════════════════════════════════════════
    # HAS_PROCEDURE
    # ═══════════════════════════════════════════════════════
    (
        _p(
            rf"\b(?P<src>{_SOP_PROC})\s+"
            r"(?:covers|describes|documents|defines|specifies|addresses|"
            r"provides|outlines|details)\s+"
            r"(?:the\s+)?(?:maintenance|operation|installation|inspection|"
            r"repair|testing|calibration)\s*"
            r"(?:of\s+|for\s+)?"
            rf"(?:the\s+)?(?P<tgt>{_TAG}|{_NAMED_EQUIP}|{_PIPELINE}|{_INSTRUMENT})\b"
        ),
        RelationshipType.HAS_PROCEDURE,
        0.90,
    ),
    (
        _p(
            rf"\b(?:follow|use|refer\s+to|consult|see)\s+"
            rf"(?P<src>{_SOP_PROC})\s+"
            r"(?:for|to|when\s+(?:working|servicing|operating)\s+on)\s+"
            rf"(?:the\s+)?(?P<tgt>{_TAG}|{_NAMED_EQUIP}|{_PIPELINE}|{_INSTRUMENT})\b"
        ),
        RelationshipType.HAS_PROCEDURE,
        0.85,
    ),
    # ═══════════════════════════════════════════════════════
    # MAINTAINED_BY (M22 fix)
    # ═══════════════════════════════════════════════════════
    (
        _p(
            rf"\b(?P<src>{_TAG}|{_NAMED_EQUIP}|{_PIPELINE}|{_INSTRUMENT})\s+"
            r"(?:is\s+|are\s+|was\s+|were\s+)?"
            r"(?:maintained|serviced|inspected|checked|calibrated|"
            r"overhauled|repaired|tested|cleaned)\s+"
            r"by\s+"
            rf"(?P<tgt>[A-Z][\w\s'-]{{2,60}}?)"
            r"(?=[.?!;]|\s+(?:per|according|on|every|monthly|yearly|weekly|daily|annually|"
            r"using|with|at|in|by|for|as|\n)|$)"
        ),
        RelationshipType.MAINTAINED_BY,
        0.85,
    ),
    # ═══════════════════════════════════════════════════════
    # USES
    # ═══════════════════════════════════════════════════════
    (
        _p(
            rf"\b(?P<src>{_TAG}|{_NAMED_EQUIP}|{_UNIT}|{_PIPELINE}|{_INSTRUMENT})\s+"
            r"(?:uses?|utilizes?|consumes?|requires?|handles?|"
            r"processes?|pumps?|transfers?|circulates?)\s+"
            rf"(?:the\s+)?(?P<tgt>{CHEMICAL})\b"
        ),
        RelationshipType.USES,
        0.85,
    ),
    (
        _p(
            rf"\b(?P<src>{CHEMICAL})\s+(?:is\s+|was\s+|are\s+)?"
            r"(?:used|handled|stored|processed|consumed|injected|fed|pumped)\s+"
            r"(?:in|at|to|into|by|through)\s+"
            rf"(?:the\s+)?(?P<tgt>{_TAG}|{_NAMED_EQUIP}|{_UNIT}|{_PIPELINE}|{_INSTRUMENT})\b"
        ),
        RelationshipType.USES,
        0.80,
    ),
    # ═══════════════════════════════════════════════════════
    # REFERENCES
    # ═══════════════════════════════════════════════════════
    (
        _p(
            rf"\b(?P<src>{_STANDARD})\s+"
            r"(?:covers|defines|specifies|applies\s+to|is\s+applicable\s+to|"
            r"governs|addresses)\s+"
            r"(?:the\s+)?(?:design|fabrication|construction|testing|"
            r"inspection|maintenance)?\s*"
            r"(?:of\s+|for\s+)?"
            rf"(?:the\s+)?(?P<tgt>{_TAG}|{_NAMED_EQUIP}|{_PIPELINE}|{_INSTRUMENT})\b"
        ),
        RelationshipType.REFERENCES,
        0.85,
    ),
    (
        _p(
            rf"\b(?P<src>{_TAG}|{_NAMED_EQUIP}|{_PIPELINE}|{_INSTRUMENT})\s+"
            r"(?:refers?\s+to|references?|is\s+based\s+on|"
            r"is\s+designed\s+(?:per|to))\s+"
            rf"(?P<tgt>{_STANDARD}|{_SOP_PROC})\b"
        ),
        RelationshipType.REFERENCES,
        0.80,
    ),
    (
        _p(
            rf"\b(?:per|according\s+to|in\s+accordance\s+with|as\s+per)\s+"
            rf"(?P<src>{_STANDARD})\s*"
            r"(?:,\s+)?(?:section|table|figure|clause|paragraph|appendix)?\s*"
            r"(?:for|applicable\s+to|governing|pertaining\s+to)\s+"
            rf"(?:the\s+)?(?P<tgt>{_TAG}|{_NAMED_EQUIP}|{_PIPELINE}|{_INSTRUMENT})\b"
        ),
        RelationshipType.REFERENCES,
        0.75,
    ),
    # ═══════════════════════════════════════════════════════
    # DEPENDS_ON
    # ═══════════════════════════════════════════════════════
    (
        _p(
            rf"\b(?P<src>{_TAG}|{_NAMED_EQUIP}|{_UNIT}|{_PIPELINE}|{_INSTRUMENT})\s+"
            r"(?:is\s+)?"
            r"(?:depends?|reliant|contingent|conditional)\s+(?:on|upon)\s+"
            rf"(?:the\s+)?(?P<tgt>{_TAG}|{_NAMED_EQUIP}|{_PIPELINE}|{CHEMICAL})\b"
        ),
        RelationshipType.DEPENDS_ON,
        0.80,
    ),
    (
        _p(
            rf"\b(?P<src>{_TAG}|{_NAMED_EQUIP}|{_UNIT}|{_PIPELINE}|{_INSTRUMENT})\s+"
            r"(?:is\s+)?"
            r"(?:depends?|dependent|reliant|contingent|conditional)\s+(?:on|upon)\s+"
            r"(?:the\s+)?"
            rf"(?P<tgt>cooling\s+water|cooling\s+system|steam\s+supply|"
            r"power\s+supply|instrument\s+air|nitrogen\s+supply|"
            r"service\s+water|feed\s+supply)\b"
        ),
        RelationshipType.DEPENDS_ON,
        0.75,
    ),
    (
        _p(
            rf"\b(?P<src>{_TAG}|{_NAMED_EQUIP}|{_PIPELINE}|{_INSTRUMENT})\s+"
            r"(?:requires?|needs?|must\s+have)\s+"
            rf"(?:the\s+)?"
            r"(?P<tgt>{CHEMICAL}|cooling\s+water|steam|"
            r"power\s+supply|electricity|instrument\s+air|nitrogen)\b"
        ),
        RelationshipType.DEPENDS_ON,
        0.75,
    ),
    (
        _p(
            rf"\b(?P<src>{_TAG})\s+(?:is\s+|was\s+)?"
            r"(?:dependent|reliant|based)\s+(?:on|upon)\s+"
            rf"(?P<tgt>{_TAG})\b"
        ),
        RelationshipType.DEPENDS_ON,
        0.85,
    ),
    # ═══════════════════════════════════════════════════════
    # INPUT_TO
    # ═══════════════════════════════════════════════════════
    (
        _p(
            rf"\b(?P<src>{_TAG}|{_PIPELINE})\s+"
            r"(?:feeds?|supplies?|provides?|delivers?|sends?|transfers?)\s+"
            r"(?:\w+\s+)?(?:to|into)\s+"
            rf"(?:the\s+)?(?P<tgt>{_TAG}|{_PIPELINE})\b"
        ),
        RelationshipType.INPUT_TO,
        0.90,
    ),
    (
        _p(
            rf"\b(?P<src>{_TAG}|{_PIPELINE})\s+"
            r"(?:feeds?|supplies?)\s+"
            rf"(?P<tgt>{_TAG}|{_PIPELINE})\b"
        ),
        RelationshipType.INPUT_TO,
        0.75,
    ),
    (
        _p(
            rf"\b(?:feed|inlet|supply|input)\s+(?:from|to)\s+"
            rf"(?P<src>{_TAG}|{_PIPELINE})(?:\s+and\s+{_TAG}|{_PIPELINE})?\s+"
            r"(?:goes?|flows?|enters?|passes?|"
            r"is\s+sent|is\s+supplied|is\s+fed|is\s+directed)\s+"
            r"(?:\w+\s+)?(?:to|into)\s+"
            rf"(?:the\s+)?(?P<tgt>{_TAG}|{_PIPELINE})\b"
        ),
        RelationshipType.INPUT_TO,
        0.85,
    ),
    (
        _p(
            rf"\b(?:flow|stream|product|process\s+fluid)\s+(?:from|of)\s+"
            rf"(?P<src>{_TAG}|{_PIPELINE})\s+"
            r"(?:goes?|flows?|enters?|passes?|"
            r"is\s+directed|is\s+fed|is\s+routed)\s+"
            r"(?:\w+\s+)?(?:to|into)\s+"
            rf"(?:the\s+)?(?P<tgt>{_TAG}|{_PIPELINE})\b"
        ),
        RelationshipType.INPUT_TO,
        0.85,
    ),
    (
        _p(
            rf"\b(?P<src>{_TAG}|{_PIPELINE})\s+"
            r"(?:is\s+)?connected\s+to\s+the\s+"
            r"(?:inlet|suction)\s+(?:of|side\s+of|nozzle\s+of)\s+"
            rf"(?P<tgt>{_TAG}|{_PIPELINE})\b"
        ),
        RelationshipType.INPUT_TO,
        0.80,
    ),
    # ═══════════════════════════════════════════════════════
    # OUTPUT_TO
    # ═══════════════════════════════════════════════════════
    (
        _p(
            rf"\b(?P<src>{_TAG}|{_PIPELINE})\s+"
            r"(?:discharges?|drains?|exhausts?|vents?|"
            r"blows?\s+down|purges?|releases?|emits?)\s+"
            r"(?:\w+\s+)?(?:to|into|from|via)\s+"
            rf"(?:the\s+)?(?P<tgt>{_TAG}|{_PIPELINE})\b"
        ),
        RelationshipType.OUTPUT_TO,
        0.90,
    ),
    (
        _p(
            rf"\b(?:discharge|outlet|exhaust|drain|blowdown|vent)\s+"
            r"(?:from|of|line|side|port)\s+"
            rf"(?P<src>{_TAG}|{_PIPELINE})\s+"
            r"(?:goes?|flows?|passes?|is\s+directed|"
            r"is\s+sent|is\s+routed|is\s+discharged)\s+"
            r"(?:\w+\s+)?(?:to|into)\s+"
            rf"(?:the\s+)?(?P<tgt>{_TAG}|{_PIPELINE})\b"
        ),
        RelationshipType.OUTPUT_TO,
        0.85,
    ),
    (
        _p(
            rf"\b(?:drain|vent|blowdown|purge)\s+"
            rf"(?P<src>{_TAG}|{_PIPELINE})\s+(?:to|into|from)\s+"
            rf"(?:the\s+)?(?P<tgt>{_TAG}|{_PIPELINE}|"
            r"(?:sump|flare|atmosphere|drain|sewer|slop|blowdown|vent)\s*(?:system|drum|pot|tank|header)?)\b"
        ),
        RelationshipType.OUTPUT_TO,
        0.80,
    ),
    (
        _p(
            rf"\b(?P<src>{_TAG}|{_PIPELINE})\s+"
            r"(?:is\s+)?connected\s+to\s+the\s+"
            r"(?:outlet|discharge)\s+(?:of|side\s+of|nozzle\s+of)\s+"
            rf"(?P<tgt>{_TAG}|{_PIPELINE})\b"
        ),
        RelationshipType.OUTPUT_TO,
        0.80,
    ),
    # ═══════════════════════════════════════════════════════
    # HAS_FAILURE
    # ═══════════════════════════════════════════════════════
    (
        _p(
            rf"\b(?P<src>{_TAG}|{_NAMED_EQUIP})\s+"
            r"(?:experienced?|suffered?|developed?|exhibited?|had|showed?|"
            r"reported?|encountered?|presented\s+with)\s+"
            r"(?:a\s+|an\s+|the\s+)?"
            rf"(?P<tgt>{_FAILURE})\b"
        ),
        RelationshipType.HAS_FAILURE,
        0.90,
    ),
    (
        _p(
            rf"\b(?P<src>{_FAILURE})\s+"
            r"(?:occurred|happened|developed|manifested|appeared)\s+"
            r"(?:on|in|at|for)\s+"
            r"(?:the\s+)?"
            rf"(?P<tgt>{_TAG}|{_NAMED_EQUIP})\b"
        ),
        RelationshipType.HAS_FAILURE,
        0.85,
    ),
    (
        _p(
            rf"\b(?P<src>{_TAG}|{_NAMED_EQUIP})\s+(?:has|with|having)\s+"
            r"(?:a\s+|an\s+)?"
            rf"(?P<tgt>{_FAILURE})\b"
        ),
        RelationshipType.HAS_FAILURE,
        0.80,
    ),
    # ═══════════════════════════════════════════════════════
    # CAUSED_BY
    # ═══════════════════════════════════════════════════════
    (
        _p(
            rf"\b(?P<src>{_FAILURE})\s+"
            r"(?:was\s+|were\s+|is\s+|are\s+)?"
            r"(?:caused\s+by|due\s+to|resulting?\s+from|attributed\s+to|"
            r"stemming?\s+from|triggered\s+by|induced\s+by|originating?\s+from)\s+"
            rf"(?P<tgt>{_CAUSE}|{_FAILURE}|{_TAG})\b"
        ),
        RelationshipType.CAUSED_BY,
        0.90,
    ),
    (
        _p(
            rf"\b(?P<src>{_CAUSE})\s+"
            r"(?:caused?|led\s+to|resulted?\s+in|triggered?|induced?|"
            r"produced?|created?|generated?)\s+"
            r"(?:a\s+|an\s+|the\s+)?"
            rf"(?P<tgt>{_FAILURE})\b"
        ),
        RelationshipType.CAUSED_BY,
        0.85,
    ),
    (
        _p(
            rf"\b(?:(?P<src>{_FAILURE})\s+(?:due|attributable|owing)\s+to\s+"
            rf"(?P<tgt>{_CAUSE}|{_TAG})\b)"
        ),
        RelationshipType.CAUSED_BY,
        0.80,
    ),
    # ═══════════════════════════════════════════════════════
    # PERFORMED_BY
    # ═══════════════════════════════════════════════════════
    (
        _p(
            rf"\b(?:(?:the\s+)?(?:maintenance|inspection|repair|service|check|"
            r"calibration|test|operation|installation|overhaul)\s+"
            r"(?:of|on|for|performed|carried\s+out|conducted|executed)\s+"
            r"(?:the\s+)?"
            rf"{_TAG}|{_NAMED_EQUIP}|{_PIPELINE}|{_INSTRUMENT})\s+"
            r"(?:was\s+|were\s+|is\s+|are\s+|shall\s+be\s+|will\s+be\s+)?"
            r"(?:performed\s+by|carried\s+out\s+by|conducted\s+by|done\s+by|"
            r"executed\s+by|completed\s+by)\s+"
            rf"(?P<tgt>{_OPERATOR})\b"
        ),
        RelationshipType.PERFORMED_BY,
        0.85,
    ),
    (
        _p(
            rf"\b(?P<src>{_OPERATOR})\s+"
            r"(?:performs?|carries?\s+out|conducts?|executes?|"
            r"completes?|performed|carried\s+out|conducted|executed)\s+"
            r"(?:the\s+)?(?:maintenance|inspection|repair|service|check|"
            r"calibration|test|operation|installation|overhaul)\s+"
            r"(?:of|on|for)\s+"
            r"(?:the\s+)?"
            rf"(?P<tgt>{_TAG}|{_NAMED_EQUIP}|{_PIPELINE}|{_INSTRUMENT})\b"
        ),
        RelationshipType.PERFORMED_BY,
        0.80,
    ),
    (
        _p(
            rf"\b(?P<src>{_TAG}|{_NAMED_EQUIP}|{_PIPELINE}|{_INSTRUMENT})\s+"
            r"(?:is\s+|was\s+|are\s+|were\s+|shall\s+be\s+)?"
            r"(?:maintained|serviced|inspected|operated|checked|calibrated|"
            r"tested|repaired|overhauled|installed)\s+"
            r"(?:by)\s+"
            rf"(?P<tgt>{_OPERATOR})\b"
        ),
        RelationshipType.PERFORMED_BY,
        0.85,
    ),
]
