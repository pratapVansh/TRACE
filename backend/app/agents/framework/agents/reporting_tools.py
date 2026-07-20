import base64
from typing import Any

from app.agents.framework.tool import ToolResult
from app.agents.framework.tools.base import FrameworkTool
from app.agents.framework.tools.context import ToolContext
from app.agents.framework.tools.schemas import ToolCategory, ToolMetadata
from app.core.authorization.permissions import Permission


class ReportsTool(FrameworkTool):
    metadata = ToolMetadata(
        tool_id="report_builder",
        name="Report Builder",
        description="Generates structured HTML or Markdown reports from sections.",
        category=ToolCategory.DOCUMENT,
        permissions={Permission.AI_AGENTS},
        input_schema={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "sections": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "heading": {"type": "string"},
                            "content": {"type": "string"}
                        }
                    }
                },
                "format": {"type": "string", "enum": ["markdown", "html"]}
            },
            "required": ["title", "sections"]
        }
    )

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        title = params.get("title", "Report")
        sections = params.get("sections", [])
        fmt = params.get("format", "markdown")
        
        report_str = ""
        
        if fmt == "markdown":
            report_str += f"# {title}\n\n"
            for sec in sections:
                heading = sec.get("heading", "")
                content = sec.get("content", "")
                report_str += f"## {heading}\n{content}\n\n"
        elif fmt == "html":
            report_str += f"<h1>{title}</h1>\n"
            for sec in sections:
                heading = sec.get("heading", "")
                content = sec.get("content", "")
                report_str += f"<h2>{heading}</h2>\n<p>{content}</p>\n"
                
        context.add_reasoning_step("ReportsTool: Assembled structured report.")
        return ToolResult(data={"report": report_str, "format": fmt})


class PdfGenerationTool(FrameworkTool):
    metadata = ToolMetadata(
        tool_id="pdf_generator",
        name="PDF Generator",
        description="Generates a PDF from text or HTML and returns it as base64.",
        category=ToolCategory.DOCUMENT,
        permissions={Permission.AI_AGENTS},
        input_schema={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "HTML or text content"},
                "is_html": {"type": "boolean", "description": "Whether content is HTML (default False)"}
            },
            "required": ["content"]
        }
    )

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        content = params.get("content", "")
        is_html = params.get("is_html", False)
        
        if not content:
            return ToolResult(data=None, error="Content is empty")
            
        try:
            # For demonstration, if reportlab or pdfkit is not available, we return a mock PDF or basic rendering.
            # We'll try importing reportlab to generate a basic PDF.
            import io
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter
            
            buf = io.BytesIO()
            c = canvas.Canvas(buf, pagesize=letter)
            
            # Simple line breaking for text
            textobject = c.beginText()
            textobject.setTextOrigin(50, 750)
            textobject.setFont("Helvetica", 12)
            
            # Strip simple HTML if is_html is set (naive approach for fallback)
            display_text = content
            if is_html:
                import re
                display_text = re.sub('<[^<]+?>', '', content)
                
            lines = display_text.split('\n')
            for line in lines:
                textobject.textLine(line[:100]) # truncated line to fit roughly
                
            c.drawText(textobject)
            c.showPage()
            c.save()
            
            b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            context.add_reasoning_step("PdfGenerationTool: Generated PDF.")
            return ToolResult(data={"pdf_base64": b64})
            
        except ImportError:
            return ToolResult(data=None, error="reportlab is required for PDF generation")
        except Exception as e:
            return ToolResult(data=None, error=f"PDF generation failed: {e}")
