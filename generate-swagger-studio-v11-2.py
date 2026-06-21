from pathlib import Path
import traceback

APP_PY = r'''from flask import Flask, render_template, request, jsonify, Response
import sqlite3
import yaml
import json
from datetime import datetime

app = Flask(__name__)
DB_FILE = "swagger_specs.db"

RELATIONSHIP_TYPES = [
    "single",
    "oneOf",
    "anyOf",
    "allOf"
]


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
        "x-studio": {
            "relationships": {
                "paths": {
                    "/users": {
                        "post": {
                            "requestSchemaRelation": {
                                "type": "oneOf",
                                "items": [
                                    {"kind": "ref", "value": "#/components/schemas/CreateUserRequest"},
                                    {"kind": "ref", "value": "#/components/schemas/MinimalCreateUserRequest"}
                                ]
                            },
                            "requestExampleRelation": {
                                "type": "anyOf",
                                "items": [
                                    {"name": "createUser", "summary": "Full request", "value": {"name": "John", "email": "john@example.com"}},
                                    {"name": "minimal", "summary": "Minimal request", "value": {"name": "Jane"}}
                                ]
                            },
                            "responseSchemaRelations": {
                                "201": {
                                    "type": "single",
                                    "items": [
                                        {"kind": "ref", "value": "#/components/schemas/User"}
                                    ]
                                }
                            },
                            "responseExampleRelations": {
                                "201": {
                                    "type": "single",
                                    "items": [
                                        {"name": "created", "summary": "Created user", "value": {"id": 1, "name": "John", "email": "john@example.com"}}
                                    ]
                                }
                            }
                        }
                    }
                }
            }
        },
        "info": {
            "title": "Swagger Studio v11.2",
            "description": "Schema selection UX with dropdown and drag-drop, stable editing panels.",
            "version": "1.0.0"
        },
        "servers": [{"url": "https://api.example.com"}],
        "components": {
            "schemas": {
                "User": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "name": {"type": "string"},
                        "email": {"type": "string"}
                    }
                },
                "CreateUserRequest": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "email": {"type": "string"}
                    }
                },
                "MinimalCreateUserRequest": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"}
                    }
                },
                "ErrorResponse": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string"},
                        "code": {"type": "string"}
                    }
                }
            }
        },
        "paths": {
            "/users": {
                "post": {
                    "summary": "Create user",
                    "description": "Creates a new user.",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "oneOf": [
                                        {"$ref": "#/components/schemas/CreateUserRequest"},
                                        {"$ref": "#/components/schemas/MinimalCreateUserRequest"}
                                    ]
                                },
                                "examples": {
                                    "createUser": {
                                        "summary": "Full request",
                                        "value": {"name": "John", "email": "john@example.com"}
                                    },
                                    "minimal": {
                                        "summary": "Minimal request",
                                        "value": {"name": "Jane"}
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "201": {
                            "description": "Created",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/User"},
                                    "examples": {
                                        "created": {
                                            "summary": "Created user",
                                            "value": {"id": 1, "name": "John", "email": "john@example.com"}
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


def ensure_x_studio(spec):
    if "x-studio" not in spec or not isinstance(spec["x-studio"], dict):
        spec["x-studio"] = {}
    if "relationships" not in spec["x-studio"] or not isinstance(spec["x-studio"]["relationships"], dict):
        spec["x-studio"]["relationships"] = {}
    if "paths" not in spec["x-studio"]["relationships"] or not isinstance(spec["x-studio"]["relationships"]["paths"], dict):
        spec["x-studio"]["relationships"]["paths"] = {}
    return spec["x-studio"]["relationships"]["paths"]


def relation_template():
    return {"type": "single", "items": []}


def ensure_operation_relationships(spec, path_key, method):
    rel_paths = ensure_x_studio(spec)
    if path_key not in rel_paths or not isinstance(rel_paths[path_key], dict):
        rel_paths[path_key] = {}
    if method not in rel_paths[path_key] or not isinstance(rel_paths[path_key][method], dict):
        rel_paths[path_key][method] = {}
    op_rel = rel_paths[path_key][method]

    if "requestSchemaRelation" not in op_rel or not isinstance(op_rel["requestSchemaRelation"], dict):
        op_rel["requestSchemaRelation"] = relation_template()
    if "requestExampleRelation" not in op_rel or not isinstance(op_rel["requestExampleRelation"], dict):
        op_rel["requestExampleRelation"] = relation_template()
    if "responseSchemaRelations" not in op_rel or not isinstance(op_rel["responseSchemaRelations"], dict):
        op_rel["responseSchemaRelations"] = {}
    if "responseExampleRelations" not in op_rel or not isinstance(op_rel["responseExampleRelations"], dict):
        op_rel["responseExampleRelations"] = {}

    return op_rel


def normalize_relation_type(value):
    return value if value in RELATIONSHIP_TYPES else "single"


def schema_item_to_openapi(item):
    if not isinstance(item, dict):
        return None
    kind = item.get("kind", "inline")
    value = item.get("value")
    if kind == "ref":
        return {"$ref": value} if isinstance(value, str) and value.strip() else None
    if isinstance(value, dict):
        return value
    return None


def apply_relation_to_schema(relation):
    relation_type = normalize_relation_type((relation or {}).get("type"))
    items = (relation or {}).get("items", [])
    schemas = [schema_item_to_openapi(item) for item in items]
    schemas = [s for s in schemas if s is not None]

    if not schemas:
        return None

    if relation_type == "single":
        return schemas[0]

    if relation_type in ("oneOf", "anyOf", "allOf"):
        return {relation_type: schemas}

    return schemas[0]


def example_item_to_openapi(item):
    if not isinstance(item, dict):
        return None, None
    name = (item.get("name") or "").strip()
    if not name:
        return None, None
    return name, {
        "summary": item.get("summary", ""),
        "value": item.get("value")
    }


def apply_relation_to_examples(relation):
    items = (relation or {}).get("items", [])
    result = {}
    for item in items:
        name, obj = example_item_to_openapi(item)
        if name:
            result[name] = obj
    return result


def sync_relationships_to_openapi(spec):
    if not isinstance(spec, dict):
        return spec

    rel_paths = ensure_x_studio(spec)
    paths = spec.get("paths", {})
    if not isinstance(paths, dict):
        return spec

    for path_key, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if not isinstance(operation, dict):
                continue

            op_rel = ensure_operation_relationships(spec, path_key, method)

            request_schema = apply_relation_to_schema(op_rel.get("requestSchemaRelation"))
            request_examples = apply_relation_to_examples(op_rel.get("requestExampleRelation"))

            if request_schema or request_examples:
                if "requestBody" not in operation or not isinstance(operation["requestBody"], dict):
                    operation["requestBody"] = {"required": True, "content": {}}
                if "content" not in operation["requestBody"] or not isinstance(operation["requestBody"]["content"], dict):
                    operation["requestBody"]["content"] = {}
                if "application/json" not in operation["requestBody"]["content"] or not isinstance(operation["requestBody"]["content"]["application/json"], dict):
                    operation["requestBody"]["content"]["application/json"] = {}

                req_json = operation["requestBody"]["content"]["application/json"]
                if request_schema:
                    req_json["schema"] = request_schema
                elif "schema" in req_json:
                    del req_json["schema"]

                if request_examples:
                    req_json["examples"] = request_examples
                elif "examples" in req_json:
                    del req_json["examples"]

            response_schema_rel = op_rel.get("responseSchemaRelations", {})
            response_example_rel = op_rel.get("responseExampleRelations", {})
            responses = operation.get("responses", {})
            if not isinstance(responses, dict):
                operation["responses"] = {}
                responses = operation["responses"]

            all_codes = set(response_schema_rel.keys()) | set(response_example_rel.keys()) | set(responses.keys())

            for code in all_codes:
                if code not in responses or not isinstance(responses[code], dict):
                    responses[code] = {"description": "Response", "content": {}}
                if "content" not in responses[code] or not isinstance(responses[code]["content"], dict):
                    responses[code]["content"] = {}
                if "application/json" not in responses[code]["content"] or not isinstance(responses[code]["content"]["application/json"], dict):
                    responses[code]["content"]["application/json"] = {}

                res_json = responses[code]["content"]["application/json"]

                schema_relation = response_schema_rel.get(code, relation_template())
                example_relation = response_example_rel.get(code, relation_template())

                compiled_schema = apply_relation_to_schema(schema_relation)
                compiled_examples = apply_relation_to_examples(example_relation)

                if compiled_schema:
                    res_json["schema"] = compiled_schema
                elif "schema" in res_json:
                    del res_json["schema"]

                if compiled_examples:
                    res_json["examples"] = compiled_examples
                elif "examples" in res_json:
                    del res_json["examples"]

    return spec


@app.route("/")
def index():
    spec = default_openapi_spec()
    spec = sync_relationships_to_openapi(spec)
    yaml_text = yaml.dump(spec, sort_keys=False, allow_unicode=True)
    return render_template("index.html", initial_yaml=yaml_text, relationship_types=RELATIONSHIP_TYPES)


@app.route("/parse_spec", methods=["POST"])
def parse_spec():
    data = request.json or {}
    text = data.get("text", "")
    mode = data.get("mode", "yaml")
    try:
        parsed = json.loads(text) if mode == "json" else yaml.safe_load(text)
        if parsed is None:
            parsed = {}
        parsed = sync_relationships_to_openapi(parsed)
        return jsonify({
            "success": True,
            "json": parsed,
            "yaml": yaml.dump(parsed, sort_keys=False, allow_unicode=True),
            "relationship_types": RELATIONSHIP_TYPES
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/validate_semantic", methods=["POST"])
def validate_semantic():
    data = request.json or {}
    spec = data.get("spec", {})
    errors = []
    if not isinstance(spec, dict):
        errors.append("Root document must be an object.")
    else:
        if "openapi" not in spec:
            errors.append("Missing openapi")
        if "info" not in spec:
            errors.append("Missing info")
        if "paths" not in spec:
            errors.append("Missing paths")
    return jsonify({"success": len(errors) == 0, "errors": errors})


@app.route("/export_html", methods=["POST"])
def export_html():
    data = request.json or {}
    spec = data.get("spec", {})
    spec = sync_relationships_to_openapi(spec)
    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8" />
  <title>OpenAPI HTML Export</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist/swagger-ui.css" />
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist/swagger-ui-bundle.js"></script>
  <script>
    const spec = {json.dumps(spec)};
    SwaggerUIBundle({{
      spec: spec,
      dom_id: '#swagger-ui'
    }});
  </script>
</body>
</html>"""
    return Response(html, mimetype="text/html")


@app.route("/api/relationship_types", methods=["GET"])
def relationship_types():
    return jsonify({"types": RELATIONSHIP_TYPES})


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

    try:
        parsed = yaml.safe_load(row["yaml_text"]) or {}
        parsed = sync_relationships_to_openapi(parsed)
        yaml_text = yaml.dump(parsed, sort_keys=False, allow_unicode=True)
    except Exception:
        yaml_text = row["yaml_text"]

    return jsonify({
        "success": True,
        "spec": {
            "id": row["id"],
            "name": row["name"],
            "yaml_text": yaml_text,
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
    if not yaml_text.strip():
        return jsonify({"success": False, "error": "YAML content is required"}), 400

    parsed = yaml.safe_load(yaml_text) or {}
    parsed = sync_relationships_to_openapi(parsed)
    yaml_text = yaml.dump(parsed, sort_keys=False, allow_unicode=True)

    now = datetime.utcnow().isoformat()
    conn = get_db_connection()
    cur = conn.execute("""
        INSERT INTO specs (name, yaml_text, created_at, updated_at)
        VALUES (?, ?, ?, ?)
    """, (name, yaml_text, now, now))
    conn.commit()
    new_id = cur.lastrowid
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
    if not yaml_text.strip():
        return jsonify({"success": False, "error": "YAML content is required"}), 400

    parsed = yaml.safe_load(yaml_text) or {}
    parsed = sync_relationships_to_openapi(parsed)
    yaml_text = yaml.dump(parsed, sort_keys=False, allow_unicode=True)

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
    app.run(debug=True, host="0.0.0.0", port=5000)
'''

