from pathlib import Path
import traceback

APP_PY = r'''from flask import Flask, render_template, request, jsonify, Response
import sqlite3
import yaml
import json
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
            "title": "Swagger Studio v9.2",
            "description": "Bootstrap-based OpenAPI editor with collapsible sections and example management.",
            "version": "1.0.0"
        },
        "servers": [
            {"url": "https://api.example.com"},
            {"url": "https://staging-api.example.com"}
        ],
        "components": {
            "schemas": {
                "User": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "name": {"type": "string"},
                        "email": {"type": "string"}
                    },
                    "example": {
                        "id": 1,
                        "name": "John",
                        "email": "john@example.com"
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
                "get": {
                    "summary": "List users",
                    "description": "Returns a list of users.",
                    "parameters": [
                        {
                            "name": "page",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "integer", "default": 1}
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Successful response",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/User"}
                                    },
                                    "examples": {
                                        "basic": {
                                            "summary": "Basic response",
                                            "value": [
                                                {"id": 1, "name": "John", "email": "john@example.com"}
                                            ]
                                        },
                                        "empty": {
                                            "summary": "Empty list",
                                            "value": []
                                        }
                                    }
                                }
                            }
                        },
                        "400": {
                            "description": "Bad request",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                                    "examples": {
                                        "validationError": {
                                            "summary": "Validation error",
                                            "value": {"message": "Invalid page", "code": "INVALID_PAGE"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                "post": {
                    "summary": "Create user",
                    "description": "Creates a new user.",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "email": {"type": "string"}
                                    }
                                },
                                "examples": {
                                    "createUser": {
                                        "summary": "Create user payload",
                                        "value": {"name": "John", "email": "john@example.com"}
                                    },
                                    "minimal": {
                                        "summary": "Minimal payload",
                                        "value": {"name": "Jane", "email": "jane@example.com"}
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
                                            "value": {"id": 2, "name": "John", "email": "john@example.com"}
                                        }
                                    }
                                }
                            }
                        },
                        "409": {
                            "description": "Conflict",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                                    "examples": {
                                        "duplicateEmail": {
                                            "summary": "Duplicate email",
                                            "value": {"message": "Email already exists", "code": "DUPLICATE_EMAIL"}
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


@app.route("/")
def index():
    yaml_text = yaml.dump(default_openapi_spec(), sort_keys=False, allow_unicode=True)
    return render_template("index.html", initial_yaml=yaml_text)


@app.route("/parse_spec", methods=["POST"])
def parse_spec():
    data = request.json or {}
    text = data.get("text", "")
    mode = data.get("mode", "yaml")
    try:
        parsed = json.loads(text) if mode == "json" else yaml.safe_load(text)
        if parsed is None:
            parsed = {}
        return jsonify({
            "success": True,
            "json": parsed,
            "yaml": yaml.dump(parsed, sort_keys=False, allow_unicode=True)
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
    if not yaml_text.strip():
        return jsonify({"success": False, "error": "YAML content is required"}), 400
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
'''

INDEX_HTML = r'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Swagger Studio v9.2</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist/swagger-ui.css" />
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body class="studio-body">
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark border-bottom shadow-sm">
        <div class="container-fluid">
            <a class="navbar-brand fw-bold" href="#">Swagger Studio v9.2</a>
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
                            <div class="small text-muted">Collapsible sections, multiple examples, cleaner UX</div>
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
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body" id="editorModalBody"></div>
                <div class="modal-footer sticky-bottom bg-body">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                </div>
            </div>
        </div>
    </div>

    <script>
        window.INITIAL_YAML = {{ initial_yaml|tojson }};
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
.design-panel { width: 32%; min-width: 280px; }
.raw-panel { width: 22%; min-width: 260px; }
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
}

