#!/usr/bin/env python3
import json
import os
from pathlib import Path

inbox = Path(os.environ["OBSIDIAN_VAULT_PATH"]).expanduser() / "content" / "inbox"
files = list(inbox.rglob("*.md")) if inbox.exists() else []

if files:
    print(json.dumps({"wakeAgent": True}))
    print(f"{len(files)} new files in inbox:")
    for file in files:
        print(f"  {file.relative_to(inbox)}")
else:
    print(json.dumps({"wakeAgent": False}))