INDEX_HTML = r'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Swagger Studio v11.2</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist/swagger-ui.css" />
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body class="studio-body">
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark border-bottom shadow-sm">
        <div class="container-fluid">
            <a class="navbar-brand fw-bold" href="#">Swagger Studio v11.2</a>
            <div class="d-flex align-items-center gap-2 flex-wrap">
                <button class="btn btn-outline-light btn-sm" onclick="togglePanel('left-panel')">Tree</button>
                <button class="btn btn-outline-light btn-sm" onclick="togglePanel('design-panel')">Design</button>
                <button class="btn btn-outline-light btn-sm" onclick="togglePanel('raw-panel')">Raw</button>
                <button class="btn btn-outline-light btn-sm" onclick="togglePanel('preview-panel')">Preview</button>
                <span class="badge text-bg-secondary" id="parse-status">Syntax: Unknown</span>
                <span class="badge text-bg-secondary" id="semantic-status">Semantic: Unknown</span>
                <button class="btn btn-outline-warning btn-sm" onclick="toggleTheme()" id="theme-toggle-btn">Theme</button>
            </div>
        </div>
    </nav>

    <div class="container-fluid py-2 border-bottom bg-body-tertiary">
        <div class="row g-2 align-items-center">
            <div class="col-lg-8">
                <div class="d-flex flex-wrap gap-2">
                    <input type="hidden" id="current-spec-id">
                    <input type="text" id="spec-name" class="form-control form-control-sm studio-inline-input" placeholder="Specification name">
                    <button class="btn btn-primary btn-sm" onclick="saveAsNewSpec()">Save As New</button>
                    <button class="btn btn-success btn-sm" onclick="updateCurrentSpec()">Update</button>
                    <button class="btn btn-danger btn-sm" onclick="deleteCurrentSpec()">Delete</button>
                </div>
            </div>
            <div class="col-lg-4">
                <div class="d-flex flex-wrap justify-content-lg-end gap-2">
                    <button class="btn btn-outline-secondary btn-sm" onclick="triggerImport()">Import</button>
                    <button class="btn btn-outline-secondary btn-sm" onclick="downloadCurrentYaml()">YAML</button>
                    <button class="btn btn-outline-secondary btn-sm" onclick="downloadCurrentJson()">JSON</button>
                    <button class="btn btn-outline-secondary btn-sm" onclick="downloadHtmlDocs()">HTML</button>
                    <input type="file" id="file-import" accept=".yaml,.yml,.json" hidden>
                </div>
            </div>
        </div>
    </div>

    <div class="workspace" id="workspace">
        <aside class="studio-panel left-panel" id="left-panel">
            <div class="studio-panel-inner">
                <div class="card h-100 border-0 shadow-sm">
                    <div class="card-header bg-primary-subtle fw-semibold">Tree</div>
                    <div class="card-body panel-scroll">
                        <div class="accordion" id="leftAccordion">
                            <div class="accordion-item">
                                <h2 class="accordion-header">
                                    <button class="accordion-button" type="button" data-bs-toggle="collapse" data-bs-target="#storedSpecsCollapse">
                                        Stored Specs
                                    </button>
                                </h2>
                                <div id="storedSpecsCollapse" class="accordion-collapse collapse show">
                                    <div class="accordion-body">
                                        <input type="text" id="spec-search" class="form-control form-control-sm mb-2" placeholder="Search specs by name...">
                                        <div id="spec-list" class="list-group small"></div>
                                    </div>
                                </div>
                            </div>

                            <div class="accordion-item">
                                <h2 class="accordion-header">
                                    <button class="accordion-button" type="button" data-bs-toggle="collapse" data-bs-target="#structureCollapse">
                                        Structure
                                    </button>
                                </h2>
                                <div id="structureCollapse" class="accordion-collapse collapse show">
                                    <div class="accordion-body">
                                        <div id="tree-list" class="list-group small"></div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </aside>

        <div class="splitter" id="splitter-left-tree-design"></div>

        <main class="studio-panel design-panel" id="design-panel">
            <div class="studio-panel-inner">
                <div class="card h-100 border-0 shadow-sm">
                    <div class="card-header d-flex justify-content-between align-items-center bg-info-subtle">
                        <div>
                            <div class="fw-semibold">Design Editor</div>
                            <div class="small text-muted">Existing schema selection, drag-drop and stable edit panels</div>
                        </div>
                    </div>
                    <div class="card-body panel-scroll">
                        <div class="d-flex flex-wrap gap-2 mb-3">
                            <button class="btn btn-primary btn-sm" onclick="addPath()">Add Path</button>
                            <button class="btn btn-outline-primary btn-sm" onclick="addSchema()">Add Schema</button>
                            <button class="btn btn-outline-primary btn-sm" onclick="addServer()">Add Server</button>
                            <button class="btn btn-outline-secondary btn-sm" onclick="openInfoEditor()">Edit Info</button>
                        </div>
                        <div id="editable-canvas" class="d-flex flex-column gap-3"></div>
                    </div>
                </div>
            </div>
        </main>

        <div class="splitter" id="splitter-design-raw"></div>

        <section class="studio-panel raw-panel" id="raw-panel">
            <div class="studio-panel-inner">
                <div class="card h-100 border-0 shadow-sm">
                    <div class="card-header d-flex justify-content-between align-items-center bg-warning-subtle">
                        <div>
                            <div class="fw-semibold">Raw Content</div>
                            <div class="small text-muted">View YAML / JSON while editing design</div>
                        </div>
                    </div>
                    <div class="card-body panel-scroll">
                        <div class="d-flex flex-wrap gap-2 mb-3">
                            <div class="btn-group btn-group-sm" role="group">
                                <button id="view-yaml-btn" class="btn btn-outline-secondary active" onclick="setEditorMode('yaml')">YAML</button>
                                <button id="view-json-btn" class="btn btn-outline-secondary" onclick="setEditorMode('json')">JSON</button>
                            </div>
                            <button class="btn btn-outline-secondary btn-sm" onclick="formatEditorContent()">Format</button>
                        </div>
                        <div id="yaml-editor"></div>
                    </div>
                </div>
            </div>
        </section>

        <div class="splitter" id="splitter-raw-preview"></div>

        <section class="studio-panel preview-panel" id="preview-panel">
            <div class="studio-panel-inner">
                <div class="card h-100 border-0 shadow-sm">
                    <div class="card-header bg-success-subtle">
                        <div class="fw-semibold">Live Preview</div>
                        <div class="small text-muted">Always visible while editing</div>
                    </div>
                    <div class="card-body panel-scroll p-2">
                        <div id="swagger-ui"></div>
                    </div>
                </div>
            </div>
        </section>
    </div>

    <div class="modal fade" id="editorModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-xl modal-dialog-centered modal-dialog-scrollable">
            <div class="modal-content">
                <div class="modal-header sticky-top bg-body">
                    <div>
                        <h5 class="modal-title mb-0" id="editorModalTitle">Edit</h5>
                        <div class="small text-muted" id="editorModalSubtitle">Manage related information and properties</div>
                    </div>
                    <button type="button" class="btn-close" onclick="closeMainModal()"></button>
                </div>
                <div class="modal-body" id="editorModalBody"></div>
                <div class="modal-footer sticky-bottom bg-body">
                    <button type="button" class="btn btn-secondary" onclick="closeMainModal()">Close</button>
                </div>
            </div>
        </div>
    </div>

    <div class="modal fade" id="relationshipItemModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-lg modal-dialog-centered modal-dialog-scrollable">
            <div class="modal-content">
                <div class="modal-header sticky-top bg-body">
                    <div>
                        <h5 class="modal-title mb-0" id="relationshipItemModalTitle">Relationship Item</h5>
                        <div class="small text-muted" id="relationshipItemModalSubtitle">Add or edit schema/example relationship item</div>
                    </div>
                    <button type="button" class="btn-close" onclick="closeRelationshipItemModal()"></button>
                </div>
                <div class="modal-body" id="relationshipItemModalBody"></div>
                <div class="modal-footer sticky-bottom bg-body">
                    <button type="button" class="btn btn-secondary" onclick="closeRelationshipItemModal()">Cancel</button>
                    <button type="button" class="btn btn-primary" onclick="saveRelationshipItemModal()">Save</button>
                </div>
            </div>
        </div>
    </div>

    <script>
        window.INITIAL_YAML = {{ initial_yaml|tojson }};
        window.RELATIONSHIP_TYPES = {{ relationship_types|tojson }};
    </script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/js-yaml@4.1.0/dist/js-yaml.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist/swagger-ui-bundle.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.45.0/min/vs/loader.min.js"></script>
    <script src="{{ url_for('static', filename='app.js') }}"></script>
</body>
</html>
'''

STYLE_CSS = r'''html, body {
    height: 100%;
    overflow: hidden;
}

.studio-body {
    background: #f5f7fb;
}

.workspace {
    display: flex;
    height: calc(100vh - 106px);
    min-height: 0;
    min-width: 0;
    overflow: hidden;
}

.studio-panel {
    min-width: 0;
    min-height: 0;
    overflow: hidden;
}

.studio-panel-inner {
    height: 100%;
    padding: 10px;
}

.left-panel { width: 18%; min-width: 220px; }
.design-panel { width: 35%; min-width: 320px; }
.raw-panel { width: 19%; min-width: 260px; }
.preview-panel { width: 28%; min-width: 280px; }

.splitter {
    width: 8px;
    cursor: col-resize;
    background: linear-gradient(to right, transparent, rgba(0,0,0,0.08), transparent);
}

.splitter.hidden,
.hidden {
    display: none !important;
}

.panel-scroll {
    overflow: auto;
    min-height: 0;
    height: 100%;
}

#yaml-editor {
    width: 100%;
    height: calc(100vh - 265px);
    min-height: 450px;
    border: 1px solid #dee2e6;
    border-radius: 0.5rem;
    overflow: hidden;
}

#swagger-ui {
    min-height: calc(100vh - 250px);
    background: #fff;
    border-radius: 0.5rem;
}

.studio-inline-input {
    width: 280px;
    max-width: 100%;
}

.pre-json {
    white-space: pre-wrap;
    word-break: break-word;
    font-size: 0.8rem;
    background: #f8f9fa;
    border: 1px solid #e9ecef;
    border-radius: 0.5rem;
    padding: 0.75rem;
    max-height: 220px;
    overflow: auto;
}

