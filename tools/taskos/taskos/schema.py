from __future__ import annotations

import json


TASKS_SCHEMA: dict[str, object] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://example.local/codex-taskos/tasks.schema.json",
    "title": "Codex TaskOS tasks file",
    "oneOf": [
        {"$ref": "#/$defs/taskArray"},
        {
            "type": "object",
            "required": ["tasks"],
            "properties": {
                "project": {"type": "object"},
                "agent_instructions": {"type": "object"},
                "tasks": {"$ref": "#/$defs/taskArray"},
            },
            "additionalProperties": True,
        },
    ],
    "$defs": {
        "taskArray": {
            "type": "array",
            "items": {"$ref": "#/$defs/task"},
        },
        "task": {
            "type": "object",
            "required": ["id", "title", "status"],
            "properties": {
                "id": {"type": "string", "minLength": 1},
                "title": {"type": "string", "minLength": 1},
                "description": {"type": "string"},
                "status": {"enum": ["pending", "in_progress", "blocked", "done"]},
                "priority": {"type": "string"},
                "category": {"type": "string"},
                "dependencies": {
                    "type": "array",
                    "items": {"type": "string"},
                    "uniqueItems": True,
                },
                "scope": {"type": "array", "items": {"type": "string"}},
                "acceptance_criteria": {"type": "array", "items": {"type": "string"}},
                "test_steps": {"type": "array", "items": {"type": "string"}},
                "notes": {"type": "string"},
            },
            "additionalProperties": True,
        },
    },
}


def schema_json() -> str:
    return json.dumps(TASKS_SCHEMA, indent=2) + "\n"
