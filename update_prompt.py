import re

with open("app/llm.py", "r", encoding="utf-8") as f:
    content = f.read()

with open("app/improved_system_prompt.txt", "r", encoding="utf-8") as f:
    new_prompt = f.read()

new_content = re.sub(
    r'SYSTEM_PROMPT\s*=\s*\"\"\"[\s\S]*?\"\"\"',
    'SYSTEM_PROMPT = \"\"\"' + new_prompt + '\"\"\"',
    content
)

with open("app/llm.py", "w", encoding="utf-8") as f:
    f.write(new_content)

print("Done!")