.rel-box {
    border: 1px solid #dee2e6;
    border-radius: 0.5rem;
    padding: 0.75rem;
    background: #fff;
}

.large-textarea {
    min-height: 260px;
    max-height: 420px;
    overflow: auto;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    white-space: pre;
}

.schema-drop-zone {
    border: 2px dashed #6c757d;
    border-radius: 0.75rem;
    padding: 1rem;
    text-align: center;
    background: #f8f9fa;
    transition: all 0.2s ease;
}

.schema-drop-zone.drag-over {
    border-color: #0d6efd;
    background: #e7f1ff;
}

.schema-chip {
    display: inline-block;
    padding: 0.35rem 0.6rem;
    border-radius: 999px;
    background: #eef2ff;
    border: 1px solid #c7d2fe;
    cursor: grab;
    margin: 0.25rem;
    font-size: 0.85rem;
}

.schema-chip:hover {
    background: #dbeafe;
}

body.dark-theme {
    background: #0f172a;
    color: #e5e7eb;
}

body.dark-theme .navbar,
body.dark-theme .bg-body-tertiary {
    background-color: #111827 !important;
    color: #e5e7eb;
}

body.dark-theme .card,
body.dark-theme .modal-content,
body.dark-theme .accordion-item {
    background: #111827;
    color: #e5e7eb;
}

body.dark-theme .card-header,
body.dark-theme .modal-header,
body.dark-theme .modal-footer,
body.dark-theme .accordion-button {
    background: #172033 !important;
    color: #e5e7eb;
}

body.dark-theme .form-control,
body.dark-theme .form-select,
body.dark-theme textarea {
    background: #0b1220;
    color: #e5e7eb;
    border-color: #334155;
}

body.dark-theme .pre-json,
body.dark-theme .rel-box,
body.dark-theme .schema-drop-zone {
    background: #0b1220;
    border-color: #334155;
    color: #e5e7eb;
}

body.dark-theme .schema-chip {
    background: #1e293b;
    border-color: #334155;
    color: #e5e7eb;
}

body.dark-theme .schema-drop-zone.drag-over {
    background: #10243f;
    border-color: #60a5fa;
}

body.dark-theme #swagger-ui {
    background: #fff;
}
'''

APP_JS = r'''let swaggerUiInstance = null;
let editorMode = "yaml";
let monacoEditor = null;
let isUpdatingEditorProgrammatically = false;
let currentSpec = null;
let editorModal = null;
let relationshipItemModal = null;
let currentOperationContext = null;
let relationshipItemContext = null;
let REL_TYPES = window.RELATIONSHIP_TYPES || ["single", "oneOf", "anyOf", "allOf"];

/* ---------------- Theme ---------------- */

function applyTheme(theme) {
    document.body.classList.toggle("dark-theme", theme === "dark");
    localStorage.setItem("swagger-studio-theme", theme);
    const btn = document.getElementById("theme-toggle-btn");
    if (btn) btn.textContent = theme === "dark" ? "Light" : "Dark";
    if (window.monaco && monacoEditor) {
        monaco.editor.setTheme(theme === "dark" ? "vs-dark" : "vs");
    }
}

function toggleTheme() {
    const current = document.body.classList.contains("dark-theme") ? "dark" : "light";
    applyTheme(current === "dark" ? "light" : "dark");
}

/* ---------------- Monaco ---------------- */

function initMonacoEditor(initialText = "") {
    require.config({
        paths: { vs: "https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.45.0/min/vs" }
    });

    require(["vs/editor/editor.main"], function () {
        monacoEditor = monaco.editor.create(document.getElementById("yaml-editor"), {
            value: initialText,
            language: "yaml",
            theme: document.body.classList.contains("dark-theme") ? "vs-dark" : "vs",
            automaticLayout: true,
            minimap: { enabled: false },
            fontSize: 13,
            wordWrap: "on",
            scrollBeyondLastLine: false,
            lineNumbers: "on",
            tabSize: 2,
            insertSpaces: true
        });

        monacoEditor.onDidChangeModelContent(() => {
            if (isUpdatingEditorProgrammatically) return;
            debouncedSyncFromRaw();
        });
    });
}

function getEditorText() {
    return monacoEditor ? monacoEditor.getValue() : "";
}

function setEditorText(text) {
    if (!monacoEditor) return;
    const next = text || "";
    if (monacoEditor.getValue() === next) return;
    isUpdatingEditorProgrammatically = true;
    monacoEditor.setValue(next);
    clearEditorMarkers();
    setTimeout(() => { isUpdatingEditorProgrammatically = false; }, 0);
}

function setEditorLanguage(mode) {
    if (!monacoEditor || !window.monaco) return;
    const model = monacoEditor.getModel();
    if (!model) return;
    monaco.editor.setModelLanguage(model, mode === "json" ? "json" : "yaml");
}

function updateEditorModeUi() {
    const yamlBtn = document.getElementById("view-yaml-btn");
    const jsonBtn = document.getElementById("view-json-btn");
    if (yamlBtn) yamlBtn.classList.toggle("active", editorMode === "yaml");
    if (jsonBtn) jsonBtn.classList.toggle("active", editorMode === "json");
    setEditorLanguage(editorMode);
}

function clearEditorMarkers() {
    if (!window.monaco || !monacoEditor) return;
    const model = monacoEditor.getModel();
    if (!model) return;
    monaco.editor.setModelMarkers(model, "swagger-studio", []);
}

function setEditorErrorMarker(message) {
    if (!window.monaco || !monacoEditor) return;
    const model = monacoEditor.getModel();
    if (!model) return;
    monaco.editor.setModelMarkers(model, "swagger-studio", [{
        severity: monaco.MarkerSeverity.Error,
        message,
        startLineNumber: 1,
        startColumn: 1,
        endLineNumber: 1,
        endColumn: 2
    }]);
}

/* ---------------- Helpers ---------------- */

function debounce(func, wait) {
    let timeout;
    return function () {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, arguments), wait);
    };
}

