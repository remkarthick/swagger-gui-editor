from flask import Flask, render_template, request, jsonify
import yaml
import json
import sqlite3
from datetime import datetime

app = Flask(__name__)
DB_FILE = "swagger_specs.db"


def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS specs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            yaml_text TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def default_openapi_spec():
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Neon API",
            "description": "Futuristic API editor demo",
            "version": "1.0.0"
        },
        "servers": [
            {"url": "https://api.example.com"}
        ],
        "paths": {
            "/users": {
                "post": {
                    "summary": "Create user",
                    "description": "Creates a new user",
                    "parameters": [
                        {
                            "name": "X-Request-ID",
                            "in": "header",
                            "description": "Tracking ID",
                            "required": False,
                            "schema": {"type": "string"},
                            "example": "abc-123"
                        }
                    ],
                    "requestBody": {
                        "required": False,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["name"],
                                    "properties": {
                                        "name": {"type": "string"},
                                        "email": {"type": "string"}
                                    }
                                },
                                "examples": {
                                    "basicUser": {
                                        "summary": "Basic user",
                                        "value": {
                                            "name": "John",
                                            "email": "john@example.com"
                                        }
                                    },
                                    "adminUser": {
                                        "summary": "Admin user",
                                        "value": {
                                            "name": "Alice",
                                            "email": "alice@example.com",
                                            "role": "admin"
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Successful response",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "required": ["id", "name"],
                                        "properties": {
                                            "id": {"type": "integer"},
                                            "name": {"type": "string"}
                                        }
                                    },
                                    "examples": {
                                        "successBasic": {
                                            "summary": "Success response",
                                            "value": {
                                                "id": 1,
                                                "name": "John"
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }


def parse_json_text(text, fallback=None):
    text = (text or "").strip()
    if not text:
        return fallback
    try:
        return json.loads(text)
    except Exception:
        return fallback if fallback is not None else text


def field_to_schema(field):
    field_type = field.get("type", "string")

    if field_type == "object":
        properties = {}
        required = []

        for child in field.get("children", []):
            child_name = (child.get("name") or "").strip()
            if not child_name:
                continue
            properties[child_name] = field_to_schema(child)
            if child.get("required"):
                required.append(child_name)

        schema = {
            "type": "object",
            "properties": properties
        }
        if required:
            schema["required"] = required
        return schema

    if field_type == "array":
        array_item_type = field.get("arrayItemType", "string")

        if array_item_type in ["string", "integer", "number", "boolean"]:
            return {
                "type": "array",
                "items": {"type": array_item_type}
            }

        if array_item_type == "object":
            properties = {}
            required = []

            for child in field.get("arrayChildren", []):
                child_name = (child.get("name") or "").strip()
                if not child_name:
                    continue
                properties[child_name] = field_to_schema(child)
                if child.get("required"):
                    required.append(child_name)

            items_schema = {
                "type": "object",
                "properties": properties
            }
            if required:
                items_schema["required"] = required

            return {
                "type": "array",
                "items": items_schema
            }

        if array_item_type == "array":
            return {
                "type": "array",
                "items": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            }

        return {
            "type": "array",
            "items": {"type": "string"}
        }

    return {"type": field_type}


def visual_fields_to_schema(fields):
    properties = {}
    required = []

    for field in fields or []:
        name = (field.get("name") or "").strip()
        if not name:
            continue
        properties[name] = field_to_schema(field)
        if field.get("required"):
            required.append(name)

    schema = {
        "type": "object",
        "properties": properties
    }
    if required:
        schema["required"] = required
    return schema


def build_schema_from_variants(mode, variants):
    built = []

    for variant in variants or []:
        fields = variant.get("fields", [])
        built.append(visual_fields_to_schema(fields))

    if not built:
        return None

    if mode == "single" or len(built) == 1:
        return built[0]

    if mode in ["oneOf", "anyOf", "allOf"]:
        return {mode: built}

    return built[0]


def build_examples_dict(examples):
    result = {}

    for example in examples or []:
        key = (example.get("key") or "").strip()
        if not key:
            continue

        value_text = example.get("value", "")
        value_obj = parse_json_text(value_text, None)
        if value_obj is None:
            continue

        item = {"value": value_obj}
        summary = (example.get("summary") or "").strip()
        if summary:
            item["summary"] = summary

        result[key] = item

    return result


@app.route("/")
def index():
    spec = default_openapi_spec()
    yaml_text = yaml.dump(spec, sort_keys=False, allow_unicode=True)
    return render_template("index.html", initial_yaml=yaml_text)


@app.route("/generate_yaml", methods=["POST"])
def generate_yaml():
    data = request.json or {}

    spec = {
        "openapi": "3.0.3",
        "info": {
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "version": data.get("version", "1.0.0")
        },
        "servers": [],
        "paths": {}
    }

    for server in data.get("servers", []):
        if server.get("url"):
            spec["servers"].append({"url": server["url"]})

    for path_item in data.get("paths", []):
        path_url = (path_item.get("url") or "").strip()
        method = (path_item.get("method") or "").lower().strip()

        if not path_url or not method:
            continue

        if path_url not in spec["paths"]:
            spec["paths"][path_url] = {}

        operation = {
            "summary": path_item.get("summary", ""),
            "description": path_item.get("description", ""),
            "responses": {
                "200": {
                    "description": "Successful response"
                }
            }
        }

        headers = []
        for hdr in path_item.get("headers", []):
            name = (hdr.get("name") or "").strip()
            if not name:
                continue

            header_obj = {
                "name": name,
                "in": "header",
                "description": hdr.get("description", ""),
                "required": bool(hdr.get("required", False)),
                "schema": {"type": hdr.get("type", "string")}
            }

            example = (hdr.get("example", "") or "").strip()
            if example:
                header_obj["example"] = parse_json_text(example, example)

            headers.append(header_obj)

        if headers:
            operation["parameters"] = headers

        # Backward compatibility with old single-schema payload
        request_schema = None
        if path_item.get("request_schema_obj") is not None:
            request_schema = path_item.get("request_schema_obj")
        else:
            request_schema = build_schema_from_variants(
                path_item.get("request_schema_mode", "single"),
                path_item.get("request_schema_variants", [])
            )

        # Backward compatibility with old single-example payload
        request_examples = {}
        if path_item.get("request_examples"):
            request_examples = build_examples_dict(path_item.get("request_examples", []))
        else:
            request_example = parse_json_text(path_item.get("request_example", "").strip(), None)
            if request_example is not None:
                request_examples = {
                    "default": {
                        "summary": "Default example",
                        "value": request_example
                    }
                }

        if request_schema is not None or request_examples:
            operation["requestBody"] = {
                "required": False,
                "content": {
                    "application/json": {}
                }
            }
            request_media = operation["requestBody"]["content"]["application/json"]

            if request_schema is not None:
                request_media["schema"] = request_schema

            if request_examples:
                request_media["examples"] = request_examples

        response_schema = None
        if path_item.get("response_schema_obj") is not None:
            response_schema = path_item.get("response_schema_obj")
        else:
            response_schema = build_schema_from_variants(
                path_item.get("response_schema_mode", "single"),
                path_item.get("response_schema_variants", [])
            )

        response_examples = {}
        if path_item.get("response_examples"):
            response_examples = build_examples_dict(path_item.get("response_examples", []))
        else:
            response_example = parse_json_text(path_item.get("response_example", "").strip(), None)
            if response_example is not None:
                response_examples = {
                    "default": {
                        "summary": "Default example",
                        "value": response_example
                    }
                }

        if response_schema is not None or response_examples:
            operation["responses"]["200"]["content"] = {
                "application/json": {}
            }
            response_media = operation["responses"]["200"]["content"]["application/json"]

            if response_schema is not None:
                response_media["schema"] = response_schema

            if response_examples:
                response_media["examples"] = response_examples

        spec["paths"][path_url][method] = operation

    yaml_text = yaml.dump(spec, sort_keys=False, allow_unicode=True)
    return jsonify({
        "yaml": yaml_text,
        "json": spec
    })


@app.route("/parse_yaml", methods=["POST"])
def parse_yaml():
    data = request.json or {}
    text = data.get("yaml", "")

    try:
        parsed = yaml.safe_load(text)
        return jsonify({
            "success": True,
            "json": parsed
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400


@app.route("/api/specs", methods=["GET"])
def list_specs():
    q = (request.args.get("q") or "").strip().lower()

    conn = get_db_connection()
    if q:
        rows = conn.execute("""
            SELECT id, name, created_at, updated_at
            FROM specs
            WHERE lower(name) LIKE ?
            ORDER BY updated_at DESC, id DESC
        """, (f"%{q}%",)).fetchall()
    else:
        rows = conn.execute("""
            SELECT id, name, created_at, updated_at
            FROM specs
            ORDER BY updated_at DESC, id DESC
        """).fetchall()
    conn.close()

    return jsonify([
        {
            "id": row["id"],
            "name": row["name"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }
        for row in rows
    ])


@app.route("/api/specs/<int:spec_id>", methods=["GET"])
def get_spec(spec_id):
    conn = get_db_connection()
    row = conn.execute("""
        SELECT id, name, yaml_text, created_at, updated_at
        FROM specs
        WHERE id = ?
    """, (spec_id,)).fetchone()
    conn.close()

    if not row:
        return jsonify({"success": False, "error": "Spec not found"}), 404

    return jsonify({
        "success": True,
        "spec": {
            "id": row["id"],
            "name": row["name"],
            "yaml_text": row["yaml_text"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }
    })


@app.route("/api/specs", methods=["POST"])
def create_spec():
    data = request.json or {}
    name = (data.get("name") or "").strip()
    yaml_text = data.get("yaml_text", "")

    if not name:
        return jsonify({"success": False, "error": "Name is required"}), 400

    now = datetime.utcnow().isoformat()

    conn = get_db_connection()
    cursor = conn.execute("""
        INSERT INTO specs (name, yaml_text, created_at, updated_at)
        VALUES (?, ?, ?, ?)
    """, (name, yaml_text, now, now))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()

    return jsonify({"success": True, "id": new_id})


@app.route("/api/specs/<int:spec_id>", methods=["PUT"])
def update_spec(spec_id):
    data = request.json or {}
    name = (data.get("name") or "").strip()
    yaml_text = data.get("yaml_text", "")
    now = datetime.utcnow().isoformat()

    if not name:
        return jsonify({"success": False, "error": "Name is required"}), 400

    conn = get_db_connection()
    row = conn.execute("SELECT id FROM specs WHERE id = ?", (spec_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"success": False, "error": "Spec not found"}), 404

    conn.execute("""
        UPDATE specs
        SET name = ?, yaml_text = ?, updated_at = ?
        WHERE id = ?
    """, (name, yaml_text, now, spec_id))
    conn.commit()
    conn.close()

    return jsonify({"success": True})


@app.route("/api/specs/<int:spec_id>", methods=["DELETE"])
def delete_spec(spec_id):
    conn = get_db_connection()
    row = conn.execute("SELECT id FROM specs WHERE id = ?", (spec_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"success": False, "error": "Spec not found"}), 404

    conn.execute("DELETE FROM specs WHERE id = ?", (spec_id,))
    conn.commit()
    conn.close()

    return jsonify({"success": True})


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