.example-box {
    border: 1px solid #dee2e6;
    border-radius: 0.5rem;
    padding: 0.75rem;
    background: #fff;
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
body.dark-theme .example-box {
    background: #0b1220;
    border-color: #334155;
    color: #e5e7eb;
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

function ensurePaths() {
    if (!currentSpec.paths) currentSpec.paths = {};
}

function ensureComponents() {
    if (!currentSpec.components) currentSpec.components = {};
    if (!currentSpec.components.schemas) currentSpec.components.schemas = {};
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

function ensureRequestJson(op) {
    if (!op.requestBody) op.requestBody = { required: true, content: {} };
    if (!op.requestBody.content) op.requestBody.content = {};
    if (!op.requestBody.content["application/json"]) op.requestBody.content["application/json"] = {};
    return op.requestBody.content["application/json"];
}

function ensureResponseJson(op, code) {
    if (!op.responses) op.responses = {};
    if (!op.responses[code]) op.responses[code] = { description: "Response", content: {} };
    if (!op.responses[code].content) op.responses[code].content = {};
    if (!op.responses[code].content["application/json"]) op.responses[code].content["application/json"] = {};
    return op.responses[code].content["application/json"];
}

function syncRawEditorFromSpec() {
    if (!currentSpec) return;
    if (editorMode === "json") setEditorText(JSON.stringify(currentSpec, null, 2));
    else setEditorText(specToYaml(currentSpec));
}

function syncSpecFromRawEditor() {
    currentSpec = parseEditorContent(getEditorText()) || {};
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

function inferSchemaFromExample(value) {
    if (Array.isArray(value)) {
        return {
            type: "array",
            items: value.length ? inferSchemaFromExample(value[0]) : { type: "string" }
        };
    }
    if (value === null) return { type: "string", nullable: true };
    if (typeof value === "object") {
        const properties = {};
        Object.keys(value).forEach(key => {
            properties[key] = inferSchemaFromExample(value[key]);
        });
        return { type: "object", properties };
    }
    if (typeof value === "number") return Number.isInteger(value) ? { type: "integer" } : { type: "number" };
    if (typeof value === "boolean") return { type: "boolean" };
    return { type: "string" };
}

function classifyResponseCode(code) {
    const n = parseInt(code, 10);
    if (n >= 200 && n < 300) return "success";
    if (n >= 400 && n < 600) return "error";
    return "other";
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
        const designW = designVisible ? parseFloat(design.style.width || "32") : 0;
        const rawW = rawVisible ? parseFloat(raw.style.width || "22") : 0;
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
            if (newDesign > 55) newDesign = 55;
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

/* ---------------- Design Canvas with collapsibles ---------------- */

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
                    <div class="accordion mb-2" id="serverAcc${i}">
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
                    return `
                        <div class="accordion mb-2" id="${opId}">
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
                                            <strong>Parameters:</strong> ${(op.parameters || []).length}
                                            <br>
                                            <strong>Responses:</strong> ${Object.keys(op.responses || {}).length}
                                            <br>
                                            <strong>Request Examples:</strong> ${Object.keys(op.requestBody?.content?.["application/json"]?.examples || {}).length}
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
                    <div class="accordion mb-2" id="schemaAcc${i}">
                        <div class="accordion-item">
                            <h2 class="accordion-header">
                                <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#schemaCollapse${i}">
                                    ${escapeHtml(name)} (${escapeHtml(schemas[name]?.type || "object")})
                                </button>
                            </h2>
                            <div id="schemaCollapse${i}" class="accordion-collapse collapse">
                                <div class="accordion-body">
                                    <div class="small text-muted mb-2">Properties: ${Object.keys(schemas[name]?.properties || {}).length}</div>
                                    <div class="pre-json mb-2">${escapeHtml(JSON.stringify(schemas[name]?.example || {}, null, 2))}</div>
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

function slugify(text) {
    return String(text).replace(/[^a-zA-Z0-9]+/g, "-");
}

/* ---------------- Modal helpers ---------------- */

function openModalEditor(title, subtitle, html) {
    document.getElementById("editorModalTitle").textContent = title;
    document.getElementById("editorModalSubtitle").textContent = subtitle || "";
    document.getElementById("editorModalBody").innerHTML = html;
    editorModal.show();
}

function accordionItem(id, title, body, show = false) {
    return `
        <div class="accordion-item">
            <h2 class="accordion-header" id="heading-${id}">
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

/* ---------------- Editors ---------------- */

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
    }
    syncAllViews();
}

function openSchemaEditor(name) {
    ensureComponents();
    const schema = currentSpec.components.schemas[name] || { type: "object", properties: {}, example: {} };
    const properties = Object.keys(schema.properties || {}).map(key => `
        <div class="d-flex justify-content-between align-items-center border rounded p-2 mb-2">
            <div>
                <strong>${escapeHtml(key)}</strong>
                <div class="small text-muted">${escapeHtml(schema.properties[key]?.type || "string")}</div>
            </div>
            <div class="d-flex gap-2">
                <button class="btn btn-sm btn-outline-primary" onclick='renameSchemaProperty(${JSON.stringify(name)}, ${JSON.stringify(key)})'>Rename</button>
                <button class="btn btn-sm btn-outline-danger" onclick='deleteSchemaProperty(${JSON.stringify(name)}, ${JSON.stringify(key)})'>Delete</button>
            </div>
        </div>
    `).join("") || "<div class='text-muted'>No properties</div>";

    openModalEditor(`Edit Schema: ${name}`, "Manage reusable schema types, properties and example.", `
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
                    <div class="col-12 d-flex gap-2">
                        <button class="btn btn-primary" onclick='saveSchemaEditor(${JSON.stringify(name)})'>Save</button>
                        <button class="btn btn-outline-primary" onclick='addSchemaProperty(${JSON.stringify(name)})'>Add Property</button>
                    </div>
                </div>
            `, true)}
            ${accordionItem("schema-properties", "Properties", properties)}
            ${accordionItem("schema-example", "Schema Example", `
                <div class="mb-3">
                    <label class="form-label">Example JSON</label>
                    <textarea id="schema-example-json" class="form-control" rows="8">${escapeHtml(JSON.stringify(schema.example || {}, null, 2))}</textarea>
                </div>
                <button class="btn btn-outline-primary" onclick='saveSchemaExample(${JSON.stringify(name)})'>Save Example</button>
            `)}
        </div>
    `);
}

function saveSchemaEditor(oldName) {
    ensureComponents();
    const newName = document.getElementById("fe-schema-name").value.trim();
    const type = document.getElementById("fe-schema-type").value;
    if (!newName) return alert("Schema name is required");

    const schema = currentSpec.components.schemas[oldName] || {};
    schema.type = type;
    if (type === "object" && !schema.properties) schema.properties = {};
    if (!schema.example) schema.example = {};

    if (oldName !== newName) {
        currentSpec.components.schemas[newName] = schema;
        delete currentSpec.components.schemas[oldName];
    } else {
        currentSpec.components.schemas[oldName] = schema;
    }
    syncAllViews();
}

function saveSchemaExample(schemaName) {
    try {
        const text = document.getElementById("schema-example-json").value.trim();
        currentSpec.components.schemas[schemaName].example = text ? JSON.parse(text) : {};
        syncAllViews();
    } catch {
        alert("Invalid schema example JSON.");
    }
}

function addSchemaProperty(schemaName) {
    ensureComponents();
    const schema = currentSpec.components.schemas[schemaName];
    if (!schema.properties) schema.properties = {};
    let base = "property";
    let candidate = base;
    let i = 1;
    while (schema.properties[candidate]) candidate = `${base}${i++}`;
    schema.properties[candidate] = { type: "string" };
    syncAllViews();
    openSchemaEditor(schemaName);
}

function renameSchemaProperty(schemaName, propName) {
    const next = prompt("New property name:", propName);
    if (!next || next === propName) return;
    const schema = currentSpec.components.schemas[schemaName];
    schema.properties[next] = schema.properties[propName];
    delete schema.properties[propName];
    syncAllViews();
    openSchemaEditor(schemaName);
}

function deleteSchemaProperty(schemaName, propName) {
    if (!confirm(`Delete property ${propName}?`)) return;
    const schema = currentSpec.components.schemas[schemaName];
    delete schema.properties[propName];
    syncAllViews();
    openSchemaEditor(schemaName);
}

function openOperationEditor(pathKey, method) {
    const op = ensurePathOperation(pathKey, method);
    const requestJson = ensureRequestJson(op);
    const requestExamples = requestJson.examples || {};
    const responseCodes = Object.keys(op.responses || {});

    openModalEditor(`${method.toUpperCase()} ${pathKey}`, "Edit operation, request/response examples and related settings.", `
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
                        <button class="btn btn-primary" onclick='saveOperationEditor(${JSON.stringify(pathKey)}, ${JSON.stringify(method)})'>Save</button>
                    </div>
                </div>
            `, true)}

            ${accordionItem("op-params", "Parameters", `
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <div class="small text-muted">Manage parameters</div>
                    <button class="btn btn-sm btn-outline-primary" onclick='addOperationParameter(${JSON.stringify(pathKey)}, ${JSON.stringify(method)})'>Add Parameter</button>
                </div>
                ${(op.parameters || []).length ? (op.parameters || []).map((p, i) => `
                    <div class="d-flex justify-content-between align-items-center border rounded p-2 mb-2">
                        <div>
                            <strong>${escapeHtml(p.name || "")}</strong>
                            <div class="small text-muted">${escapeHtml(p.in || "query")} • ${escapeHtml(p.schema?.type || "string")}</div>
                        </div>
                        <div class="d-flex gap-2">
                            <button class="btn btn-sm btn-primary" onclick='editOperationParameter(${JSON.stringify(pathKey)}, ${JSON.stringify(method)}, ${i})'>Edit</button>
                            <button class="btn btn-sm btn-danger" onclick='deleteOperationParameter(${JSON.stringify(pathKey)}, ${JSON.stringify(method)}, ${i})'>Delete</button>
                        </div>
                    </div>
                `).join("") : "<div class='text-muted'>No parameters</div>"}
            `)}

            ${accordionItem("op-request-schema", "Request Schema", `
                <div class="d-flex flex-wrap gap-2 mb-3">
                    <button class="btn btn-sm btn-outline-primary" onclick='setRequestSchemaType(${JSON.stringify(pathKey)}, ${JSON.stringify(method)}, "object")'>Object Schema</button>
                    <button class="btn btn-sm btn-outline-primary" onclick='setRequestSchemaType(${JSON.stringify(pathKey)}, ${JSON.stringify(method)}, "array")'>Array Schema</button>
                    <button class="btn btn-sm btn-outline-primary" onclick='setRequestSchemaType(${JSON.stringify(pathKey)}, ${JSON.stringify(method)}, "string")'>String Schema</button>
                    <button class="btn btn-sm btn-outline-secondary" onclick='useRequestSchemaRef(${JSON.stringify(pathKey)}, ${JSON.stringify(method)})'>Use Schema Ref</button>
                </div>
                <div class="pre-json">${escapeHtml(JSON.stringify(requestJson.schema || {}, null, 2))}</div>
            `)}

            ${accordionItem("op-request-examples", "Request Examples", `
                <div class="d-flex flex-wrap gap-2 mb-3">
                    <button class="btn btn-sm btn-outline-primary" onclick='addRequestExample(${JSON.stringify(pathKey)}, ${JSON.stringify(method)})'>Add Example</button>
                    <button class="btn btn-sm btn-outline-success" onclick='convertFirstRequestExampleToSchema(${JSON.stringify(pathKey)}, ${JSON.stringify(method)})'>Example To Schema</button>
                </div>
                ${renderExampleList(pathKey, method, "request", requestExamples)}
            `)}

            ${accordionItem("op-responses", "Responses", `
                <div class="d-flex flex-wrap gap-2 mb-3">
                    <button class="btn btn-sm btn-outline-success" onclick='addResponseCode(${JSON.stringify(pathKey)}, ${JSON.stringify(method)}, "success")'>Add Success</button>
                    <button class="btn btn-sm btn-outline-danger" onclick='addResponseCode(${JSON.stringify(pathKey)}, ${JSON.stringify(method)}, "error")'>Add Error</button>
                    <button class="btn btn-sm btn-outline-warning" onclick='addResponseCode(${JSON.stringify(pathKey)}, ${JSON.stringify(method)}, "other")'>Add Other</button>
                </div>
                ${responseCodes.length ? responseCodes.map(code => renderResponseEditorSummary(pathKey, method, code)).join("") : "<div class='text-muted'>No responses</div>"}
            `)}

            ${accordionItem("op-necessary", "Recommended / Necessary Additions", `
                <div class="small text-muted">
                    Included suggestions:
                    <ul class="mb-0 mt-2">
                        <li>Use reusable schema refs where possible</li>
                        <li>Add request examples and response examples</li>
                        <li>Include at least one success and one error response</li>
                        <li>Keep schema examples updated for API consumers</li>
                    </ul>
                </div>
            `)}
        </div>
    `);
}

function renderResponseEditorSummary(pathKey, method, code) {
    const op = ensurePathOperation(pathKey, method);
    const res = op.responses[code] || {};
    const json = ensureResponseJson(op, code);
    const examples = json.examples || {};
    const badge = classifyResponseCode(code) === "success"
        ? "success"
        : classifyResponseCode(code) === "error"
            ? "danger"
            : "warning";

    return `
        <div class="example-box mb-2">
            <div class="d-flex justify-content-between align-items-start">
                <div>
                    <span class="badge text-bg-${badge}">${escapeHtml(code)}</span>
                    <div class="fw-semibold mt-2">${escapeHtml(res.description || "")}</div>
                    <div class="small text-muted">Examples: ${Object.keys(examples).length}</div>
                </div>
                <div class="d-flex gap-2">
                    <button class="btn btn-sm btn-primary" onclick='openResponseEditor(${JSON.stringify(pathKey)}, ${JSON.stringify(method)}, ${JSON.stringify(code)})'>Edit</button>
                    <button class="btn btn-sm btn-danger" onclick='deleteResponseCode(${JSON.stringify(pathKey)}, ${JSON.stringify(method)}, ${JSON.stringify(code)})'>Delete</button>
                </div>
            </div>
        </div>
    `;
}

function renderExampleList(pathKey, method, mode, examples) {
    const keys = Object.keys(examples || {});
    if (!keys.length) return "<div class='text-muted'>No examples</div>";

    return keys.map(key => `
        <div class="example-box mb-2">
            <div class="d-flex justify-content-between align-items-start">
                <div>
                    <strong>${escapeHtml(key)}</strong>
                    <div class="small text-muted">${escapeHtml(examples[key]?.summary || "")}</div>
                    <div class="pre-json mt-2">${escapeHtml(JSON.stringify(examples[key]?.value || {}, null, 2))}</div>
                </div>
                <div class="d-flex gap-2">
                    <button class="btn btn-sm btn-primary" onclick='editExample(${JSON.stringify(pathKey)}, ${JSON.stringify(method)}, ${JSON.stringify(mode)}, ${JSON.stringify(key)})'>Edit</button>
                    <button class="btn btn-sm btn-danger" onclick='deleteExample(${JSON.stringify(pathKey)}, ${JSON.stringify(method)}, ${JSON.stringify(mode)}, ${JSON.stringify(key)})'>Delete</button>
                </div>
            </div>
        </div>
    `).join("");
}

function saveOperationEditor(pathKey, method) {
    const op = ensurePathOperation(pathKey, method);
    op.summary = document.getElementById("op-summary").value;
    op.description = document.getElementById("op-description").value;
    syncAllViews();
}

function addOperationParameter(pathKey, method) {
    const op = ensurePathOperation(pathKey, method);
    op.parameters.push({
        name: `param${op.parameters.length + 1}`,
        in: "query",
        required: false,
        schema: { type: "string" }
    });
    syncAllViews();
    openOperationEditor(pathKey, method);
}

function editOperationParameter(pathKey, method, index) {
    const op = ensurePathOperation(pathKey, method);
    const p = op.parameters[index];
    openModalEditor("Edit Parameter", "Adjust name, location and type.", `
        <div class="accordion">
            ${accordionItem("param-main", "Parameter", `
                <div class="row g-3">
                    <div class="col-md-4">
                        <label class="form-label">Name</label>
                        <input id="param-name" class="form-control" value="${escapeHtml(p.name || "")}">
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">In</label>
                        <select id="param-in" class="form-select">
                            <option value="query" ${p.in === "query" ? "selected" : ""}>query</option>
                            <option value="path" ${p.in === "path" ? "selected" : ""}>path</option>
                            <option value="header" ${p.in === "header" ? "selected" : ""}>header</option>
                            <option value="cookie" ${p.in === "cookie" ? "selected" : ""}>cookie</option>
                        </select>
                    </div>
                    <div class="col-md-4">
                        <label class="form-label">Type</label>
                        <select id="param-type" class="form-select">
                            <option value="string" ${(p.schema?.type || "string") === "string" ? "selected" : ""}>string</option>
                            <option value="integer" ${(p.schema?.type || "") === "integer" ? "selected" : ""}>integer</option>
                            <option value="number" ${(p.schema?.type || "") === "number" ? "selected" : ""}>number</option>
                            <option value="boolean" ${(p.schema?.type || "") === "boolean" ? "selected" : ""}>boolean</option>
                        </select>
                    </div>
                    <div class="col-12">
                        <button class="btn btn-primary" onclick='saveOperationParameter(${JSON.stringify(pathKey)}, ${JSON.stringify(method)}, ${index})'>Save</button>
                    </div>
                </div>
            `, true)}
        </div>
    `);
}

function saveOperationParameter(pathKey, method, index) {
    const op = ensurePathOperation(pathKey, method);
    op.parameters[index] = {
        name: document.getElementById("param-name").value.trim(),
        in: document.getElementById("param-in").value,
        schema: { type: document.getElementById("param-type").value },
        required: false
    };
    syncAllViews();
    openOperationEditor(pathKey, method);
}

function deleteOperationParameter(pathKey, method, index) {
    const op = ensurePathOperation(pathKey, method);
    op.parameters.splice(index, 1);
    syncAllViews();
    openOperationEditor(pathKey, method);
}

/* ---------------- Request / Response / Example handling ---------------- */

function setRequestSchemaType(pathKey, method, type) {
    const op = ensurePathOperation(pathKey, method);
    const json = ensureRequestJson(op);
    if (type === "object") json.schema = { type: "object", properties: {} };
    else if (type === "array") json.schema = { type: "array", items: { type: "object", properties: {} } };
    else json.schema = { type };
    syncAllViews();
    openOperationEditor(pathKey, method);
}

function useRequestSchemaRef(pathKey, method) {
    ensureComponents();
    const names = Object.keys(currentSpec.components.schemas || {});
    if (!names.length) return alert("No schemas available.");
    const choice = prompt(`Enter schema name:\n${names.join(", ")}`, names[0]);
    if (!choice) return;
    const op = ensurePathOperation(pathKey, method);
    const json = ensureRequestJson(op);
    json.schema = { "$ref": `#/components/schemas/${choice}` };
    syncAllViews();
    openOperationEditor(pathKey, method);
}

function addRequestExample(pathKey, method) {
    const op = ensurePathOperation(pathKey, method);
    const json = ensureRequestJson(op);
    if (!json.examples) json.examples = {};
    const key = prompt("Example key:", `example${Object.keys(json.examples).length + 1}`);
    if (!key) return;
    const summary = prompt("Example summary:", key) || key;
    const text = prompt("Example JSON value:", '{"name":"John","email":"john@example.com"}');
    if (text == null) return;
    try {
        json.examples[key] = { summary, value: JSON.parse(text) };
        syncAllViews();
        openOperationEditor(pathKey, method);
    } catch {
        alert("Invalid JSON.");
    }
}

function convertFirstRequestExampleToSchema(pathKey, method) {
    const op = ensurePathOperation(pathKey, method);
    const json = ensureRequestJson(op);
    const keys = Object.keys(json.examples || {});
    if (!keys.length) return alert("No request examples available.");
    json.schema = inferSchemaFromExample(json.examples[keys[0]].value);
    syncAllViews();
    openOperationEditor(pathKey, method);
}

function addResponseCode(pathKey, method, group) {
    const op = ensurePathOperation(pathKey, method);
    let code = group === "success" ? "200" : group === "error" ? "400" : "300";
    while (op.responses[code]) code = String(Number(code) + 1);
    op.responses[code] = {
        description: "Response",
        content: { "application/json": { examples: {} } }
    };
    syncAllViews();
    openOperationEditor(pathKey, method);
}

function deleteResponseCode(pathKey, method, code) {
    const op = ensurePathOperation(pathKey, method);
    delete op.responses[code];
    syncAllViews();
    openOperationEditor(pathKey, method);
}

function openResponseEditor(pathKey, method, code) {
    const op = ensurePathOperation(pathKey, method);
    const res = op.responses[code];
    const json = ensureResponseJson(op, code);
    const examples = json.examples || {};

    openModalEditor(`Edit Response ${code}`, "Manage response schema and one or more examples.", `
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
                        <button class="btn btn-primary" onclick='saveResponseEditor(${JSON.stringify(pathKey)}, ${JSON.stringify(method)}, ${JSON.stringify(code)})'>Save</button>
                    </div>
                </div>
            `, true)}

            ${accordionItem("response-schema", "Response Schema", `
                <div class="d-flex flex-wrap gap-2 mb-3">
                    <button class="btn btn-sm btn-outline-primary" onclick='setResponseSchemaType(${JSON.stringify(pathKey)}, ${JSON.stringify(method)}, ${JSON.stringify(code)}, "object")'>Object</button>
                    <button class="btn btn-sm btn-outline-primary" onclick='setResponseSchemaType(${JSON.stringify(pathKey)}, ${JSON.stringify(method)}, ${JSON.stringify(code)}, "array")'>Array</button>
                    <button class="btn btn-sm btn-outline-primary" onclick='setResponseSchemaType(${JSON.stringify(pathKey)}, ${JSON.stringify(method)}, ${JSON.stringify(code)}, "string")'>String</button>
                    <button class="btn btn-sm btn-outline-secondary" onclick='useResponseSchemaRef(${JSON.stringify(pathKey)}, ${JSON.stringify(method)}, ${JSON.stringify(code)})'>Use Schema Ref</button>
                </div>
                <div class="pre-json">${escapeHtml(JSON.stringify(json.schema || {}, null, 2))}</div>
            `)}

            ${accordionItem("response-examples", "Response Examples", `
                <div class="d-flex flex-wrap gap-2 mb-3">
                    <button class="btn btn-sm btn-outline-primary" onclick='addResponseExample(${JSON.stringify(pathKey)}, ${JSON.stringify(method)}, ${JSON.stringify(code)})'>Add Example</button>
                    <button class="btn btn-sm btn-outline-success" onclick='convertFirstResponseExampleToSchema(${JSON.stringify(pathKey)}, ${JSON.stringify(method)}, ${JSON.stringify(code)})'>Example To Schema</button>
                </div>
                ${renderResponseExampleList(pathKey, method, code, examples)}
            `)}
        </div>
    `);
}

function saveResponseEditor(pathKey, method, oldCode) {
    const op = ensurePathOperation(pathKey, method);
    const newCode = document.getElementById("response-code").value.trim();
    const desc = document.getElementById("response-description").value;
    if (!newCode) return alert("Code required");
    const value = op.responses[oldCode];
    value.description = desc;
    if (newCode !== oldCode) {
        op.responses[newCode] = value;
        delete op.responses[oldCode];
    }
    syncAllViews();
    openOperationEditor(pathKey, method);
}

function setResponseSchemaType(pathKey, method, code, type) {
    const op = ensurePathOperation(pathKey, method);
    const json = ensureResponseJson(op, code);
    if (type === "object") json.schema = { type: "object", properties: {} };
    else if (type === "array") json.schema = { type: "array", items: { type: "object", properties: {} } };
    else json.schema = { type };
    syncAllViews();
    openResponseEditor(pathKey, method, code);
}

function useResponseSchemaRef(pathKey, method, code) {
    ensureComponents();
    const names = Object.keys(currentSpec.components.schemas || {});
    if (!names.length) return alert("No schemas available.");
    const choice = prompt(`Enter schema name:\n${names.join(", ")}`, names[0]);
    if (!choice) return;
    const op = ensurePathOperation(pathKey, method);
    const json = ensureResponseJson(op, code);
    json.schema = { "$ref": `#/components/schemas/${choice}` };
    syncAllViews();
    openResponseEditor(pathKey, method, code);
}

