import json

raw_file = "heroku_catalogo_raw.json"
clean_file = "heroku_catalogo_clean.json"

with open(raw_file, "rb") as f:
    content_bytes = f.read()

# Heroku usually outputs UTF-16 with BOM or UTF-8
if content_bytes.startswith(b"\xff\xfe") or content_bytes.startswith(b"\xfe\xff"):
    content = content_bytes.decode("utf-16")
else:
    content = content_bytes.decode("utf-8", errors="ignore")

lines = content.splitlines()
start_index = -1
for i, line in enumerate(lines):
    if line.strip() == "[":
        start_index = i
        break

if start_index == -1:
    print("Error: No se encontró el inicio del array JSON '['.")
    exit(1)

json_content = "\n".join(lines[start_index:])
data = json.loads(json_content)

with open(clean_file, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"Total objetos: {len(data)}")
counts = {}
for obj in data:
    m = obj.get("model")
    counts[m] = counts.get(m, 0) + 1
for m in sorted(counts.keys()):
    print(f"Model {m}: {counts[m]}")