function escapeHtml(str) {
    return String(str ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function parseEditorContent(text) {
    if (!text.trim()) return {};
    return editorMode === "json" ? JSON.parse(text) : jsyaml.load(text);
}

function specToYaml(spec) {
    return jsyaml.dump(spec, { noRefs: true, lineWidth: -1 });
}

function setStatus(message, ok = true) {
    const el = document.getElementById("parse-status");
    if (!el) return;
    el.textContent = message;
    el.className = `badge ${ok ? "text-bg-success" : "text-bg-danger"}`;
}

function setSemanticStatus(message, ok = true) {
    const el = document.getElementById("semantic-status");
    if (!el) return;
    el.textContent = message;
    el.className = `badge ${ok ? "text-bg-success" : "text-bg-danger"}`;
}

function slugify(text) {
    return String(text).replace(/[^a-zA-Z0-9]+/g, "-");
}

function deepClone(obj) {
    return JSON.parse(JSON.stringify(obj));
}

function ensurePaths() {
    if (!currentSpec.paths) currentSpec.paths = {};
}

function ensureComponents() {
    if (!currentSpec.components) currentSpec.components = {};
    if (!currentSpec.components.schemas) currentSpec.components.schemas = {};
}

function getSchemaNames() {
    ensureComponents();
    return Object.keys(currentSpec.components.schemas || {});
}

function ensureXPathRelationships() {
    if (!currentSpec["x-studio"]) currentSpec["x-studio"] = {};
    if (!currentSpec["x-studio"]["relationships"]) currentSpec["x-studio"]["relationships"] = {};
    if (!currentSpec["x-studio"]["relationships"]["paths"]) currentSpec["x-studio"]["relationships"]["paths"] = {};
    return currentSpec["x-studio"]["relationships"]["paths"];
}

function ensurePathOperation(pathKey, method) {
    ensurePaths();
    if (!currentSpec.paths[pathKey]) currentSpec.paths[pathKey] = {};
    if (!currentSpec.paths[pathKey][method]) {
        currentSpec.paths[pathKey][method] = {
            summary: "",
            description: "",
            parameters: [],
            responses: { "200": { description: "OK", content: { "application/json": {} } } }
        };
    }
    if (!currentSpec.paths[pathKey][method].parameters) currentSpec.paths[pathKey][method].parameters = [];
    if (!currentSpec.paths[pathKey][method].responses) currentSpec.paths[pathKey][method].responses = {};
    return currentSpec.paths[pathKey][method];
}

function relationTemplate() {
    return { type: "single", items: [] };
}

function ensureOperationRelationships(pathKey, method) {
    const relPaths = ensureXPathRelationships();
    if (!relPaths[pathKey]) relPaths[pathKey] = {};
    if (!relPaths[pathKey][method]) relPaths[pathKey][method] = {};
    const opRel = relPaths[pathKey][method];
    if (!opRel.requestSchemaRelation) opRel.requestSchemaRelation = relationTemplate();
    if (!opRel.requestExampleRelation) opRel.requestExampleRelation = relationTemplate();
    if (!opRel.responseSchemaRelations) opRel.responseSchemaRelations = {};
    if (!opRel.responseExampleRelations) opRel.responseExampleRelations = {};
    return opRel;
}

function ensureResponseSchemaRelation(pathKey, method, code) {
    const opRel = ensureOperationRelationships(pathKey, method);
    if (!opRel.responseSchemaRelations[code]) opRel.responseSchemaRelations[code] = relationTemplate();
    return opRel.responseSchemaRelations[code];
}

function ensureResponseExampleRelation(pathKey, method, code) {
    const opRel = ensureOperationRelationships(pathKey, method);
    if (!opRel.responseExampleRelations[code]) opRel.responseExampleRelations[code] = relationTemplate();
    return opRel.responseExampleRelations[code];
}

function compileSchemaItem(item) {
    if (!item || typeof item !== "object") return null;
    if (item.kind === "ref") {
        if (!item.value) return null;
        return { "$ref": item.value };
    }
    return item.value || null;
}

function compileSchemaRelation(relation) {
    relation = relation || relationTemplate();
    const type = REL_TYPES.includes(relation.type) ? relation.type : "single";
    const items = (relation.items || []).map(compileSchemaItem).filter(Boolean);
    if (!items.length) return null;
    if (type === "single") return items[0];
    if (type === "oneOf" || type === "anyOf" || type === "allOf") return { [type]: items };
    return items[0];
}

function compileExampleRelation(relation) {
    relation = relation || relationTemplate();
    const result = {};
    (relation.items || []).forEach(item => {
        if (item && item.name) {
            result[item.name] = {
                summary: item.summary || "",
                value: item.value
            };
        }
    });
    return Object.keys(result).length ? result : null;
}

function syncOpenApiFromRelationships() {
    const relPaths = ensureXPathRelationships();
    Object.keys(currentSpec.paths || {}).forEach(pathKey => {
        Object.keys(currentSpec.paths[pathKey] || {}).forEach(method => {
            const op = ensurePathOperation(pathKey, method);
            const opRel = ensureOperationRelationships(pathKey, method);

            const reqSchema = compileSchemaRelation(opRel.requestSchemaRelation);
            const reqExamples = compileExampleRelation(opRel.requestExampleRelation);

            if (reqSchema || reqExamples) {
                if (!op.requestBody) op.requestBody = { required: true, content: {} };
                if (!op.requestBody.content) op.requestBody.content = {};
                if (!op.requestBody.content["application/json"]) op.requestBody.content["application/json"] = {};
                const reqJson = op.requestBody.content["application/json"];
                if (reqSchema) reqJson.schema = reqSchema;
                else delete reqJson.schema;
                if (reqExamples) reqJson.examples = reqExamples;
                else delete reqJson.examples;
            }

            const allCodes = new Set([
                ...Object.keys(op.responses || {}),
                ...Object.keys(opRel.responseSchemaRelations || {}),
                ...Object.keys(opRel.responseExampleRelations || {})
            ]);

            allCodes.forEach(code => {
                if (!op.responses[code]) op.responses[code] = { description: "Response", content: {} };
                if (!op.responses[code].content) op.responses[code].content = {};
                if (!op.responses[code].content["application/json"]) op.responses[code].content["application/json"] = {};
                const resJson = op.responses[code].content["application/json"];
                const resSchema = compileSchemaRelation(ensureResponseSchemaRelation(pathKey, method, code));
                const resExamples = compileExampleRelation(ensureResponseExampleRelation(pathKey, method, code));
                if (resSchema) resJson.schema = resSchema;
                else delete resJson.schema;
                if (resExamples) resJson.examples = resExamples;
                else delete resJson.examples;
            });
        });
    });
}

function syncRawEditorFromSpec() {
    syncOpenApiFromRelationships();
    if (editorMode === "json") setEditorText(JSON.stringify(currentSpec, null, 2));
    else setEditorText(specToYaml(currentSpec));
}

function syncSpecFromRawEditor() {
    currentSpec = parseEditorContent(getEditorText()) || {};
    syncOpenApiFromRelationships();
}

function downloadTextFile(filename, content, mimeType) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
}

function getDownloadBaseName() {
    const rawName = document.getElementById("spec-name")?.value?.trim() || "openapi-spec";
    return rawName.replace(/[^a-zA-Z0-9-_]+/g, "_");
}

/* ---------------- Layout ---------------- */

function togglePanel(panelId) {
    const panel = document.getElementById(panelId);
    if (!panel) return;
    panel.classList.toggle("hidden");
    updateSplitterVisibility();
    normalizeVisiblePanelWidths();
}

function updateSplitterVisibility() {
    const left = document.getElementById("left-panel");
    const design = document.getElementById("design-panel");
    const raw = document.getElementById("raw-panel");
    const preview = document.getElementById("preview-panel");

    document.getElementById("splitter-left-tree-design")?.classList.toggle("hidden", left.classList.contains("hidden") || design.classList.contains("hidden"));
    document.getElementById("splitter-design-raw")?.classList.toggle("hidden", design.classList.contains("hidden") || raw.classList.contains("hidden"));
    document.getElementById("splitter-raw-preview")?.classList.toggle("hidden", raw.classList.contains("hidden") || preview.classList.contains("hidden"));
}

function normalizeVisiblePanelWidths() {
    const panels = [
        document.getElementById("left-panel"),
        document.getElementById("design-panel"),
        document.getElementById("raw-panel"),
        document.getElementById("preview-panel")
    ].filter(Boolean).filter(p => !p.classList.contains("hidden"));

    if (!panels.length) return;
    const width = `${100 / panels.length}%`;
    panels.forEach(p => p.style.width = width);
}

function initResizablePanels() {
    const workspace = document.getElementById("workspace");
    const left = document.getElementById("left-panel");
    const design = document.getElementById("design-panel");
    const raw = document.getElementById("raw-panel");
    const preview = document.getElementById("preview-panel");

    const splitter1 = document.getElementById("splitter-left-tree-design");
    const splitter2 = document.getElementById("splitter-design-raw");
    const splitter3 = document.getElementById("splitter-raw-preview");

    let activeSplitter = null;

    function percent(n, total) {
        return (n / total) * 100;
    }

    function onMouseMove(e) {
        if (!activeSplitter || !workspace) return;
        const rect = workspace.getBoundingClientRect();
        const total = rect.width;
        const x = e.clientX - rect.left;

        const leftVisible = !left.classList.contains("hidden");
        const designVisible = !design.classList.contains("hidden");
        const rawVisible = !raw.classList.contains("hidden");
        const previewVisible = !preview.classList.contains("hidden");

        const leftW = leftVisible ? parseFloat(left.style.width || "18") : 0;
        const designW = designVisible ? parseFloat(design.style.width || "35") : 0;
        const rawW = rawVisible ? parseFloat(raw.style.width || "19") : 0;
        const previewW = previewVisible ? parseFloat(preview.style.width || "28") : 0;

        if (activeSplitter === splitter1 && leftVisible && designVisible) {
            let newLeft = percent(x, total);
            if (newLeft < 12) newLeft = 12;
            if (newLeft > 35) newLeft = 35;
            const remaining = 100 - rawW - previewW;
            const newDesign = remaining - newLeft;
            if (newDesign < 18) return;
            left.style.width = `${newLeft}%`;
            design.style.width = `${newDesign}%`;
        }

        if (activeSplitter === splitter2 && designVisible && rawVisible) {
            const before = leftVisible ? leftW : 0;
            let newDesign = percent(x, total) - before;
            if (newDesign < 18) newDesign = 18;
            if (newDesign > 60) newDesign = 60;
            const newRaw = 100 - before - previewW - newDesign;
            if (newRaw < 15) return;
            design.style.width = `${newDesign}%`;
            raw.style.width = `${newRaw}%`;
        }

        if (activeSplitter === splitter3 && rawVisible && previewVisible) {
            const before = (leftVisible ? leftW : 0) + (designVisible ? designW : 0);
            let newRaw = percent(x, total) - before;
            if (newRaw < 15) newRaw = 15;
            if (newRaw > 45) newRaw = 45;
            const newPreview = 100 - before - newRaw;
            if (newPreview < 18) return;
            raw.style.width = `${newRaw}%`;
            preview.style.width = `${newPreview}%`;
        }
    }

    function onMouseUp() {
        activeSplitter = null;
        document.body.style.cursor = "default";
        document.body.style.userSelect = "auto";
    }

    [splitter1, splitter2, splitter3].forEach(splitter => {
        splitter?.addEventListener("mousedown", () => {
            activeSplitter = splitter;
            document.body.style.cursor = "col-resize";
            document.body.style.userSelect = "none";
        });
    });

    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
}

/* ---------------- Preview ---------------- */

function initSwaggerUI(spec) {
    const el = document.getElementById("swagger-ui");
    if (!el) return;
    el.innerHTML = "";
    swaggerUiInstance = SwaggerUIBundle({
        spec,
        dom_id: "#swagger-ui"
    });
}

async function runSemanticValidation(spec) {
    try {
        const response = await fetch("/validate_semantic", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ spec })
        });
        const result = await response.json();
        setSemanticStatus(result.success ? "Semantic: Valid" : "Semantic: Invalid", result.success);
    } catch {
        setSemanticStatus("Semantic: Error", false);
    }
}

/* ---------------- Tree ---------------- */

function renderTree() {
    const container = document.getElementById("tree-list");
    if (!container) return;
    container.innerHTML = "";

    container.insertAdjacentHTML("beforeend", `<button type="button" class="list-group-item list-group-item-action" onclick="openInfoEditor()"><strong>Info</strong></button>`);

    (currentSpec?.servers || []).forEach((server, index) => {
        container.insertAdjacentHTML("beforeend", `<button type="button" class="list-group-item list-group-item-action" onclick="openServerEditor(${index})">Server ${index + 1}: ${escapeHtml(server.url || "")}</button>`);
    });

    const paths = currentSpec?.paths || {};
    Object.keys(paths).forEach(pathKey => {
        container.insertAdjacentHTML("beforeend", `<button type="button" class="list-group-item list-group-item-action" onclick='openPathEditor(${JSON.stringify(pathKey)})'><strong>${escapeHtml(pathKey)}</strong></button>`);
        Object.keys(paths[pathKey] || {}).forEach(method => {
            const op = paths[pathKey][method] || {};
            container.insertAdjacentHTML("beforeend", `<button type="button" class="list-group-item list-group-item-action ps-4" onclick='openOperationEditor(${JSON.stringify(pathKey)}, ${JSON.stringify(method)})'>${escapeHtml(method.toUpperCase())} — ${escapeHtml(op.summary || "")}</button>`);
        });
    });

    const schemas = currentSpec?.components?.schemas || {};
    Object.keys(schemas).forEach(name => {
        container.insertAdjacentHTML("beforeend", `<button type="button" class="list-group-item list-group-item-action" onclick='openSchemaEditor(${JSON.stringify(name)})'>Schema: ${escapeHtml(name)}</button>`);
    });
}

/* ---------------- Design Canvas ---------------- */

function renderEditableCanvas() {
    const container = document.getElementById("editable-canvas");
    if (!container) return;
    container.innerHTML = "";

    container.appendChild(renderInfoCard());
    container.appendChild(renderServersCard());

    const paths = currentSpec?.paths || {};
    Object.keys(paths).forEach(pathKey => {
        container.appendChild(renderPathCard(pathKey, paths[pathKey]));
    });

    container.appendChild(renderSchemasCard());
}

function renderInfoCard() {
    const card = document.createElement("div");
    card.className = "card shadow-sm";
    const info = currentSpec?.info || {};
    card.innerHTML = `
        <div class="card-header d-flex justify-content-between align-items-center">
            <button class="btn btn-link text-decoration-none p-0 fw-bold" type="button" data-bs-toggle="collapse" data-bs-target="#infoCardCollapse">
                API Info
            </button>
            <button class="btn btn-sm btn-primary" onclick="openInfoEditor()">Edit</button>
        </div>
        <div id="infoCardCollapse" class="collapse show">
            <div class="card-body">
                <div><strong>Title:</strong> ${escapeHtml(info.title || "")}</div>
                <div><strong>Description:</strong> ${escapeHtml(info.description || "")}</div>
                <div><strong>Version:</strong> ${escapeHtml(info.version || "")}</div>
            </div>
        </div>
    `;
    return card;
}

function renderServersCard() {
    const card = document.createElement("div");
    card.className = "card shadow-sm";
    const servers = currentSpec?.servers || [];
    card.innerHTML = `
        <div class="card-header d-flex justify-content-between align-items-center">
            <button class="btn btn-link text-decoration-none p-0 fw-bold" type="button" data-bs-toggle="collapse" data-bs-target="#serversCardCollapse">
                Servers
            </button>
            <button class="btn btn-sm btn-outline-primary" onclick="addServer()">Add</button>
        </div>
        <div id="serversCardCollapse" class="collapse show">
            <div class="card-body">
                ${servers.length ? servers.map((s, i) => `
                    <div class="accordion mb-2">
                        <div class="accordion-item">
                            <h2 class="accordion-header">
                                <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#serverCollapse${i}">
                                    Server ${i + 1}: ${escapeHtml(s.url || "")}
                                </button>
                            </h2>
                            <div id="serverCollapse${i}" class="accordion-collapse collapse">
                                <div class="accordion-body">
                                    <div class="mb-2">${escapeHtml(s.url || "")}</div>
                                    <div class="d-flex gap-2">
                                        <button class="btn btn-sm btn-primary" onclick="openServerEditor(${i})">Edit</button>
                                        <button class="btn btn-sm btn-danger" onclick="deleteServer(${i})">Delete</button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                `).join("") : "<div class='text-muted'>No servers</div>"}
            </div>
        </div>
    `;
    return card;
}

