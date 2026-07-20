import pytest
import base64
from typing import Any

from app.agents.framework.tools.context import ToolContext
from app.agents.framework.agents.data_tools import SqlTool, CsvTool, ExcelTool
from app.agents.framework.agents.integration_tools import EmailTool, PiHistorianTool, SapTool, RestTool
from app.agents.framework.agents.python_tools import PythonExecutionTool, ChartsTool
from app.agents.framework.agents.reporting_tools import ReportsTool, PdfGenerationTool


@pytest.fixture
def tool_context():
    return ToolContext(user_id="user-123", user_role="Engineer", conversation_id="conv-123")


@pytest.mark.asyncio
async def test_csv_tool(tool_context):
    tool = CsvTool()
    csv_data = "id,name,value\n1,SensorA,42.5\n2,SensorB,40.1"
    
    result = await tool.execute({"csv_data": csv_data}, tool_context)
    assert result.error is None
    assert result.data is not None
    assert len(result.data["rows"]) == 2
    assert result.data["rows"][0]["name"] == "SensorA"


@pytest.mark.asyncio
async def test_python_execution_tool(tool_context):
    tool = PythonExecutionTool()
    script = "print('Hello Industrial World')\nx = 10 * 5"
    
    result = await tool.execute({"script": script}, tool_context)
    assert result.error is None
    assert result.data is not None
    assert "Hello Industrial World" in result.data["stdout"]
    assert result.data["locals"]["x"] == "50"


@pytest.mark.asyncio
async def test_python_execution_tool_error(tool_context):
    tool = PythonExecutionTool()
    script = "1 / 0"
    
    result = await tool.execute({"script": script}, tool_context)
    assert result.error is not None
    assert "division by zero" in result.error


@pytest.mark.asyncio
async def test_email_tool(tool_context):
    tool = EmailTool()
    result = await tool.execute({
        "to": "admin@example.com",
        "subject": "Alert",
        "body": "System pressure high"
    }, tool_context)
    
    assert result.error is None
    assert result.data["success"] is True
    assert result.data["to"] == "admin@example.com"


@pytest.mark.asyncio
async def test_pi_historian_tool(tool_context):
    tool = PiHistorianTool()
    result = await tool.execute({
        "tag_name": "PUMP_1_VIB",
        "start_time": "2023-01-01T00:00:00Z",
        "end_time": "2023-01-02T00:00:00Z"
    }, tool_context)
    
    assert result.error is None
    assert result.data["tag_name"] == "PUMP_1_VIB"
    assert len(result.data["data"]) == 2


@pytest.mark.asyncio
async def test_reports_tool(tool_context):
    tool = ReportsTool()
    result = await tool.execute({
        "title": "Daily Summary",
        "sections": [
            {"heading": "Production", "content": "1000 units"}
        ],
        "format": "markdown"
    }, tool_context)
    
    assert result.error is None
    report = result.data["report"]
    assert "# Daily Summary" in report
    assert "## Production" in report
    assert "1000 units" in report


@pytest.mark.asyncio
async def test_pdf_generation_tool(tool_context):
    tool = PdfGenerationTool()
    # Assuming reportlab might not be installed, we check if it gracefully handles it or succeeds
    result = await tool.execute({"content": "Hello World"}, tool_context)
    if result.error:
        assert "reportlab" in result.error
    else:
        assert result.data["pdf_base64"] is not None


@pytest.mark.asyncio
async def test_charts_tool(tool_context):
    tool = ChartsTool()
    # Assuming matplotlib might not be installed
    result = await tool.execute({
        "chart_type": "bar",
        "data": {"labels": ["A", "B"], "y": [10, 20]},
        "title": "Test Chart"
    }, tool_context)
    
    if result.error:
        assert "matplotlib" in result.error
    else:
        assert result.data["image_base64"] is not None
        assert result.data["format"] == "png"
