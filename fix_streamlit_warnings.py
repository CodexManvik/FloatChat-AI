#!/usr/bin/env python3
"""
Fix Streamlit deprecation warnings
"""

def fix_app_py():
    with open('app.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace all instances
    content = content.replace('use_container_width=True', 'width="stretch"')
    
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("Fixed all Streamlit deprecation warnings")

if __name__ == "__main__":
    fix_app_py()