function renderPathCard(pathKey, pathObj) {
    const card = document.createElement("div");
    card.className = "card shadow-sm";
    card.innerHTML = `
        <div class="card-header d-flex justify-content-between align-items-center">
            <button class="btn btn-link text-decoration-none p-0 fw-bold" type="button" data-bs-toggle="collapse" data-bs-target="#pathCollapse${slugify(pathKey)}">
                ${escapeHtml(pathKey)}
            </button>
            <div class="d-flex gap-2">
                <button class="btn btn-sm btn-primary" onclick='openPathEditor(${JSON.stringify(pathKey)})'>Edit</button>
                <button class="btn btn-sm btn-outline-primary" onclick='addOperation(${JSON.stringify(pathKey)})'>Add Operation</button>
                <button class="btn btn-sm btn-danger" onclick='deletePath(${JSON.stringify(pathKey)})'>Delete</button>
            </div>
        </div>
        <div id="pathCollapse${slugify(pathKey)}" class="collapse show">
            <div class="card-body">
                ${Object.keys(pathObj || {}).length ? Object.keys(pathObj).map((method, index) => {
                    const op = pathObj[method] || {};
                    const opId = `op-${slugify(pathKey)}-${method}-${index}`;
                    const rel = ensureOperationRelationships(pathKey, method);
                    const reqSchemaCount = (rel.requestSchemaRelation?.items || []).length;
                    const reqExampleCount = (rel.requestExampleRelation?.items || []).length;
                    const resSchemaCount = Object.values(rel.responseSchemaRelations || {}).reduce((a, r) => a + ((r?.items || []).length), 0);
                    const resExampleCount = Object.values(rel.responseExampleRelations || {}).reduce((a, r) => a + ((r?.items || []).length), 0);
                    return `
                        <div class="accordion mb-2">
                            <div class="accordion-item">
                                <h2 class="accordion-header">
                                    <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#${opId}-collapse">
                                        ${escapeHtml(method.toUpperCase())} — ${escapeHtml(op.summary || "Untitled operation")}
                                    </button>
                                </h2>
                                <div id="${opId}-collapse" class="accordion-collapse collapse">
                                    <div class="accordion-body">
                                        <div class="small text-muted mb-2">${escapeHtml(op.description || "")}</div>
                                        <div class="mb-2">
                                            <strong>Request Schemas:</strong> ${reqSchemaCount}
                                            <br>
                                            <strong>Request Examples:</strong> ${reqExampleCount}
                                            <br>
                                            <strong>Response Schemas:</strong> ${resSchemaCount}
                                            <br>
                                            <strong>Response Examples:</strong> ${resExampleCount}
                                        </div>
                                        <div class="d-flex gap-2">
                                            <button class="btn btn-sm btn-primary" onclick='openOperationEditor(${JSON.stringify(pathKey)}, ${JSON.stringify(method)})'>Edit</button>
                                            <button class="btn btn-sm btn-danger" onclick='deleteOperation(${JSON.stringify(pathKey)}, ${JSON.stringify(method)})'>Delete</button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    `;
                }).join("") : "<div class='text-muted'>No operations</div>"}
            </div>
        </div>
    `;
    return card;
}

function renderSchemasCard() {
    ensureComponents();
    const card = document.createElement("div");
    card.className = "card shadow-sm";
    const schemas = currentSpec.components.schemas || {};
    card.innerHTML = `
        <div class="card-header d-flex justify-content-between align-items-center">
            <button class="btn btn-link text-decoration-none p-0 fw-bold" type="button" data-bs-toggle="collapse" data-bs-target="#schemasCardCollapse">
                Schemas
            </button>
            <button class="btn btn-sm btn-outline-primary" onclick="addSchema()">Add Schema</button>
        </div>
        <div id="schemasCardCollapse" class="collapse show">
            <div class="card-body">
                ${Object.keys(schemas).length ? Object.keys(schemas).map((name, i) => `
                    <div class="accordion mb-2">
                        <div class="accordion-item">
                            <h2 class="accordion-header">
                                <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#schemaCollapse${i}">
                                    ${escapeHtml(name)} (${escapeHtml(schemas[name]?.type || "object")})
                                </button>
                            </h2>
                            <div id="schemaCollapse${i}" class="accordion-collapse collapse">
                                <div class="accordion-body">
                                    <div class="small text-muted mb-2">Properties: ${Object.keys(schemas[name]?.properties || {}).length}</div>
                                    <div class="pre-json mb-2">${escapeHtml(JSON.stringify(schemas[name] || {}, null, 2))}</div>
                                    <div class="d-flex gap-2">
                                        <button class="btn btn-sm btn-primary" onclick='openSchemaEditor(${JSON.stringify(name)})'>Edit</button>
                                        <button class="btn btn-sm btn-danger" onclick='deleteSchema(${JSON.stringify(name)})'>Delete</button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                `).join("") : "<div class='text-muted'>No schemas</div>"}
            </div>
        </div>
    `;
    return card;
}

/* ---------------- Modal helpers ---------------- */

function openModalEditor(title, subtitle, html) {
    document.getElementById("editorModalTitle").textContent = title;
    document.getElementById("editorModalSubtitle").textContent = subtitle || "";
    document.getElementById("editorModalBody").innerHTML = html;
    editorModal.show();
}

function closeMainModal() {
    editorModal.hide();
}

function openRelationshipItemModal(title, subtitle, html, context) {
    relationshipItemContext = context;
    document.getElementById("relationshipItemModalTitle").textContent = title;
    document.getElementById("relationshipItemModalSubtitle").textContent = subtitle || "";
    document.getElementById("relationshipItemModalBody").innerHTML = html;
    relationshipItemModal.show();
}

function closeRelationshipItemModal() {
    relationshipItemContext = null;
    relationshipItemModal.hide();
}

function accordionItem(id, title, body, show = false) {
    return `
        <div class="accordion-item">
            <h2 class="accordion-header">
                <button class="accordion-button ${show ? "" : "collapsed"}" type="button" data-bs-toggle="collapse" data-bs-target="#collapse-${id}">
                    ${escapeHtml(title)}
                </button>
            </h2>
            <div id="collapse-${id}" class="accordion-collapse collapse ${show ? "show" : ""}">
                <div class="accordion-body">
                    ${body}
                </div>
            </div>
        </div>
    `;
}

function relationshipTypeSelect(id, selected) {
    return `
        <select id="${id}" class="form-select">
            ${REL_TYPES.map(t => `<option value="${t}" ${t === selected ? "selected" : ""}>${t}</option>`).join("")}
        </select>
    `;
}

/* ---------------- Basic editors ---------------- */

function openInfoEditor() {
    const info = currentSpec.info || {};
    openModalEditor("Edit API Info", "Update title, description and version.", `
        <div class="accordion">
            ${accordionItem("info-general", "General", `
                <div class="row g-3">
                    <div class="col-md-8">
                        <label class="form-label">Title</label>
                        <input id="fe-info-title" class="form-control" value="${escapeHtml(info.title || "")}">
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">Version</label>
                        <input id="fe-info-version" class="form-control" value="${escapeHtml(info.version || "")}">
                    </div>
                    <div class="col-12">
                        <label class="form-label">Description</label>
                        <textarea id="fe-info-description" class="form-control">${escapeHtml(info.description || "")}</textarea>
                    </div>
                    <div class="col-12">
                        <button class="btn btn-primary" onclick="saveInfoEditor()">Save</button>
                    </div>
                </div>
            `, true)}
        </div>
    `);
}

function saveInfoEditor() {
    if (!currentSpec.info) currentSpec.info = {};
    currentSpec.info.title = document.getElementById("fe-info-title").value;
    currentSpec.info.description = document.getElementById("fe-info-description").value;
    currentSpec.info.version = document.getElementById("fe-info-version").value;
    syncAllViews();
}

function openServerEditor(index) {
    const server = currentSpec.servers?.[index] || { url: "" };
    openModalEditor("Edit Server", "Configure server URL.", `
        <div class="accordion">
            ${accordionItem("server-main", "Server", `
                <div class="mb-3">
                    <label class="form-label">Server URL</label>
                    <input id="fe-server-url" class="form-control" value="${escapeHtml(server.url || "")}">
                </div>
                <button class="btn btn-primary" onclick="saveServerEditor(${index})">Save</button>
            `, true)}
        </div>
    `);
}

function saveServerEditor(index) {
    if (!currentSpec.servers) currentSpec.servers = [];
    currentSpec.servers[index] = { url: document.getElementById("fe-server-url").value.trim() };
    syncAllViews();
}

function openPathEditor(pathKey) {
    openModalEditor("Edit Path", "Update path value.", `
        <div class="accordion">
            ${accordionItem("path-main", "Path", `
                <div class="mb-3">
                    <label class="form-label">Path</label>
                    <input id="fe-path-key" class="form-control" value="${escapeHtml(pathKey)}">
                </div>
                <button class="btn btn-primary" onclick='savePathEditor(${JSON.stringify(pathKey)})'>Save</button>
            `, true)}
        </div>
    `);
}

function savePathEditor(oldPath) {
    const newPath = document.getElementById("fe-path-key").value.trim();
    if (!newPath) return alert("Path is required");
    if (oldPath !== newPath) {
        currentSpec.paths[newPath] = currentSpec.paths[oldPath];
        delete currentSpec.paths[oldPath];

        const relPaths = ensureXPathRelationships();
        if (relPaths[oldPath]) {
            relPaths[newPath] = relPaths[oldPath];
            delete relPaths[oldPath];
        }
    }
    syncAllViews();
}

function openSchemaEditor(name) {
    ensureComponents();
    const schema = currentSpec.components.schemas[name] || { type: "object", properties: {} };
    openModalEditor(`Edit Schema: ${name}`, "Manage reusable schema.", `
        <div class="accordion">
            ${accordionItem("schema-general", "General", `
                <div class="row g-3">
                    <div class="col-md-6">
                        <label class="form-label">Schema Name</label>
                        <input id="fe-schema-name" class="form-control" value="${escapeHtml(name)}">
                    </div>
                    <div class="col-md-6">
                        <label class="form-label">Type</label>
                        <select id="fe-schema-type" class="form-select">
                            <option value="object" ${schema.type === "object" ? "selected" : ""}>object</option>
                            <option value="array" ${schema.type === "array" ? "selected" : ""}>array</option>
                            <option value="string" ${schema.type === "string" ? "selected" : ""}>string</option>
                            <option value="integer" ${schema.type === "integer" ? "selected" : ""}>integer</option>
                            <option value="number" ${schema.type === "number" ? "selected" : ""}>number</option>
                            <option value="boolean" ${schema.type === "boolean" ? "selected" : ""}>boolean</option>
                        </select>
                    </div>
                    <div class="col-12">
                        <label class="form-label">Raw Schema JSON</label>
                        <textarea id="fe-schema-json" class="form-control large-textarea" spellcheck="false">${escapeHtml(JSON.stringify(schema, null, 2))}</textarea>
                    </div>
                    <div class="col-12">
                        <button class="btn btn-primary" onclick='saveSchemaEditor(${JSON.stringify(name)})'>Save</button>
                    </div>
                </div>
            `, true)}
        </div>
    `);
}

