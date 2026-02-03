import re

file_path = "src/services/bot_runner.py"

with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
indent_next = False
inside_try_block = False
target_indent_level = 0

for i, line in enumerate(lines):
    # Detect the async context manager line we added
    if "async with async_session_factory() as db:" in line:
        new_lines.append(line)
        indent_next = True
        # Calculate current indentation + 4 spaces
        current_indent = len(line) - len(line.lstrip())
        target_indent_level = current_indent + 4
        continue

    # Detect end of the block being indented (except/finally/or next usage)
    # The 'except' block usually has the same indentation as the 'try' block.
    # The 'try' block was indented by N (e.g. 12 spaces).
    # The 'async with' is at N+4 (16 spaces).
    # The code inside was at N+4 (16 spaces).
    # We want to indent it to N+8 (20 spaces).
    
    stripped = line.lstrip()
    
    if indent_next:
        # Stop indenting when we hit an 'except' block or empty line that breaks flow?
        # Empty lines are fine.
        # 'except' block will have lower indentation than our target.
        if stripped.startswith("except ") or stripped.startswith("finally:"):
             indent_next = False
        elif stripped == "":
            pass # Keep empty lines structure but no need to indent specific amount usually
        else:
             # Add 4 spaces to existing indentation
             # ONLY if this line was previously at the same level as our 'async with' or deeper?
             # Actually, simpler: Just add 4 spaces to everything until 'except'.
             if indent_next:
                 if line.strip(): # Only indent non-empty lines
                    line = "    " + line
    
    new_lines.append(line)

with open(file_path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("Indentation fixed.")
