from enum import Enum


class EntityType(str, Enum):
    EQUIPMENT = "Equipment"
    PUMP = "Pump"
    VALVE = "Valve"
    COMPRESSOR = "Compressor"
    PIPELINE = "Pipeline"
    TANK = "Tank"
    INSTRUMENT = "Instrument"
    MOTOR = "Motor"
    HEAT_EXCHANGER = "Heat Exchanger"
    UNIT = "Unit"
    PROCEDURE = "Procedure"
    DOCUMENT = "Document"
    STANDARD = "Standard"
    CHEMICAL = "Chemical"
    LOCATION = "Location"
    FAILURE = "Failure"
    CAUSE = "Cause"
    OPERATOR = "Operator"
    USER = "User"
    DEPARTMENT = "Department"
    ROLE = "Role"

    @classmethod
    def _missing_(cls, value: object) -> "EntityType | None":
        normalized = str(value).strip().lower().replace(" ", "_")
        for member in cls:
            if member.value.lower().replace(" ", "_") == normalized:
                return member
        return None