function saveSchemaEditor(oldName) {
    ensureComponents();
    const newName = document.getElementById("fe-schema-name").value.trim();
    if (!newName) return alert("Schema name is required");
    try {
        const schema = JSON.parse(document.getElementById("fe-schema-json").value || "{}");
        schema.type = document.getElementById("fe-schema-type").value;
        if (oldName !== newName) {
            currentSpec.components.schemas[newName] = schema;
            delete currentSpec.components.schemas[oldName];
        } else {
            currentSpec.components.schemas[oldName] = schema;
        }
        syncAllViews();
    } catch {
        alert("Invalid schema JSON.");
    }
}

/* ---------------- Operation editor ---------------- */

function openOperationEditor(pathKey, method) {
    currentOperationContext = { pathKey, method };
    const op = ensurePathOperation(pathKey, method);
    const rel = ensureOperationRelationships(pathKey, method);
    const responseCodes = Object.keys(op.responses || {});

    openModalEditor(`${method.toUpperCase()} ${pathKey}`, "Stable editor with user-friendly schema relationship selection.", `
        <div class="accordion">
            ${accordionItem("op-general", "General", `
                <div class="row g-3">
                    <div class="col-md-6">
                        <label class="form-label">Summary</label>
                        <input id="op-summary" class="form-control" value="${escapeHtml(op.summary || "")}">
                    </div>
                    <div class="col-md-6">
                        <label class="form-label">Description</label>
                        <input id="op-description" class="form-control" value="${escapeHtml(op.description || "")}">
                    </div>
                    <div class="col-12">
                        <button class="btn btn-primary" onclick='saveOperationGeneral()'>Save General</button>
                    </div>
                </div>
            `, true)}

            ${accordionItem("op-request-schema-rel", "Request Schema Relationship", renderSchemaRelationshipEditor(pathKey, method, rel.requestSchemaRelation, "requestSchema"), true)}
            ${accordionItem("op-request-example-rel", "Request Example Relationship", renderExampleRelationshipEditor(pathKey, method, rel.requestExampleRelation, "requestExample"), true)}

            ${accordionItem("op-response-rel", "Response Relationships", `
                <div class="d-flex flex-wrap gap-2 mb-3">
                    <button class="btn btn-sm btn-outline-success" onclick='addResponseCode("success")'>Add Success Response</button>
                    <button class="btn btn-sm btn-outline-danger" onclick='addResponseCode("error")'>Add Error Response</button>
                    <button class="btn btn-sm btn-outline-warning" onclick='addResponseCode("other")'>Add Other Response</button>
                </div>
                ${responseCodes.length ? responseCodes.map(code => renderResponseRelationshipCard(pathKey, method, code)).join("") : "<div class='text-muted'>No responses</div>"}
            `, true)}
        </div>
    `);
}

function saveOperationGeneral() {
    const { pathKey, method } = currentOperationContext;
    const op = ensurePathOperation(pathKey, method);
    op.summary = document.getElementById("op-summary").value;
    op.description = document.getElementById("op-description").value;
    syncAllViews();
}

