"""Script to generate the Cursor SQLite fixture for tests."""

import json
import sqlite3
from pathlib import Path

fixture_path = Path(__file__).parent / "cursor_workspace" / "state.vscdb"
fixture_path.parent.mkdir(parents=True, exist_ok=True)

con = sqlite3.connect(str(fixture_path))
con.execute("CREATE TABLE IF NOT EXISTS ItemTable ([key] TEXT PRIMARY KEY, value TEXT)")

chat_data = {
    "tabs": [
        {
            "bubbles": [
                {
                    "type": "user",
                    "text": "Refactor the database layer",
                    "createdAt": 1709546400000,  # 2024-03-04T10:00:00Z
                },
                {
                    "type": "ai",
                    "rawText": "I'll restructure the DB module to use the repository pattern.",
                    "createdAt": 1709546460000,  # 2024-03-04T10:01:00Z
                },
                {
                    "type": "user",
                    "delegate": {"a": "Also add connection pooling"},
                    "text": "fallback text",
                    "createdAt": 1709546520000,  # 2024-03-04T10:02:00Z
                },
                {
                    "type": "user",
                    "text": "Old message",
                    "createdAt": 1709539200000,  # 2024-03-04T08:00:00Z (before window)
                },
            ],
            "timestamp": 0,
        }
    ]
}

# Embed project path so _matches_project can find it
chat_data["project_path"] = "/Users/dev/project"

con.execute(
    "INSERT OR REPLACE INTO ItemTable ([key], value) VALUES (?, ?)",
    ("workbench.panel.aichat.view.aichat.chatdata", json.dumps(chat_data)),
)
con.commit()
con.close()
print(f"✓ Cursor fixture created at {fixture_path}")
