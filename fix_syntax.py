import sys

file_path = 'web/services/formatting_service.py'
with open(file_path, 'r') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    # Match the specific line with the outer f-string and inner JS curly braces
    if 'f"onclick=\\"(function(bid, cid){const c=document.getElementById(cid);' in line:
        # Escape double curly braces for regular f-string syntax in Python
        new_line = line.replace('{const', '{{const').replace('none\';', 'none\';')
        new_line = new_line.replace('display===\'none\';', 'display===\'none\';')
        # We need to be careful. Let's just manually construct the replacement for that specific line.
        new_line = (
            '            f"onclick=\\\"(function(bid, cid){{const c=document.getElementById(cid); '
            'const b=document.getElementById(bid); const show=c.style.display===\'none\'; '
            'c.style.display=show?\'block\':\'none\'; '
            'b.textContent=show?\'Hide recommendations\':\'Show recommendations\';}}'
            '(\'btn_{toggle_id}\',\'{toggle_id}\')\\\">\"\n'
        )
        new_lines.append(new_line)
    else:
        new_lines.append(line)

with open(file_path, 'w') as f:
    f.writelines(new_lines)
