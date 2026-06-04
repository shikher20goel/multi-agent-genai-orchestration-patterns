import json, sys
p = "prd.json"
with open(p) as f:
    data = json.load(f)
for t in data["tasks"]:
    if t["id"] in sys.argv[1:]:
        t["passes"] = True
with open(p, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
