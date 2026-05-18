import os
import json

def extract_todos():
    todos = []
    # exclude dev/archived and __pycache__
    lines = os.popen('grep -rn "TODO" packages/ dev/ --exclude-dir=archived --exclude-dir=__pycache__').readlines()
    for line in lines:
        parts = line.split(":", 2)
        if len(parts) >= 3:
            file, line_num, content = parts
            priority = "sometime"
            content_lower = content.lower()
            if "urgent" in content_lower:
                priority = "urgent"
            elif "release" in content_lower:
                priority = "before release"
            todos.append({"file": file, "line": line_num, "text": content.strip(), "priority": priority})
    return todos

todos = extract_todos()
with open("prioritized_todos.json", "w") as f:
    json.dump(todos, f, indent=2)

print(f"Extracted {len(todos)} TODOs.")
