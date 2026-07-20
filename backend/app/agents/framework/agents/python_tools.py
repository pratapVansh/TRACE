import sys
import io
import base64
from typing import Any

from app.agents.framework.tool import ToolResult
from app.agents.framework.tools.base import FrameworkTool
from app.agents.framework.tools.context import ToolContext
from app.agents.framework.tools.schemas import ToolCategory, ToolMetadata
from app.core.authorization.permissions import Permission


class PythonExecutionTool(FrameworkTool):
    metadata = ToolMetadata(
        tool_id="python_execute",
        name="Python Execution",
        description="Executes a Python script in a restricted sandbox and returns stdout.",
        category=ToolCategory.ACTION,
        permissions={Permission.AI_AGENTS},
        input_schema={
            "type": "object",
            "properties": {
                "script": {"type": "string", "description": "Python script to execute"}
            },
            "required": ["script"]
        }
    )

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        script = params.get("script", "")
        if not script.strip():
            return ToolResult(data=None, error="Script cannot be empty")
        
        # We redirect stdout to capture print statements
        old_stdout = sys.stdout
        redirected_output = io.StringIO()
        sys.stdout = redirected_output
        
        # We run the code in an empty dictionary to isolate its global scope.
        # Note: In a true production environment, this should be executed in an isolated container/sandbox (e.g., Docker, gVisor, WebAssembly).
        # This implementation uses `exec` directly, assuming network and OS level restrictions apply to the Python worker process.
        local_scope = {}
        try:
            exec(script, {}, local_scope)
            output = redirected_output.getvalue()
            context.add_reasoning_step("PythonExecutionTool: Executed python script successfully.")
            return ToolResult(data={"stdout": output, "locals": {k: str(v) for k, v in local_scope.items() if not k.startswith("__")}})
        except Exception as e:
            return ToolResult(data=None, error=f"Python execution failed: {e}")
        finally:
            sys.stdout = old_stdout


class ChartsTool(FrameworkTool):
    metadata = ToolMetadata(
        tool_id="chart_generator",
        name="Chart Generator",
        description="Generates charts (bar, line, pie) from data and returns a base64 encoded image.",
        category=ToolCategory.DATA,
        permissions={Permission.AI_AGENTS},
        input_schema={
            "type": "object",
            "properties": {
                "chart_type": {"type": "string", "enum": ["bar", "line", "pie", "scatter"]},
                "data": {"type": "object", "description": "Data dictionary e.g. {'x': [1,2,3], 'y': [4,5,6]}"},
                "title": {"type": "string"}
            },
            "required": ["chart_type", "data"]
        }
    )

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
        except ImportError:
            return ToolResult(data=None, error="matplotlib is not installed")
            
        chart_type = params.get("chart_type")
        data = params.get("data", {})
        title = params.get("title", "Chart")
        
        try:
            fig, ax = plt.subplots()
            
            x = data.get("x", [])
            y = data.get("y", [])
            labels = data.get("labels", [])
            
            if chart_type == "bar":
                ax.bar(x or labels, y)
            elif chart_type == "line":
                ax.plot(x, y, marker='o')
            elif chart_type == "pie":
                ax.pie(y, labels=labels, autopct='%1.1f%%')
            elif chart_type == "scatter":
                ax.scatter(x, y)
                
            ax.set_title(title)
            
            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight')
            plt.close(fig)
            
            b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            context.add_reasoning_step(f"ChartsTool: Generated {chart_type} chart.")
            
            return ToolResult(data={"image_base64": b64, "format": "png"})
        except Exception as e:
            return ToolResult(data=None, error=f"Chart generation failed: {e}")
