import os
import re

directory = 'app/agents/framework/agents'
files = [os.path.join(directory, f) for f in os.listdir(directory) if f.endswith('_tools.py')]

# Regex for the ID resolution pattern
ID_RESOLUTION_PATTERN = re.compile(
    r'(?P<indent>[ \t]+)resolved_id = (?P<id_var>\w+)\n'
    r'\s+resolved_name = ""\n\n'
    r'\s+if not resolved_id and (?P<name_var>\w+):\n'
    r'\s+try:\n'
    r'\s+results, _ = await self\._graph_svc\.search_entities\(\n'
    r'\s+query=\(?\2\)?,\s*limit=\d+,\n'
    r'\s+\)\n'
    r'\s+if results:\n'
    r'\s+resolved_id = results\[0\]\.id\n'
    r'\s+resolved_name = results\[0\]\.name\n'
    r'\s+else:\n'
    r'\s+return ToolResult\(\n'
    r'\s+data=(?P<fallback_data>[^,]+),\n'
    r'\s+error=f"No [^"]+ matching \'\{\2\}\'\.",?\n'
    r'\s+\)\n'
    r'\s+except Exception as exc:\n'
    r'\s+return ToolResult\(data=None, error=f"[^"]+: \{exc\}"\)'
)

def replace_id_resolution(content):
    def repl(m):
        indent = m.group('indent')
        id_var = m.group('id_var')
        name_var = m.group('name_var')
        return f'{indent}resolved_id, resolved_name, err = await self.resolve_entity({id_var}, {name_var}, self._graph_svc, context)\n{indent}if err:\n{indent}    return err'
    
    # Try a slightly looser regex since the formatting varies
    loose_regex = re.compile(
        r'(?P<indent>[ \t]+)resolved_id = (?P<id_var>\w+)\n'
        r'\s+resolved_name = ""\n+'
        r'\s+if not resolved_id and (?P<name_var>\w+):\n'
        r'\s+try:\n'
        r'\s+results, _ = await self\._graph_svc\.search_entities\([^)]+\)\n'
        r'\s+if results:\n'
        r'\s+resolved_id = results\[0\]\.id\n'
        r'\s+resolved_name = results\[0\]\.name\n'
        r'\s+else:\n'
        r'\s+return ToolResult\([^)]+\)\n'
        r'\s+except Exception as exc:\n'
        r'\s+return ToolResult\([^)]+\)'
    )
    return loose_regex.sub(repl, content)

LLM_PATTERN = re.compile(
    r'(?P<indent>[ \t]+)if self\._llm is not None(?: and [^:]+)?:(?:\s+#.*)?\n'
    r'\s+try:\n'
    r'\s+(?P<var>\w+) = await self\._llm\.generate\(prompt=(?P<prompt>[^)]+)\)\n'
    r'\s+except Exception as exc:\n'
    r'\s+context\.add_reasoning_step\([^)]+\)\n'
    r'\s+(?P=var) = (?P<fallback>.+?)\n'
)

def replace_llm_generation(content):
    def repl(m):
        indent = m.group('indent')
        var = m.group('var')
        prompt = m.group('prompt')
        fallback = m.group('fallback')
        return f'{indent}{var} = await self.generate_with_llm(prompt={prompt}, llm_provider=self._llm, context=context, fallback_value={fallback})\n'
    return LLM_PATTERN.sub(repl, content)

for f in files:
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
    
    new_content = replace_id_resolution(content)
    new_content = replace_llm_generation(new_content)
    
    if new_content != content:
        with open(f, 'w', encoding='utf-8') as file:
            file.write(new_content)
        print(f'Refactored {f}')
