
import os

def search_files(directory, search_text):
    print(f"Searching for '{search_text}' in {directory}...")
    for root, dirs, files in os.walk(directory):
        if 'venv' in dirs:
            dirs.remove('venv')
        if '__pycache__' in dirs:
            dirs.remove('__pycache__')
        if '.git' in dirs:
            dirs.remove('.git')
        if 'node_modules' in dirs:
            dirs.remove('node_modules')
        if 'frontend' in dirs:
            dirs.remove('frontend')
            
        for file in files:
            if file.endswith(('.py', '.json', '.js', '.ts', '.tsx')):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        if search_text in content:
                            print(f"FOUND in: {path}")
                            # Print context
                            lines = content.splitlines()
                            for i, line in enumerate(lines):
                                if search_text in line:
                                    print(f"  Line {i+1}: {line.strip()[:100]}")
                except Exception as e:
                    print(f"Error reading {path}: {e}")

if __name__ == "__main__":
    search_files("C:\\Users\\Nxiss\\OneDrive\\Desktop\\Polymarket-Kalshi-Bot", "leverage_allowed")
