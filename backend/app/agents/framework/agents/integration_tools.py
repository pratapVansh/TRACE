import httpx
from typing import Any

from app.agents.framework.tool import ToolResult
from app.agents.framework.tools.base import FrameworkTool
from app.agents.framework.tools.context import ToolContext
from app.agents.framework.tools.schemas import ToolCategory, ToolMetadata
from app.core.authorization.permissions import Permission


class EmailTool(FrameworkTool):
    metadata = ToolMetadata(
        tool_id="send_email",
        name="Send Email",
        description="Sends an email via SMTP (mocked for demo).",
        category=ToolCategory.ACTION,
        permissions={Permission.AI_AGENTS},
        input_schema={
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"}
            },
            "required": ["to", "subject", "body"]
        }
    )

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        to = params.get("to")
        subject = params.get("subject")
        body = params.get("body")
        
        # Mocking SMTP send
        context.add_reasoning_step(f"EmailTool: Simulated sending email to {to} with subject '{subject}'.")
        return ToolResult(data={"success": True, "message": "Email sent successfully", "to": to})


class PiHistorianTool(FrameworkTool):
    metadata = ToolMetadata(
        tool_id="pi_historian",
        name="PI Historian Query",
        description="Queries OSIsoft PI Historian for time-series data.",
        category=ToolCategory.DATA,
        permissions={Permission.AI_AGENTS},
        input_schema={
            "type": "object",
            "properties": {
                "tag_name": {"type": "string"},
                "start_time": {"type": "string"},
                "end_time": {"type": "string"}
            },
            "required": ["tag_name", "start_time", "end_time"]
        }
    )

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        tag_name = params.get("tag_name")
        start = params.get("start_time")
        end = params.get("end_time")
        
        # Mocking PI Web API
        mock_data = [
            {"timestamp": start, "value": 100.5, "good": True},
            {"timestamp": end, "value": 105.2, "good": True}
        ]
        context.add_reasoning_step(f"PiHistorianTool: Fetched mock data for tag {tag_name}.")
        return ToolResult(data={"tag_name": tag_name, "data": mock_data})


class SapTool(FrameworkTool):
    metadata = ToolMetadata(
        tool_id="sap_execute",
        name="SAP RFC/BAPI Execution",
        description="Executes a SAP BAPI or RFC (mocked).",
        category=ToolCategory.ACTION,
        permissions={Permission.AI_AGENTS},
        input_schema={
            "type": "object",
            "properties": {
                "bapi_name": {"type": "string"},
                "parameters": {"type": "object"}
            },
            "required": ["bapi_name"]
        }
    )

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        bapi = params.get("bapi_name")
        context.add_reasoning_step(f"SapTool: Simulated call to {bapi}.")
        
        return ToolResult(data={
            "bapi_name": bapi,
            "status": "Success",
            "return_message": "Mock SAP execution completed."
        })


class RestTool(FrameworkTool):
    metadata = ToolMetadata(
        tool_id="rest_client",
        name="REST API Client",
        description="Makes HTTP REST calls to external services.",
        category=ToolCategory.ACTION,
        permissions={Permission.AI_AGENTS},
        input_schema={
            "type": "object",
            "properties": {
                "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"]},
                "url": {"type": "string"},
                "headers": {"type": "object"},
                "json_data": {"type": "object"}
            },
            "required": ["method", "url"]
        }
    )

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        method = params.get("method", "GET").upper()
        url = params.get("url")
        headers = params.get("headers", {})
        json_data = params.get("json_data")
        
        # To avoid abuse in our system, we might restrict domains. 
        # But this is a generic tool.
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.request(method, url, headers=headers, json=json_data)
                context.add_reasoning_step(f"RestTool: Executed {method} {url} with status {response.status_code}")
                
                try:
                    resp_data = response.json()
                except Exception:
                    resp_data = response.text
                
                return ToolResult(data={"status_code": response.status_code, "response": resp_data})
        except Exception as e:
            return ToolResult(data=None, error=f"REST call failed: {e}")
