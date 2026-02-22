import os
import glob
import re

root = r"c:\Users\aseem\Desktop\VAMS-main\VAMS-main"

replacements = {
    r"Team Docs/": r"docs/team/",
    r"Team%20Docs/": r"docs/team/",
    r"narrative/": r"docs/narrative/",
    r"papers/": r"docs/papers/",
    r"VAMS - Dawn of Agentic Economy.pdf": r"docs/papers/VAMS - Dawn of Agentic Economy.pdf",
    r"VAMS%20-%20Dawn%20of%20Agentic%20Economy.pdf": r"docs/papers/VAMS%20-%20Dawn%20of%20Agentic%20Economy.pdf"
}

for root_dir, dirs, files in os.walk(root):
    if ".git" in root_dir or "node_modules" in root_dir or ".data" in root_dir:
        continue
    for file in files:
        if file.endswith(('.md', '.jsx', '.tsx', '.js', '.ts', '.html', '.json', '.txt')):
            path = os.path.join(root_dir, file)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                new_content = content
                for old, new in replacements.items():
                    if old in new_content:
                        new_content = new_content.replace(old, new)
                
                if new_content != content:
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    print(f"Updated links in {path}")
            except Exception as e:
                pass