function renderSchemaRelationshipEditor(pathKey, method, relation, targetType, code = null) {
    relation = relation || relationTemplate();
    const typeId = code ? `${targetType}-type-${code}` : `${targetType}-type`;
    const addSelectId = code ? `${targetType}-existing-select-${code}` : `${targetType}-existing-select`;

    const listHtml = (relation.items || []).length ? relation.items.map((item, idx) => `
        <div class="rel-box mb-2">
            <div class="d-flex justify-content-between align-items-start gap-2">
                <div class="flex-grow-1">
                    <div><strong>Schema Item ${idx + 1}</strong></div>
                    <div class="small text-muted">Kind: ${escapeHtml(item.kind || "inline")}</div>
                    <div class="pre-json mt-2">${escapeHtml(JSON.stringify(item.value || null, null, 2))}</div>
                </div>
                <div class="d-flex gap-2">
                    <button class="btn btn-sm btn-primary" onclick='openSchemaRelationItemEditor(${JSON.stringify(targetType)}, ${code ? JSON.stringify(code) : "null"}, ${idx})'>Edit</button>
                    <button class="btn btn-sm btn-danger" onclick='deleteSchemaRelationItem(${JSON.stringify(targetType)}, ${code ? JSON.stringify(code) : "null"}, ${idx})'>Delete</button>
                </div>
            </div>
        </div>
    `).join("") : "<div class='text-muted'>No schema relationship items</div>";

    const schemaNames = getSchemaNames();
    const selectOptions = schemaNames.map(name => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join("");

    return `
        <div class="mb-3">
            <label class="form-label">Relationship Type</label>
            ${relationshipTypeSelect(typeId, relation.type || "single")}
        </div>

        <div class="row g-3 mb-3">
            <div class="col-md-8">
                <label class="form-label">Add Existing Schema</label>
                <select id="${addSelectId}" class="form-select">
                    <option value="">Choose schema</option>
                    ${selectOptions}
                </select>
            </div>
            <div class="col-md-4 d-flex align-items-end">
                <button class="btn btn-outline-primary w-100" onclick='addExistingSchemaToRelation(${JSON.stringify(targetType)}, ${code ? JSON.stringify(code) : "null"})'>Add Selected Schema</button>
            </div>
        </div>

        <div class="schema-drop-zone mb-3" id="drop-zone-${targetType}${code ? "-" + code : ""}" ondragover="onSchemaDropZoneOver(event)" ondragleave="onSchemaDropZoneLeave(event)" ondrop='onSchemaDrop(event, ${JSON.stringify(targetType)}, ${code ? JSON.stringify(code) : "null"})'>
            Drag an existing schema here to add it to this relationship
        </div>

        <div class="mb-3">
            <div class="small text-muted mb-2">Draggable existing schemas</div>
            <div>
                ${schemaNames.length ? schemaNames.map(name => `
                    <span class="schema-chip" draggable="true" ondragstart='onSchemaDragStart(event, ${JSON.stringify(name)})'>
                        ${escapeHtml(name)}
                    </span>
                `).join("") : "<span class='text-muted'>No schemas available</span>"}
            </div>
        </div>

        <div class="d-flex gap-2 mb-3 flex-wrap">
            <button class="btn btn-sm btn-outline-primary" onclick='saveRelationType(${JSON.stringify(targetType)}, ${code ? JSON.stringify(code) : "null"})'>Save Type</button>
            <button class="btn btn-sm btn-outline-secondary" onclick='openSchemaRelationItemEditor(${JSON.stringify(targetType)}, ${code ? JSON.stringify(code) : "null"}, null)'>Add Manual Schema Item</button>
        </div>

        ${listHtml}
    `;
}

function renderExampleRelationshipEditor(pathKey, method, relation, targetType, code = null) {
    relation = relation || relationTemplate();
    const typeId = code ? `${targetType}-type-${code}` : `${targetType}-type`;

    const listHtml = (relation.items || []).length ? relation.items.map((item, idx) => `
        <div class="rel-box mb-2">
            <div class="d-flex justify-content-between align-items-start gap-2">
                <div class="flex-grow-1">
                    <div><strong>${escapeHtml(item.name || `Example ${idx + 1}`)}</strong></div>
                    <div class="small text-muted">${escapeHtml(item.summary || "")}</div>
                    <div class="pre-json mt-2">${escapeHtml(JSON.stringify(item.value || null, null, 2))}</div>
                </div>
                <div class="d-flex gap-2">
                    <button class="btn btn-sm btn-primary" onclick='openExampleRelationItemEditor(${JSON.stringify(targetType)}, ${code ? JSON.stringify(code) : "null"}, ${idx})'>Edit</button>
                    <button class="btn btn-sm btn-danger" onclick='deleteExampleRelationItem(${JSON.stringify(targetType)}, ${code ? JSON.stringify(code) : "null"}, ${idx})'>Delete</button>
                </div>
            </div>
        </div>
    `).join("") : "<div class='text-muted'>No example relationship items</div>";

    return `
        <div class="mb-3">
            <label class="form-label">Relationship Type</label>
            ${relationshipTypeSelect(typeId, relation.type || "single")}
        </div>
        <div class="d-flex gap-2 mb-3 flex-wrap">
            <button class="btn btn-sm btn-outline-primary" onclick='saveRelationType(${JSON.stringify(targetType)}, ${code ? JSON.stringify(code) : "null"})'>Save Type</button>
            <button class="btn btn-sm btn-outline-secondary" onclick='openExampleRelationItemEditor(${JSON.stringify(targetType)}, ${code ? JSON.stringify(code) : "null"}, null)'>Add Example Item</button>
        </div>
        ${listHtml}
    `;
}

function renderResponseRelationshipCard(pathKey, method, code) {
    const op = ensurePathOperation(pathKey, method);
    const response = op.responses[code] || {};
    const schemaRel = ensureResponseSchemaRelation(pathKey, method, code);
    const exampleRel = ensureResponseExampleRelation(pathKey, method, code);

    return `
        <div class="card mb-3">
            <div class="card-header d-flex justify-content-between align-items-center">
                <div>
                    <strong>${escapeHtml(code)}</strong>
                    <div class="small text-muted">${escapeHtml(response.description || "")}</div>
                </div>
                <div class="d-flex gap-2">
                    <button class="btn btn-sm btn-outline-primary" onclick='openResponseGeneralEditor(${JSON.stringify(code)})'>Edit Response</button>
                    <button class="btn btn-sm btn-danger" onclick='deleteResponseCode(${JSON.stringify(pathKey)}, ${JSON.stringify(method)}, ${JSON.stringify(code)})'>Delete</button>
                </div>
            </div>
            <div class="card-body">
                <div class="accordion">
                    ${accordionItem(`res-schema-${slugify(code)}`, `Response Schema Relationship (${schemaRel.type || "single"})`, renderSchemaRelationshipEditor(pathKey, method, schemaRel, "responseSchema", code), true)}
                    ${accordionItem(`res-example-${slugify(code)}`, `Response Example Relationship (${exampleRel.type || "single"})`, renderExampleRelationshipEditor(pathKey, method, exampleRel, "responseExample", code), true)}
                </div>
            </div>
        </div>
    `;
}

function openResponseGeneralEditor(code) {
    const { pathKey, method } = currentOperationContext;
    const op = ensurePathOperation(pathKey, method);
    const res = op.responses[code] || { description: "" };

    openModalEditor(`Edit Response ${code}`, "Edit response code and description.", `
        <div class="accordion">
            ${accordionItem("response-general", "General", `
                <div class="row g-3">
                    <div class="col-md-4">
                        <label class="form-label">Status Code</label>
                        <input id="response-code" class="form-control" value="${escapeHtml(code)}">
                    </div>
                    <div class="col-md-8">
                        <label class="form-label">Description</label>
                        <input id="response-description" class="form-control" value="${escapeHtml(res.description || "")}">
                    </div>
                    <div class="col-12">
                        <button class="btn btn-primary" onclick='saveResponseGeneral(${JSON.stringify(code)})'>Save</button>
                    </div>
                </div>
            `, true)}
        </div>
    `);
}

function saveResponseGeneral(oldCode) {
    const { pathKey, method } = currentOperationContext;
    const op = ensurePathOperation(pathKey, method);
    const newCode = document.getElementById("response-code").value.trim();
    const desc = document.getElementById("response-description").value;
    if (!newCode) return alert("Code is required.");

    const existing = op.responses[oldCode];
    existing.description = desc;

    if (newCode !== oldCode) {
        op.responses[newCode] = existing;
        delete op.responses[oldCode];

        const opRel = ensureOperationRelationships(pathKey, method);
        if (opRel.responseSchemaRelations[oldCode]) {
            opRel.responseSchemaRelations[newCode] = opRel.responseSchemaRelations[oldCode];
            delete opRel.responseSchemaRelations[oldCode];
        }
        if (opRel.responseExampleRelations[oldCode]) {
            opRel.responseExampleRelations[newCode] = opRel.responseExampleRelations[oldCode];
            delete opRel.responseExampleRelations[oldCode];
        }
    }

    syncAllViews();
}

function getRelationObject(targetType, code = null) {
    const { pathKey, method } = currentOperationContext;
    const opRel = ensureOperationRelationships(pathKey, method);
    if (targetType === "requestSchema") return opRel.requestSchemaRelation;
    if (targetType === "requestExample") return opRel.requestExampleRelation;
    if (targetType === "responseSchema") return ensureResponseSchemaRelation(pathKey, method, code);
    if (targetType === "responseExample") return ensureResponseExampleRelation(pathKey, method, code);
    return null;
}

function saveRelationType(targetType, code = null) {
    const relation = getRelationObject(targetType, code);
    if (!relation) return;
    const id = code ? `${targetType}-type-${code}` : `${targetType}-type`;
    const el = document.getElementById(id);
    if (!el) return;
    relation.type = el.value;
    syncAllViews();
}

/* ---------------- Existing schema selection / DnD ---------------- */

function addExistingSchemaToRelation(targetType, code = null, schemaName = null) {
    const relation = getRelationObject(targetType, code);
    if (!relation) return;

    const selectId = code ? `${targetType}-existing-select-${code}` : `${targetType}-existing-select`;
    const selected = schemaName || document.getElementById(selectId)?.value;
    if (!selected) return alert("Please select a schema.");

    const refValue = `#/components/schemas/${selected}`;
    const exists = (relation.items || []).some(item => item.kind === "ref" && item.value === refValue);
    if (exists) return alert("Schema already added to this relationship.");

    relation.items.push({
        kind: "ref",
        value: refValue
    });

    syncAllViews();
}

function onSchemaDragStart(event, schemaName) {
    event.dataTransfer.setData("text/plain", schemaName);
}

function onSchemaDropZoneOver(event) {
    event.preventDefault();
    event.currentTarget.classList.add("drag-over");
}

function onSchemaDropZoneLeave(event) {
    event.currentTarget.classList.remove("drag-over");
}

function onSchemaDrop(event, targetType, code = null) {
    event.preventDefault();
    event.currentTarget.classList.remove("drag-over");
    const schemaName = event.dataTransfer.getData("text/plain");
    if (!schemaName) return;
    addExistingSchemaToRelation(targetType, code, schemaName);
}

/* ---------------- Relationship item editors ---------------- */

function openSchemaRelationItemEditor(targetType, code, index) {
    const relation = getRelationObject(targetType, code);
    const item = index == null ? { kind: "inline", value: {"type": "object", "properties": {}} } : deepClone(relation.items[index]);
    const schemaNames = getSchemaNames();

    openRelationshipItemModal(
        "Schema Relationship Item",
        "Choose existing schema, use drag-drop, or define manual inline schema.",
        `
        <div class="row g-3">
            <div class="col-md-4">
                <label class="form-label">Schema Item Kind</label>
                <select id="rel-schema-kind" class="form-select" onchange="toggleSchemaItemEditorMode()">
                    <option value="existing" ${item.kind === "ref" ? "selected" : ""}>existing schema</option>
                    <option value="inline" ${item.kind === "inline" ? "selected" : ""}>inline schema</option>
                    <option value="ref" ${item.kind === "ref" ? "" : ""}>manual $ref</option>
                </select>
            </div>

            <div class="col-12" id="rel-schema-existing-wrap">
                <label class="form-label">Select Existing Schema</label>
                <select id="rel-schema-existing" class="form-select">
                    <option value="">Choose schema</option>
                    ${schemaNames.map(name => {
                        const selected = item.kind === "ref" && item.value === `#/components/schemas/${name}` ? "selected" : "";
                        return `<option value="${escapeHtml(name)}" ${selected}>${escapeHtml(name)}</option>`;
                    }).join("")}
                </select>
                <div class="schema-drop-zone mt-3" ondragover="onSchemaDropZoneOver(event)" ondragleave="onSchemaDropZoneLeave(event)" ondrop="onSchemaDropIntoEditor(event)">
                    Drag schema here
                </div>
                <div class="mt-3">
                    ${schemaNames.map(name => `
                        <span class="schema-chip" draggable="true" ondragstart='onSchemaDragStart(event, ${JSON.stringify(name)})'>
                            ${escapeHtml(name)}
                        </span>
                    `).join("")}
                </div>
            </div>

            <div class="col-12 hidden" id="rel-schema-ref-wrap">
                <label class="form-label">Manual Schema Reference</label>
                <input id="rel-schema-ref" class="form-control" value="${escapeHtml(item.kind === "ref" ? (item.value || "") : "")}" placeholder="#/components/schemas/YourSchema">
            </div>

            <div class="col-12 hidden" id="rel-schema-inline-wrap">
                <label class="form-label">Inline Schema JSON</label>
                <textarea id="rel-schema-inline" class="form-control large-textarea" spellcheck="false">${escapeHtml(JSON.stringify(item.kind === "inline" ? (item.value || {}) : {}, null, 2))}</textarea>
            </div>
        </div>
        `,
        { kind: "schema", targetType, code, index }
    );

    const initialKind = item.kind === "inline" ? "inline" : "existing";
    document.getElementById("rel-schema-kind").value = initialKind;
    toggleSchemaItemEditorMode();
}

function onSchemaDropIntoEditor(event) {
    event.preventDefault();
    event.currentTarget.classList.remove("drag-over");
    const schemaName = event.dataTransfer.getData("text/plain");
    if (!schemaName) return;
    const select = document.getElementById("rel-schema-existing");
    if (select) select.value = schemaName;
}

function toggleSchemaItemEditorMode() {
    const mode = document.getElementById("rel-schema-kind").value;
    const existingWrap = document.getElementById("rel-schema-existing-wrap");
    const refWrap = document.getElementById("rel-schema-ref-wrap");
    const inlineWrap = document.getElementById("rel-schema-inline-wrap");

    existingWrap.classList.toggle("hidden", mode !== "existing");
    refWrap.classList.toggle("hidden", mode !== "ref");
    inlineWrap.classList.toggle("hidden", mode !== "inline");
}

function openExampleRelationItemEditor(targetType, code, index) {
    const relation = getRelationObject(targetType, code);
    const item = index == null ? { name: "", summary: "", value: {} } : deepClone(relation.items[index]);

    openRelationshipItemModal(
        "Example Relationship Item",
        "Add or edit a named example relationship item.",
        `
        <div class="row g-3">
            <div class="col-md-4">
                <label class="form-label">Example Name</label>
                <input id="rel-example-name" class="form-control" value="${escapeHtml(item.name || "")}">
            </div>
            <div class="col-md-8">
                <label class="form-label">Summary</label>
                <input id="rel-example-summary" class="form-control" value="${escapeHtml(item.summary || "")}">
            </div>
            <div class="col-12">
                <label class="form-label">Example Value JSON</label>
                <textarea id="rel-example-json" class="form-control large-textarea" spellcheck="false">${escapeHtml(JSON.stringify(item.value || {}, null, 2))}</textarea>
            </div>
        </div>
        `,
        { kind: "example", targetType, code, index }
    );
}

function saveRelationshipItemModal() {
    if (!relationshipItemContext) return;

    const relation = getRelationObject(relationshipItemContext.targetType, relationshipItemContext.code);
    if (!relation) return;

    try {
        let item;
        if (relationshipItemContext.kind === "schema") {
            const mode = document.getElementById("rel-schema-kind").value;
            if (mode === "existing") {
                const schemaName = document.getElementById("rel-schema-existing").value.trim();
                if (!schemaName) return alert("Please select an existing schema.");
                item = { kind: "ref", value: `#/components/schemas/${schemaName}` };
            } else if (mode === "ref") {
                const ref = document.getElementById("rel-schema-ref").value.trim();
                if (!ref) return alert("Reference is required.");
                item = { kind: "ref", value: ref };
            } else {
                const raw = document.getElementById("rel-schema-inline").value.trim();
                item = { kind: "inline", value: raw ? JSON.parse(raw) : {} };
            }
        } else {
            const name = document.getElementById("rel-example-name").value.trim();
            const summary = document.getElementById("rel-example-summary").value.trim();
            const raw = document.getElementById("rel-example-json").value.trim();
            if (!name) return alert("Example name is required.");
            item = { name, summary, value: raw ? JSON.parse(raw) : {} };
        }

        if (relationshipItemContext.index == null) relation.items.push(item);
        else relation.items[relationshipItemContext.index] = item;

        syncAllViews();
        closeRelationshipItemModal();
    } catch {
        alert("Invalid JSON.");
    }
}

function deleteSchemaRelationItem(targetType, code, index) {
    const relation = getRelationObject(targetType, code);
    if (!relation) return;
    relation.items.splice(index, 1);
    syncAllViews();
}

function deleteExampleRelationItem(targetType, code, index) {
    const relation = getRelationObject(targetType, code);
    if (!relation) return;
    relation.items.splice(index, 1);
    syncAllViews();
}

/* ---------------- CRUD actions ---------------- */

function addPath() {
    ensurePaths();
    let base = "/new-path";
    let candidate = base;
    let i = 1;
    while (currentSpec.paths[candidate]) candidate = `${base}-${i++}`;
    currentSpec.paths[candidate] = {
        get: {
            summary: "New operation",
            description: "",
            parameters: [],
            responses: { "200": { description: "OK", content: { "application/json": {} } } }
        }
    };
    ensureOperationRelationships(candidate, "get");
    syncAllViews();
}

function deletePath(pathKey) {
    if (!confirm(`Delete ${pathKey}?`)) return;
    delete currentSpec.paths[pathKey];
    const relPaths = ensureXPathRelationships();
    delete relPaths[pathKey];
    syncAllViews();
}

function addOperation(pathKey) {
    ensurePaths();
    if (!currentSpec.paths[pathKey]) currentSpec.paths[pathKey] = {};
    const candidates = ["get", "post", "put", "delete", "patch"];
    const method = candidates.find(m => !currentSpec.paths[pathKey][m]) || `x${Date.now()}`;
    currentSpec.paths[pathKey][method] = {
        summary: "New operation",
        description: "",
        parameters: [],
        responses: { "200": { description: "OK", content: { "application/json": {} } } }
    };
    ensureOperationRelationships(pathKey, method);
    syncAllViews();
    openOperationEditor(pathKey, method);
}