function addResponseExample(pathKey, method, code) {
    const op = ensurePathOperation(pathKey, method);
    const json = ensureResponseJson(op, code);
    if (!json.examples) json.examples = {};
    const key = prompt("Example key:", `example${Object.keys(json.examples).length + 1}`);
    if (!key) return;
    const summary = prompt("Example summary:", key) || key;
    const text = prompt("Example JSON value:", '{"message":"ok"}');
    if (text == null) return;
    try {
        json.examples[key] = { summary, value: JSON.parse(text) };
        syncAllViews();
        openResponseEditor(pathKey, method, code);
    } catch {
        alert("Invalid JSON.");
    }
}

function convertFirstResponseExampleToSchema(pathKey, method, code) {
    const op = ensurePathOperation(pathKey, method);
    const json = ensureResponseJson(op, code);
    const keys = Object.keys(json.examples || {});
    if (!keys.length) return alert("No response examples available.");
    json.schema = inferSchemaFromExample(json.examples[keys[0]].value);
    syncAllViews();
    openResponseEditor(pathKey, method, code);
}

function renderResponseExampleList(pathKey, method, code, examples) {
    const keys = Object.keys(examples || {});
    if (!keys.length) return "<div class='text-muted'>No response examples</div>";

    return keys.map(key => `
        <div class="example-box mb-2">
            <div class="d-flex justify-content-between align-items-start">
                <div>
                    <strong>${escapeHtml(key)}</strong>
                    <div class="small text-muted">${escapeHtml(examples[key]?.summary || "")}</div>
                    <div class="pre-json mt-2">${escapeHtml(JSON.stringify(examples[key]?.value || {}, null, 2))}</div>
                </div>
                <div class="d-flex gap-2">
                    <button class="btn btn-sm btn-primary" onclick='editResponseExample(${JSON.stringify(pathKey)}, ${JSON.stringify(method)}, ${JSON.stringify(code)}, ${JSON.stringify(key)})'>Edit</button>
                    <button class="btn btn-sm btn-danger" onclick='deleteResponseExample(${JSON.stringify(pathKey)}, ${JSON.stringify(method)}, ${JSON.stringify(code)}, ${JSON.stringify(key)})'>Delete</button>
                </div>
            </div>
        </div>
    `).join("");
}

