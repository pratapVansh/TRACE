import os
import re

directory = 'app/agents/framework/agents'
files = [os.path.join(directory, f) for f in os.listdir(directory) if f.endswith('_tools.py')]

def refactor_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Pattern for ID resolution
    id_pattern = re.compile(
        r'(?P<indent>[ \t]+)resolved_id\s*=\s*(?P<id_var>\w+)\n'
        r'\s*resolved_name\s*=\s*""\n+'
        r'\s*if not resolved_id and (?P<name_var>\w+):\n'
        r'\s*try:\n'
        r'\s*results, _ = await self\._graph_svc\.search_entities\([\s\S]*?limit=\d+[\s\S]*?\)\n'
        r'\s*if results:\n'
        r'\s*resolved_id = results\[0\]\.id\n'
        r'\s*resolved_name = results\[0\]\.name\n'
        r'\s*else:\n'
        r'\s*return ToolResult\([\s\S]*?\)\n'
        r'\s*except Exception as exc:\n'
        r'\s*return ToolResult\([\s\S]*?\)\n'
    )

    def repl_id(m):
        indent = m.group('indent')
        id_var = m.group('id_var')
        name_var = m.group('name_var')
        return f'{indent}resolved_id, resolved_name, err = await self.resolve_entity({id_var}, {name_var}, self._graph_svc, context)\n{indent}if err:\n{indent}    return err\n'

    content = id_pattern.sub(repl_id, content)
    
    # Pattern for LLM Generation
    llm_pattern = re.compile(
        r'(?P<indent>[ \t]+)if self\._llm is not None(?: and [^:]+)?:(?:\s*#.*)?\n'
        r'\s*try:\n'
        r'\s*(?P<var>\w+) = await self\._llm\.generate\(prompt=(?P<prompt>[^)]+)\)\n'
        r'\s*except Exception as exc:\n'
        r'\s*context\.add_reasoning_step\([^)]+\)\n'
        r'\s*(?P=var) = (?P<fallback>.+?)\n'
    )
    def repl_llm(m):
        indent = m.group('indent')
        var = m.group('var')
        prompt = m.group('prompt')
        fallback = m.group('fallback')
        return f'{indent}{var} = await self.generate_with_llm(prompt={prompt}, llm_provider=self._llm, context=context, fallback_value={fallback})\n'

    content = llm_pattern.sub(repl_llm, content)

    # Some LLM generation are slightly different (fallback is just "")
    llm_pattern2 = re.compile(
        r'(?P<indent>[ \t]+)if self\._llm is not None:\n'
        r'\s*try:\n'
        r'\s*(?P<var>\w+) = await self\._llm\.generate\(prompt=(?P<prompt>[^)]+)\)\n'
        r'\s*except Exception as exc:\n'
        r'\s*context\.add_reasoning_step\([^)]+\)\n'
    )
    def repl_llm2(m):
        indent = m.group('indent')
        var = m.group('var')
        prompt = m.group('prompt')
        return f'{indent}{var} = await self.generate_with_llm(prompt={prompt}, llm_provider=self._llm, context=context, fallback_value="")\n'
        
    content = llm_pattern2.sub(repl_llm2, content)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

for f in files:
    refactor_file(f)
    print(f"Processed {f}")

