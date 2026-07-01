from pydantic import BaseModel


class DemoAdminResponse(BaseModel):
    message: str = "Admin access granted"
