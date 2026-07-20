import os, re

directory = 'app/agents/framework/agents'
files = [os.path.join(directory, f) for f in os.listdir(directory) if f.endswith('_agent.py')]

for f in files:
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # regex to find 'return AgentResponse('
    pattern = re.compile(r'([ \t]+)return AgentResponse\(')
    
    def repl(m):
        indent = m.group(1)
        return (
            f'{indent}_search_dict = locals().get("search_data") or locals().get("search_results") or locals().get("report_data")\n'
            f'{indent}_final_conf, _expl = self.evaluate_confidence(True, _search_dict, locals().get("answer", ""))\n'
            f'{indent}confidence = _final_conf\n'
            f'{indent}return AgentResponse(\n'
            f'{indent}    confidence_explanation=_expl,'
        )
        
    new_content = pattern.sub(repl, content)
    
    if new_content != content:
        with open(f, 'w', encoding='utf-8') as file:
            file.write(new_content)
        print(f'Updated {f}')
