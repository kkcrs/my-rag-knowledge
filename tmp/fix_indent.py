"""Fix indentation of stream_answer method in chat_service.py."""
import re

with open('backend/app/services/chat_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
fixed = []
in_stream = False
for line in lines:
    stripped = line.strip()
    
    # Detect stream_answer definition (no indentation)
    if stripped.startswith('async def stream_answer('):
        in_stream = True
        fixed.append('    ' + line.lstrip())
        continue
    
    # Detect _persist methods - end of stream_answer
    if in_stream and stripped.startswith('async def _persist'):
        in_stream = False
        fixed.append(line)
        continue
    
    if in_stream:
        # Add indentation to all lines inside stream_answer
        if line.strip():
            fixed.append('    ' + line)
        else:
            fixed.append(line)
        continue
    
    fixed.append(line)

content = '\n'.join(fixed)
with open('backend/app/services/chat_service.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed indentation of stream_answer')