function editExample(pathKey, method, mode, key) {
    const op = ensurePathOperation(pathKey, method);
    const source = mode === "request"
        ? ensureRequestJson(op)
        : null;
    if (!source || !source.examples || !source.examples[key]) return;

    const current = source.examples[key];
    const newSummary = prompt("Summary:", current.summary || key);
    if (newSummary == null) return;
    const newValue = prompt("Example JSON:", JSON.stringify(current.value || {}, null, 2));
    if (newValue == null) return;

    try {
        source.examples[key] = { summary: newSummary, value: JSON.parse(newValue) };
        syncAllViews();
        openOperationEditor(pathKey, method);
    } catch {
        alert("Invalid JSON.");
    }
}

function deleteExample(pathKey, method, mode, key) {
    const op = ensurePathOperation(pathKey, method);
    const source = mode === "request"
        ? ensureRequestJson(op)
        : null;
    if (!source || !source.examples) return;
    delete source.examples[key];
    syncAllViews();
    openOperationEditor(pathKey, method);
}

function editResponseExample(pathKey, method, code, key) {
    const op = ensurePathOperation(pathKey, method);
    const json = ensureResponseJson(op, code);
    if (!json.examples || !json.examples[key]) return;
    const current = json.examples[key];
    const newSummary = prompt("Summary:", current.summary || key);
    if (newSummary == null) return;
    const newValue = prompt("Example JSON:", JSON.stringify(current.value || {}, null, 2));
    if (newValue == null) return;

    try {
        json.examples[key] = { summary: newSummary, value: JSON.parse(newValue) };
        syncAllViews();
        openResponseEditor(pathKey, method, code);
    } catch {
        alert("Invalid JSON.");
    }
}