function deleteOperation(pathKey, method) {
    if (!confirm(`Delete ${method.toUpperCase()} ${pathKey}?`)) return;
    delete currentSpec.paths[pathKey][method];
    const relPaths = ensureXPathRelationships();
    if (relPaths[pathKey]) delete relPaths[pathKey][method];
    if (!Object.keys(currentSpec.paths[pathKey]).length) delete currentSpec.paths[pathKey];
    if (relPaths[pathKey] && !Object.keys(relPaths[pathKey]).length) delete relPaths[pathKey];
    syncAllViews();
}

function addResponseCode(group) {
    const { pathKey, method } = currentOperationContext;
    const op = ensurePathOperation(pathKey, method);
    let code = group === "success" ? "200" : group === "error" ? "400" : "300";
    while (op.responses[code]) code = String(Number(code) + 1);
    op.responses[code] = {
        description: "Response",
        content: { "application/json": {} }
    };
    ensureResponseSchemaRelation(pathKey, method, code);
    ensureResponseExampleRelation(pathKey, method, code);
    syncAllViews();
}

function deleteResponseCode(pathKey, method, code) {
    const op = ensurePathOperation(pathKey, method);
    delete op.responses[code];
    const opRel = ensureOperationRelationships(pathKey, method);
    delete opRel.responseSchemaRelations[code];
    delete opRel.responseExampleRelations[code];
    syncAllViews();
}

function addServer() {
    if (!currentSpec.servers) currentSpec.servers = [];
    currentSpec.servers.push({ url: "https://new-server.example.com" });
    syncAllViews();
}

function deleteServer(index) {
    currentSpec.servers.splice(index, 1);
    syncAllViews();
}

function addSchema() {
    ensureComponents();
    let base = "NewSchema";
    let candidate = base;
    let i = 1;
    while (currentSpec.components.schemas[candidate]) candidate = `${base}${i++}`;
    currentSpec.components.schemas[candidate] = { type: "object", properties: {} };
    syncAllViews();
    openSchemaEditor(candidate);
}

function deleteSchema(name) {
    if (!confirm(`Delete schema ${name}?`)) return;
    delete currentSpec.components.schemas[name];
    syncAllViews();
}

/* ---------------- Raw sync ---------------- */

async function syncFromRawEditor() {
    try {
        const response = await fetch("/parse_spec", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: getEditorText(), mode: editorMode })
        });

        const result = await response.json();
        if (!result.success) {
            setStatus("Syntax: Invalid", false);
            setEditorErrorMarker(result.error || "Invalid syntax");
            return;
        }

        clearEditorMarkers();
        currentSpec = result.json;
        if (result.relationship_types) REL_TYPES = result.relationship_types;
        renderTree();
        renderEditableCanvas();
        initSwaggerUI(currentSpec);
        runSemanticValidation(currentSpec);
        setStatus("Syntax: Valid", true);
    } catch (e) {
        console.error(e);
        setStatus("Syntax: Error", false);
    }
}

const debouncedSyncFromRaw = debounce(syncFromRawEditor, 700);

function syncAllViews() {
    syncOpenApiFromRelationships();
    syncRawEditorFromSpec();
    renderTree();
    renderEditableCanvas();
    initSwaggerUI(currentSpec);
    runSemanticValidation(currentSpec);
    setStatus("Syntax: Valid", true);
}

/* ---------------- Import / export ---------------- */

function setEditorMode(mode) {
    if (mode === editorMode) return;
    try {
        syncSpecFromRawEditor();
        editorMode = mode;
        updateEditorModeUi();
        syncRawEditorFromSpec();
        syncFromRawEditor();
    } catch {
        alert("Cannot switch mode because current content is invalid.");
    }
}

function formatEditorContent() {
    try {
        syncSpecFromRawEditor();
        syncRawEditorFromSpec();
        syncFromRawEditor();
    } catch {
        alert("Cannot format invalid content.");
    }
}

function triggerImport() {
    const input = document.getElementById("file-import");
    if (input) input.click();
}

function setupFileImport() {
    const input = document.getElementById("file-import");
    if (!input) return;
    input.addEventListener("change", async (e) => {
        const file = e.target.files && e.target.files[0];
        if (!file) return;
        await importFileObject(file);
        input.value = "";
    });
}

async function importFileObject(file) {
    const text = await file.text();
    const lower = file.name.toLowerCase();
    try {
        if (lower.endsWith(".json")) {
            editorMode = "json";
            updateEditorModeUi();
            currentSpec = JSON.parse(text);
        } else {
            editorMode = "yaml";
            updateEditorModeUi();
            currentSpec = jsyaml.load(text);
        }
        syncOpenApiFromRelationships();
        syncAllViews();
    } catch {
        alert("Imported file is not valid YAML/JSON.");
    }
}

function downloadCurrentYaml() {
    try {
        syncSpecFromRawEditor();
        downloadTextFile(`${getDownloadBaseName()}.yaml`, specToYaml(currentSpec), "text/yaml");
    } catch {
        alert("Cannot download YAML.");
    }
}

function downloadCurrentJson() {
    try {
        syncSpecFromRawEditor();
        downloadTextFile(`${getDownloadBaseName()}.json`, JSON.stringify(currentSpec, null, 2), "application/json");
    } catch {
        alert("Cannot download JSON.");
    }
}

async function downloadHtmlDocs() {
    try {
        syncSpecFromRawEditor();
        const response = await fetch("/export_html", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ spec: currentSpec })
        });
        const html = await response.text();
        downloadTextFile(`${getDownloadBaseName()}.html`, html, "text/html");
    } catch {
        alert("Cannot export HTML docs.");
    }
}

/* ---------------- Stored Specs ---------------- */

async function refreshSpecList(query = "") {
    const response = await fetch(`/api/specs?q=${encodeURIComponent(query)}`);
    const specs = await response.json();
    const list = document.getElementById("spec-list");
    if (!list) return;
    list.innerHTML = "";

    if (!specs.length) {
        list.innerHTML = "<div class='list-group-item text-muted'>No stored specifications found.</div>";
        return;
    }

    const currentId = document.getElementById("current-spec-id")?.value;
    specs.forEach(spec => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "list-group-item list-group-item-action" + (String(currentId) === String(spec.id) ? " active" : "");
        btn.innerHTML = `<div><strong>${escapeHtml(spec.name)}</strong></div><div class="small">${escapeHtml(spec.updated_at)}</div>`;
        btn.addEventListener("click", () => loadSpecById(spec.id));
        list.appendChild(btn);
    });
}

async function loadSpecById(specId) {
    const response = await fetch(`/api/specs/${specId}`);
    const result = await response.json();
    if (!result.success) {
        alert(result.error || "Failed to load spec.");
        return;
    }

    const spec = result.spec;
    document.getElementById("current-spec-id").value = spec.id;
    document.getElementById("spec-name").value = spec.name;
    editorMode = "yaml";
    updateEditorModeUi();
    currentSpec = jsyaml.load(spec.yaml_text);
    syncOpenApiFromRelationships();
    syncAllViews();
    await refreshSpecList(document.getElementById("spec-search")?.value || "");
}

async function saveAsNewSpec() {
    const name = document.getElementById("spec-name")?.value.trim();
    if (!name) return alert("Please enter a spec name.");
    syncOpenApiFromRelationships();
    const yamlText = specToYaml(currentSpec);
    const response = await fetch("/api/specs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, yaml_text: yamlText })
    });
    const result = await response.json();
    if (result.success) {
        document.getElementById("current-spec-id").value = result.id;
        await refreshSpecList(document.getElementById("spec-search")?.value || "");
        alert("Saved.");
    } else {
        alert(result.error || "Failed to save.");
    }
}

async function updateCurrentSpec() {
    const specId = document.getElementById("current-spec-id")?.value;
    const name = document.getElementById("spec-name")?.value.trim();
    if (!specId) return alert("Use Save As New first.");
    if (!name) return alert("Please enter a spec name.");

    syncOpenApiFromRelationships();
    const yamlText = specToYaml(currentSpec);
    const response = await fetch(`/api/specs/${specId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, yaml_text: yamlText })
    });
    const result = await response.json();
    if (result.success) {
        await refreshSpecList(document.getElementById("spec-search")?.value || "");
        alert("Updated.");
    } else {
        alert(result.error || "Failed to update.");
    }
}

async function deleteCurrentSpec() {
    const specId = document.getElementById("current-spec-id")?.value;
    if (!specId) return alert("No loaded spec selected.");
    if (!confirm("Delete this stored specification?")) return;

    const response = await fetch(`/api/specs/${specId}`, { method: "DELETE" });
    const result = await response.json();
    if (result.success) {
        document.getElementById("current-spec-id").value = "";
        document.getElementById("spec-name").value = "";
        await refreshSpecList(document.getElementById("spec-search")?.value || "");
        alert("Deleted.");
    } else {
        alert(result.error || "Failed to delete.");
    }
}

/* ---------------- Init ---------------- */

window.onload = async function () {
    editorModal = new bootstrap.Modal(document.getElementById("editorModal"));
    relationshipItemModal = new bootstrap.Modal(document.getElementById("relationshipItemModal"));
    const savedTheme = localStorage.getItem("swagger-studio-theme") || "light";
    applyTheme(savedTheme);
    updateEditorModeUi();

    initMonacoEditor(window.INITIAL_YAML || "");

    const waitForMonaco = setInterval(async () => {
        if (monacoEditor) {
            clearInterval(waitForMonaco);
            currentSpec = jsyaml.load(window.INITIAL_YAML || "{}");
            syncOpenApiFromRelationships();
            syncAllViews();
            initResizablePanels();
            updateSplitterVisibility();
            setupFileImport();

            document.addEventListener("input", (e) => {
                if (e.target.id === "spec-search") {
                    refreshSpecList(e.target.value || "");
                }
            });

            await refreshSpecList();
        }
    }, 100);
};
'''

REQUIREMENTS = r'''Flask
PyYAML
'''

README = r'''# Swagger Studio v11.2

Features:
- existing schema selection in schema relationship item
- drag and drop existing schemas into relationship
- manual inline schema and manual ref still supported
- multiple schema relationship items
- multiple example relationship items
- stable edit panels with no forced auto-collapse after edits
- explicit x-studio relationship metadata
- valid OpenAPI 3.x output

## Run

pip install -r requirements.txt
python app.py
'''


def log(*args):
    print(*args, flush=True)


def write_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    log(f"Created file: {path}")


def main():
    try:
        root = Path.cwd()
        log(f"Creating files in: {root}")

        write_file(root / "app.py", APP_PY)
        write_file(root / "templates" / "index.html", INDEX_HTML)
        write_file(root / "static" / "style.css", STYLE_CSS)
        write_file(root / "static" / "app.js", APP_JS)
        write_file(root / "requirements.txt", REQUIREMENTS)
        write_file(root / "README.md", README)

        log("")
        log("Done.")
        log("Created structure:")
        log(" - app.py")
        log(" - templates/index.html")
        log(" - static/style.css")
        log(" - static/app.js")
        log(" - requirements.txt")
        log(" - README.md")

    except Exception as e:
        log("ERROR OCCURRED:")
        log(str(e))
        traceback.print_exc()

    finally:
        try:
            input("\\nPress Enter to exit...")
        except EOFError:
            pass


if __name__ == "__main__":
    main()