function deleteResponseExample(pathKey, method, code, key) {
    const op = ensurePathOperation(pathKey, method);
    const json = ensureResponseJson(op, code);
    if (!json.examples) return;
    delete json.examples[key];
    syncAllViews();
    openResponseEditor(pathKey, method, code);
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
    syncAllViews();
}

function deletePath(pathKey) {
    if (!confirm(`Delete ${pathKey}?`)) return;
    delete currentSpec.paths[pathKey];
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
    syncAllViews();
    openOperationEditor(pathKey, method);
}

function deleteOperation(pathKey, method) {
    if (!confirm(`Delete ${method.toUpperCase()} ${pathKey}?`)) return;
    delete currentSpec.paths[pathKey][method];
    if (!Object.keys(currentSpec.paths[pathKey]).length) delete currentSpec.paths[pathKey];
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
    currentSpec.components.schemas[candidate] = { type: "object", properties: {}, example: {} };
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
    syncAllViews();
    await refreshSpecList(document.getElementById("spec-search")?.value || "");
}

async function saveAsNewSpec() {
    const name = document.getElementById("spec-name")?.value.trim();
    if (!name) return alert("Please enter a spec name.");
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
    const savedTheme = localStorage.getItem("swagger-studio-theme") || "light";
    applyTheme(savedTheme);
    updateEditorModeUi();

    initMonacoEditor(window.INITIAL_YAML || "");

    const waitForMonaco = setInterval(async () => {
        if (monacoEditor) {
            clearInterval(waitForMonaco);
            currentSpec = jsyaml.load(window.INITIAL_YAML || "{}");
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

README = r'''# Swagger Studio v9.2

Features:
- collapsible panels and collapsible design cards
- servers collapsible
- schemas collapsible
- paths and operations collapsible
- multiple request examples
- multiple response examples
- request example to schema
- response example to schema
- schema example editor
- Bootstrap 5 UI
- raw YAML/JSON panel
- live preview panel
- save/load/import/export

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
