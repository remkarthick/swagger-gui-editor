let swaggerUiInstance = null;
let suppressAutoGenerate = false;
let editorMode = "yaml";
let lastParsedSpec = null;
let monacoEditor = null;

let isUpdatingEditorProgrammatically = false;
let isUpdatingFromGui = false;
let isUpdatingFromEditor = false;

/* -------------------- Theme -------------------- */

function applyTheme(theme) {
    document.body.classList.toggle("light-theme", theme === "light");
    localStorage.setItem("neo-swagger-theme", theme);

    const btn = document.getElementById("theme-toggle-btn");
    if (btn) {
        btn.textContent = theme === "light" ? "Dark Mode" : "Light Mode";
    }

    if (window.monaco && monacoEditor) {
        monaco.editor.setTheme(theme === "light" ? "vs" : "vs-dark");
    }
}

function toggleTheme() {
    const current = document.body.classList.contains("light-theme") ? "light" : "dark";
    applyTheme(current === "dark" ? "light" : "dark");
}

/* -------------------- Monaco Editor -------------------- */

function initMonacoEditor(initialText = "") {
    require.config({
        paths: {
            vs: "https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.45.0/min/vs"
        }
    });

    require(["vs/editor/editor.main"], function () {
        monacoEditor = monaco.editor.create(document.getElementById("yaml-editor"), {
            value: initialText,
            language: "yaml",
            theme: document.body.classList.contains("light-theme") ? "vs" : "vs-dark",
            automaticLayout: true,
            minimap: { enabled: false },
            fontSize: 13,
            wordWrap: "on",
            scrollBeyondLastLine: false,
            roundedSelection: true,
            lineNumbers: "on",
            folding: true,
            tabSize: 2,
            insertSpaces: true
        });

        monacoEditor.onDidChangeModelContent(() => {
            if (isUpdatingEditorProgrammatically) return;
            if (isUpdatingFromGui) return;
            debouncedYamlSync();
        });
    });
}

function getEditorText() {
    return monacoEditor ? monacoEditor.getValue() : "";
}

function setEditorText(text) {
    if (!monacoEditor) return;

    const current = monacoEditor.getValue();
    const next = text || "";

    if (current === next) return;

    isUpdatingEditorProgrammatically = true;
    monacoEditor.setValue(next);

    setTimeout(() => {
        isUpdatingEditorProgrammatically = false;
    }, 0);
}

function setEditorLanguage(mode) {
    if (!monacoEditor || !window.monaco) return;
    const model = monacoEditor.getModel();
    if (!model) return;
    monaco.editor.setModelLanguage(model, mode === "json" ? "json" : "yaml");
}

/* -------------------- Swagger Preview -------------------- */

function initSwaggerUI(spec) {
    const el = document.getElementById("swagger-ui");
    if (!el) return;

    el.innerHTML = "";
    swaggerUiInstance = SwaggerUIBundle({
        spec: spec,
        dom_id: "#swagger-ui"
    });
}

function initSwaggerUIWithErrorFallback(spec) {
    try {
        initSwaggerUI(spec);
    } catch (e) {
        console.error(e);
    }
}

/* -------------------- Helpers -------------------- */

function escapeHtml(str) {
    return String(str ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function prettyJson(value) {
    if (value === undefined || value === null) return "";
    if (typeof value === "string") return value;
    return JSON.stringify(value, null, 2);
}

function debounce(func, wait) {
    let timeout;
    return function () {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, arguments), wait);
    };
}

function triggerGenerateIfAllowed() {
    if (!suppressAutoGenerate) {
        generateFromForm();
    }
}

function parseEditorContent(text) {
    if (!text.trim()) return {};
    try {
        return JSON.parse(text);
    } catch {
        return jsyaml.load(text);
    }
}

function specToYaml(spec) {
    return jsyaml.dump(spec, { noRefs: true, lineWidth: -1 });
}

function updateEditorModeUi() {
    const label = document.getElementById("editor-mode-label");
    const yamlBtn = document.getElementById("view-yaml-btn");
    const jsonBtn = document.getElementById("view-json-btn");

    if (label) label.textContent = `Viewing: ${editorMode.toUpperCase()}`;
    if (yamlBtn) yamlBtn.classList.toggle("toggle-active", editorMode === "yaml");
    if (jsonBtn) jsonBtn.classList.toggle("toggle-active", editorMode === "json");

    setEditorLanguage(editorMode);
}

function getDownloadBaseName() {
    const rawName = document.getElementById("spec-name")?.value?.trim() || "openapi-spec";
    return rawName.replace(/[^a-zA-Z0-9-_]+/g, "_");
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

/* -------------------- Downloads -------------------- */

function downloadCurrentYaml() {
    try {
        const parsed = parseEditorContent(getEditorText());
        const yamlText = specToYaml(parsed);
        downloadTextFile(`${getDownloadBaseName()}.yaml`, yamlText, "text/yaml");
    } catch (e) {
        console.error(e);
        alert("Cannot download YAML. Current content is invalid.");
    }
}

function downloadCurrentJson() {
    try {
        const parsed = parseEditorContent(getEditorText());
        const jsonText = JSON.stringify(parsed, null, 2);
        downloadTextFile(`${getDownloadBaseName()}.json`, jsonText, "application/json");
    } catch (e) {
        console.error(e);
        alert("Cannot download JSON. Current content is invalid.");
    }
}

/* -------------------- YAML / JSON Mode -------------------- */

function setEditorMode(mode) {
    if (mode === editorMode) return;

    try {
        const parsed = parseEditorContent(getEditorText());
        lastParsedSpec = parsed;

        if (mode === "json") {
            setEditorText(JSON.stringify(parsed, null, 2));
            editorMode = "json";
        } else {
            setEditorText(specToYaml(parsed));
            editorMode = "yaml";
        }

        updateEditorModeUi();
    } catch (e) {
        console.error(e);
        alert("Cannot switch view. Current editor content is invalid.");
    }
}

/* -------------------- Collapse -------------------- */

function toggleSectionBody(headerEl) {
    const body = headerEl.nextElementSibling;
    const icon = headerEl.querySelector(".collapse-icon");
    if (!body || !icon) return;
    body.classList.toggle("collapsed");
    icon.textContent = body.classList.contains("collapsed") ? "▶" : "▼";
}

function togglePathCard(headerEl) {
    const body = headerEl.nextElementSibling;
    const icon = headerEl.querySelector(".collapse-icon");
    if (!body || !icon) return;
    body.classList.toggle("collapsed");
    icon.textContent = body.classList.contains("collapsed") ? "▶" : "▼";
}

function toggleSchemaField(headerEl) {
    const body = headerEl.nextElementSibling;
    const icon = headerEl.querySelector(".collapse-icon");
    if (!body || !icon) return;
    body.classList.toggle("collapsed");
    icon.textContent = body.classList.contains("collapsed") ? "▶" : "▼";
}

function toggleMiniCard(headerEl) {
    const body = headerEl.nextElementSibling;
    const icon = headerEl.querySelector(".collapse-icon");
    if (!body || !icon) return;
    body.classList.toggle("collapsed");
    icon.textContent = body.classList.contains("collapsed") ? "▶" : "▼";
}

/* -------------------- Panel Toggle -------------------- */

function togglePanel(panelId) {
    const panel = document.getElementById(panelId);
    if (!panel) return;

    panel.classList.toggle("hidden");
    updateSplitterVisibility();
    normalizeVisiblePanelWidths();
}

function updateSplitterVisibility() {
    const left = document.getElementById("left-panel");
    const middle = document.getElementById("middle-panel");
    const right = document.getElementById("right-panel");

    const splitterLeft = document.getElementById("splitter-left");
    const splitterRight = document.getElementById("splitter-right");

    if (splitterLeft && left && middle) {
        splitterLeft.classList.toggle("hidden", left.classList.contains("hidden") || middle.classList.contains("hidden"));
    }

    if (splitterRight && middle && right) {
        splitterRight.classList.toggle("hidden", middle.classList.contains("hidden") || right.classList.contains("hidden"));
    }
}

function normalizeVisiblePanelWidths() {
    const panels = [
        document.getElementById("left-panel"),
        document.getElementById("middle-panel"),
        document.getElementById("right-panel")
    ].filter(Boolean).filter(p => !p.classList.contains("hidden"));

    if (!panels.length) return;

    const width = `${100 / panels.length}%`;
    panels.forEach(p => p.style.width = width);
}

/* -------------------- Resizable Panels -------------------- */

function initResizablePanels() {
    const container = document.getElementById("main-container");
    const leftPanel = document.getElementById("left-panel");
    const middlePanel = document.getElementById("middle-panel");
    const rightPanel = document.getElementById("right-panel");
    const splitterLeft = document.getElementById("splitter-left");
    const splitterRight = document.getElementById("splitter-right");

    let activeSplitter = null;

    function onMouseMove(e) {
        if (!activeSplitter || !container) return;

        const rect = container.getBoundingClientRect();
        const totalWidth = rect.width;
        const x = e.clientX - rect.left;

        if (
            activeSplitter === splitterLeft &&
            leftPanel && middlePanel &&
            !leftPanel.classList.contains("hidden") &&
            !middlePanel.classList.contains("hidden")
        ) {
            let leftWidth = (x / totalWidth) * 100;
            if (leftWidth < 12) leftWidth = 12;
            if (leftWidth > 70) leftWidth = 70;

            const rightWidth = rightPanel && !rightPanel.classList.contains("hidden")
                ? parseFloat(rightPanel.style.width || 35)
                : 0;

            const middleWidth = 100 - leftWidth - rightWidth;
            if (middleWidth >= 12) {
                leftPanel.style.width = `${leftWidth}%`;
                middlePanel.style.width = `${middleWidth}%`;
            }
        }

        if (
            activeSplitter === splitterRight &&
            middlePanel && rightPanel &&
            !middlePanel.classList.contains("hidden") &&
            !rightPanel.classList.contains("hidden")
        ) {
            const leftWidth = leftPanel && !leftPanel.classList.contains("hidden")
                ? parseFloat(leftPanel.style.width || 34)
                : 0;

            let middleWidth = (x / totalWidth) * 100 - leftWidth;
            if (middleWidth < 12) middleWidth = 12;
            if (middleWidth > 70) middleWidth = 70;

            const rightWidth = 100 - leftWidth - middleWidth;
            if (rightWidth >= 12) {
                middlePanel.style.width = `${middleWidth}%`;
                rightPanel.style.width = `${rightWidth}%`;
            }
        }
    }

    function onMouseUp() {
        activeSplitter = null;
        document.body.style.cursor = "default";
        document.body.style.userSelect = "auto";
    }

    if (splitterLeft) {
        splitterLeft.addEventListener("mousedown", () => {
            activeSplitter = splitterLeft;
            document.body.style.cursor = "col-resize";
            document.body.style.userSelect = "none";
        });
    }

    if (splitterRight) {
        splitterRight.addEventListener("mousedown", () => {
            activeSplitter = splitterRight;
            document.body.style.cursor = "col-resize";
            document.body.style.userSelect = "none";
        });
    }

    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
}

/* -------------------- Schema Inference -------------------- */

function inferSchemaFromExample(example) {
    if (example === null) return { type: "string" };

    if (Array.isArray(example)) {
        if (example.length === 0) {
            return { type: "array", items: { type: "string" } };
        }
        return { type: "array", items: inferSchemaFromExample(example[0]) };
    }

    if (typeof example === "object") {
        const properties = {};
        const required = [];

        Object.keys(example).forEach(key => {
            properties[key] = inferSchemaFromExample(example[key]);
            required.push(key);
        });

        const schema = {
            type: "object",
            properties
        };

        if (required.length > 0) {
            schema.required = required;
        }

        return schema;
    }

    if (typeof example === "string") return { type: "string" };
    if (typeof example === "number") return Number.isInteger(example) ? { type: "integer" } : { type: "number" };
    if (typeof example === "boolean") return { type: "boolean" };

    return { type: "string" };
}

/* -------------------- Example Helpers -------------------- */

function addExampleBlock(container, data = {}, typeLabel = "Example") {
    if (!container) return;

    const index = container.querySelectorAll(".example-block").length + 1;

    const block = document.createElement("div");
    block.className = "example-block";
    block.innerHTML = `
        <div class="mini-card-header" onclick="toggleMiniCard(this)">
            <div class="mini-card-title">${escapeHtml(data.key || `${typeLabel} ${index}`)}</div>
            <span class="collapse-icon">▼</span>
        </div>
        <div class="mini-card-body">
            <div class="inline-row">
                <div>
                    <label>Example Key</label>
                    <input type="text" class="example-key" value="${escapeHtml(data.key || "")}" placeholder="basicExample">
                </div>
                <div>
                    <label>Summary</label>
                    <input type="text" class="example-summary" value="${escapeHtml(data.summary || "")}" placeholder="Example summary">
                </div>
            </div>

            <label>Example JSON</label>
            <textarea class="example-value" placeholder='{"name":"John"}'>${escapeHtml(data.value || "")}</textarea>
            <button type="button" class="small-btn remove-example-btn">Remove Example</button>
        </div>
    `;

    container.appendChild(block);

    const keyInput = block.querySelector(".example-key");
    const title = block.querySelector(".mini-card-title");

    keyInput.addEventListener("input", () => {
        title.textContent = keyInput.value.trim() || `${typeLabel} ${index}`;
    });

    block.querySelector(".remove-example-btn").addEventListener("click", () => {
        block.remove();
        const pathBlock = container.closest(".path-card-body");
        refreshExampleSelectors(pathBlock);
        triggerGenerateIfAllowed();
    });
}

function collectExamples(container) {
    if (!container) return [];
    return Array.from(container.querySelectorAll(".example-block")).map(block => ({
        key: block.querySelector(".example-key")?.value || "",
        summary: block.querySelector(".example-summary")?.value || "",
        value: block.querySelector(".example-value")?.value || ""
    }));
}

function refreshExampleSelectors(pathBlock) {
    if (!pathBlock) return;

    const reqExamples = collectExamples(pathBlock.querySelector(".request-examples-container"));
    const resExamples = collectExamples(pathBlock.querySelector(".response-examples-container"));

    const reqSelect = pathBlock.querySelector(".request-example-select");
    const resSelect = pathBlock.querySelector(".response-example-select");

    if (reqSelect) {
        const current = reqSelect.value;
        reqSelect.innerHTML = `<option value="">Select Request Example</option>` +
            reqExamples.map((ex, i) =>
                `<option value="${i}">${escapeHtml(ex.key || `requestExample${i + 1}`)}</option>`
            ).join("");
        if (current && reqExamples[Number(current)]) reqSelect.value = current;
    }

    if (resSelect) {
        const current = resSelect.value;
        resSelect.innerHTML = `<option value="">Select Response Example</option>` +
            resExamples.map((ex, i) =>
                `<option value="${i}">${escapeHtml(ex.key || `responseExample${i + 1}`)}</option>`
            ).join("");
        if (current && resExamples[Number(current)]) resSelect.value = current;
    }
}

/* -------------------- Schema Builder -------------------- */

function createEmptyField(data = {}) {
    return {
        name: data.name || "",
        type: data.type || "string",
        required: !!data.required,
        children: Array.isArray(data.children) ? data.children : [],
        arrayItemType: data.arrayItemType || "string",
        arrayChildren: Array.isArray(data.arrayChildren) ? data.arrayChildren : []
    };
}

function schemaFieldDisplayName(fieldData) {
    const name = fieldData.name || "Unnamed Property";
    const type = fieldData.type || "string";
    return `${name} : ${type}`;
}

function addSchemaField(container, data = {}) {
    if (!container) return;

    const field = document.createElement("div");
    field.className = "schema-field";

    const fieldData = createEmptyField(data);

    field.innerHTML = `
        <div class="schema-field-header" onclick="toggleSchemaField(this)">
            <div class="schema-field-title">${escapeHtml(schemaFieldDisplayName(fieldData))}</div>
            <span class="collapse-icon">▼</span>
        </div>

        <div class="schema-field-body">
            <div class="schema-inline">
                <div>
                    <label>Property Name</label>
                    <input type="text" class="schema-name" value="${escapeHtml(fieldData.name)}" placeholder="name">
                </div>
                <div>
                    <label>Type</label>
                    <select class="schema-type">
                        <option value="string" ${fieldData.type === "string" ? "selected" : ""}>string</option>
                        <option value="integer" ${fieldData.type === "integer" ? "selected" : ""}>integer</option>
                        <option value="number" ${fieldData.type === "number" ? "selected" : ""}>number</option>
                        <option value="boolean" ${fieldData.type === "boolean" ? "selected" : ""}>boolean</option>
                        <option value="object" ${fieldData.type === "object" ? "selected" : ""}>object</option>
                        <option value="array" ${fieldData.type === "array" ? "selected" : ""}>array</option>
                    </select>
                </div>
            </div>

            <div class="checkbox-row">
                <input type="checkbox" class="schema-required" ${fieldData.required ? "checked" : ""}>
                <label>Required</label>
            </div>

            <div class="array-config" style="display:none;">
                <label>Array Item Type</label>
                <select class="schema-array-item-type">
                    <option value="string" ${fieldData.arrayItemType === "string" ? "selected" : ""}>string</option>
                    <option value="integer" ${fieldData.arrayItemType === "integer" ? "selected" : ""}>integer</option>
                    <option value="number" ${fieldData.arrayItemType === "number" ? "selected" : ""}>number</option>
                    <option value="boolean" ${fieldData.arrayItemType === "boolean" ? "selected" : ""}>boolean</option>
                    <option value="object" ${fieldData.arrayItemType === "object" ? "selected" : ""}>object</option>
                    <option value="array" ${fieldData.arrayItemType === "array" ? "selected" : ""}>array</option>
                </select>

                <div class="array-children-wrapper" style="display:none;">
                    <div class="muted">Define nested structure for array items</div>
                    <div class="schema-props array-children"></div>
                    <button type="button" class="success-btn add-array-child-btn">+ Add Nested Array Item Property</button>
                </div>
            </div>

            <div class="object-children-wrapper" style="display:none;">
                <div class="muted">Define nested object properties</div>
                <div class="schema-props object-children"></div>
                <button type="button" class="success-btn add-object-child-btn">+ Add Nested Property</button>
            </div>

            <div class="schema-actions">
                <button type="button" class="small-btn remove-schema-field">Remove Property</button>
            </div>
        </div>
    `;

    container.appendChild(field);

    const typeSelect = field.querySelector(".schema-type");
    const arrayConfig = field.querySelector(".array-config");
    const objectChildrenWrapper = field.querySelector(".object-children-wrapper");
    const arrayChildrenWrapper = field.querySelector(".array-children-wrapper");
    const arrayItemTypeSelect = field.querySelector(".schema-array-item-type");
    const objectChildren = field.querySelector(".object-children");
    const arrayChildren = field.querySelector(".array-children");
    const schemaName = field.querySelector(".schema-name");
    const schemaTitle = field.querySelector(".schema-field-title");

    function refreshFieldVisibility() {
        const type = typeSelect.value;
        arrayConfig.style.display = type === "array" ? "block" : "none";
        objectChildrenWrapper.style.display = type === "object" ? "block" : "none";

        const itemType = arrayItemTypeSelect.value;
        arrayChildrenWrapper.style.display =
            type === "array" && (itemType === "object" || itemType === "array")
                ? "block"
                : "none";

        schemaTitle.textContent = schemaFieldDisplayName({
            name: schemaName.value,
            type: typeSelect.value
        });
    }

    field.querySelector(".remove-schema-field").addEventListener("click", () => {
        field.remove();
        triggerGenerateIfAllowed();
    });

    field.querySelector(".add-object-child-btn").addEventListener("click", () => {
        addSchemaField(objectChildren);
        triggerGenerateIfAllowed();
    });

    field.querySelector(".add-array-child-btn").addEventListener("click", () => {
        addSchemaField(arrayChildren);
        triggerGenerateIfAllowed();
    });

    schemaName.addEventListener("input", refreshFieldVisibility);

    typeSelect.addEventListener("change", () => {
        refreshFieldVisibility();
        triggerGenerateIfAllowed();
    });

    arrayItemTypeSelect.addEventListener("change", () => {
        refreshFieldVisibility();
        triggerGenerateIfAllowed();
    });

    if (fieldData.type === "object" && Array.isArray(fieldData.children)) {
        fieldData.children.forEach(child => addSchemaField(objectChildren, child));
    }

    if (
        fieldData.type === "array" &&
        (fieldData.arrayItemType === "object" || fieldData.arrayItemType === "array") &&
        Array.isArray(fieldData.arrayChildren)
    ) {
        fieldData.arrayChildren.forEach(child => addSchemaField(arrayChildren, child));
    }

    refreshFieldVisibility();
}

function createSchemaBuilder(rootContainer, rootData = []) {
    if (!rootContainer) return;

    rootContainer.innerHTML = `
        <div class="schema-root">
            <div class="muted">Root schema is an object. Add properties below.</div>
            <div class="schema-props root-schema-props"></div>
            <button type="button" class="success-btn add-root-schema-field">+ Add Property</button>
        </div>
    `;

    const propsContainer = rootContainer.querySelector(".root-schema-props");

    rootContainer.querySelector(".add-root-schema-field").addEventListener("click", () => {
        addSchemaField(propsContainer);
        triggerGenerateIfAllowed();
    });

    if (Array.isArray(rootData)) {
        rootData.forEach(field => addSchemaField(propsContainer, field));
    }
}

function collectSchemaFields(container) {
    const fields = [];
    if (!container) return fields;

    container.querySelectorAll(":scope > .schema-field").forEach(fieldEl => {
        const type = fieldEl.querySelector(".schema-type").value;
        const name = fieldEl.querySelector(".schema-name").value.trim();
        const required = fieldEl.querySelector(".schema-required").checked;

        const field = {
            name,
            type,
            required,
            children: [],
            arrayItemType: "string",
            arrayChildren: []
        };

        if (type === "object") {
            const objectChildrenContainer = fieldEl.querySelector(".object-children");
            field.children = collectSchemaFields(objectChildrenContainer);
        }

        if (type === "array") {
            field.arrayItemType = fieldEl.querySelector(".schema-array-item-type").value;
            if (field.arrayItemType === "object" || field.arrayItemType === "array") {
                const arrayChildrenContainer = fieldEl.querySelector(".array-children");
                field.arrayChildren = collectSchemaFields(arrayChildrenContainer);
            }
        }

        fields.push(field);
    });

    return fields;
}

function visualFieldsToOpenApiSchema(fields) {
    const schema = {
        type: "object",
        properties: {}
    };

    const requiredList = [];

    for (const field of fields) {
        if (!field.name) continue;
        schema.properties[field.name] = convertFieldToSchema(field);
        if (field.required) requiredList.push(field.name);
    }

    if (requiredList.length > 0) schema.required = requiredList;
    return schema;
}

function convertFieldToSchema(field) {
    if (field.type === "object") {
        const objSchema = {
            type: "object",
            properties: {}
        };

        const requiredList = [];
        for (const child of field.children || []) {
            if (!child.name) continue;
            objSchema.properties[child.name] = convertFieldToSchema(child);
            if (child.required) requiredList.push(child.name);
        }

        if (requiredList.length > 0) objSchema.required = requiredList;
        return objSchema;
    }

    if (field.type === "array") {
        const arrSchema = { type: "array" };

        if (["string", "integer", "number", "boolean"].includes(field.arrayItemType)) {
            arrSchema.items = { type: field.arrayItemType };
        } else if (field.arrayItemType === "object") {
            arrSchema.items = visualFieldsToOpenApiSchema(field.arrayChildren || []);
        } else if (field.arrayItemType === "array") {
            arrSchema.items = {
                type: "array",
                items: visualArrayChildrenToArrayItems(field.arrayChildren || [])
            };
        } else {
            arrSchema.items = { type: "string" };
        }

        return arrSchema;
    }

    return { type: field.type };
}

function visualArrayChildrenToArrayItems(children) {
    if (children && children.length > 0) {
        return visualFieldsToOpenApiSchema(children);
    }
    return { type: "string" };
}

function openApiSchemaToVisualFields(schema) {
    if (!schema) return [];
    if (schema.type !== "object") return [];
    const props = schema.properties || {};
    const requiredList = schema.required || [];

    return Object.keys(props).map(propName =>
        openApiPropertyToVisualField(propName, props[propName], requiredList.includes(propName))
    );
}

function openApiPropertyToVisualField(name, propSchema, isRequired) {
    const propType = propSchema?.type || "string";

    if (propType === "object") {
        return {
            name,
            type: "object",
            required: isRequired,
            children: openApiSchemaToVisualFields(propSchema),
            arrayItemType: "string",
            arrayChildren: []
        };
    }

    if (propType === "array") {
        const itemType = propSchema?.items?.type || "string";

        if (itemType === "object") {
            return {
                name,
                type: "array",
                required: isRequired,
                children: [],
                arrayItemType: "object",
                arrayChildren: openApiSchemaToVisualFields(propSchema.items)
            };
        }

        if (itemType === "array") {
            let nestedChildren = [];
            if (propSchema.items.items && propSchema.items.items.type === "object") {
                nestedChildren = openApiSchemaToVisualFields(propSchema.items.items);
            }

            return {
                name,
                type: "array",
                required: isRequired,
                children: [],
                arrayItemType: "array",
                arrayChildren: nestedChildren
            };
        }

        return {
            name,
            type: "array",
            required: isRequired,
            children: [],
            arrayItemType: itemType,
            arrayChildren: []
        };
    }

    return {
        name,
        type: propType,
        required: isRequired,
        children: [],
        arrayItemType: "string",
        arrayChildren: []
    };
}

/* -------------------- Variant Helpers -------------------- */

function addSchemaVariant(container, builderClass, data = {}, label = "Variant") {
    if (!container) return;

    const index = container.querySelectorAll(".schema-variant-card").length + 1;

    const card = document.createElement("div");
    card.className = "schema-variant-card";
    card.innerHTML = `
        <div class="mini-card-header" onclick="toggleMiniCard(this)">
            <div class="mini-card-title">${escapeHtml(data.name || `${label} ${index}`)}</div>
            <span class="collapse-icon">▼</span>
        </div>
        <div class="mini-card-body">
            <div class="inline-row">
                <div>
                    <label>Variant Name</label>
                    <input type="text" class="schema-variant-name" value="${escapeHtml(data.name || "")}" placeholder="variant${index}">
                </div>
                <div>
                    <label>&nbsp;</label>
                    <button type="button" class="small-btn remove-schema-variant-btn">Remove Variant</button>
                </div>
            </div>
            <div class="${builderClass}"></div>
        </div>
    `;

    container.appendChild(card);

    const nameInput = card.querySelector(".schema-variant-name");
    const title = card.querySelector(".mini-card-title");

    nameInput.addEventListener("input", () => {
        title.textContent = nameInput.value.trim() || `${label} ${index}`;
    });

    createSchemaBuilder(card.querySelector(`.${builderClass}`), data.fields || []);

    card.querySelector(".remove-schema-variant-btn").addEventListener("click", () => {
        card.remove();
        triggerGenerateIfAllowed();
    });
}

function collectSchemaVariants(container, builderClass, mode) {
    if (!container) return [];

    const cards = Array.from(container.querySelectorAll(".schema-variant-card"));
    const selectedCards = mode === "single" ? cards.slice(0, 1) : cards;

    return selectedCards.map((card, idx) => ({
        name: card.querySelector(".schema-variant-name")?.value.trim() || `variant${idx + 1}`,
        fields: collectSchemaFields(card.querySelector(`.${builderClass} .root-schema-props`))
    }));
}

function ensureSchemaVariantExists(pathBlock, kind) {
    const variantsContainer = pathBlock.querySelector(`.${kind}-schema-variants`);
    const mode = pathBlock.querySelector(`.${kind}-schema-mode`)?.value || "single";

    if (!variantsContainer) return;

    const existing = variantsContainer.querySelectorAll(".schema-variant-card");
    if (existing.length === 0) {
        addSchemaVariant(
            variantsContainer,
            `${kind}-schema-builder`,
            {},
            kind === "request" ? "Request Variant" : "Response Variant"
        );
    }

    const cards = variantsContainer.querySelectorAll(".schema-variant-card");
    cards.forEach((card, idx) => {
        card.style.display = mode === "single" ? (idx === 0 ? "block" : "none") : "block";
    });
}

function getSelectedVariantCard(pathBlock, kind) {
    const select = pathBlock.querySelector(`.${kind}-schema-variant-select`);
    const container = pathBlock.querySelector(`.${kind}-schema-variants`);
    if (!container) return null;

    const cards = Array.from(container.querySelectorAll(".schema-variant-card"));
    if (!cards.length) return null;

    const idx = select && select.value !== "" ? Number(select.value) : 0;
    return cards[idx] || cards[0];
}

function refreshVariantSelectors(pathBlock) {
    ["request", "response"].forEach(kind => {
        const select = pathBlock.querySelector(`.${kind}-schema-variant-select`);
        const container = pathBlock.querySelector(`.${kind}-schema-variants`);
        if (!select || !container) return;

        const current = select.value;
        const cards = Array.from(container.querySelectorAll(".schema-variant-card"));
        select.innerHTML = `<option value="">Select ${kind} schema variant</option>` +
            cards.map((card, i) => {
                const name = card.querySelector(".schema-variant-name")?.value.trim() || `${kind}Variant${i + 1}`;
                return `<option value="${i}">${escapeHtml(name)}</option>`;
            }).join("");

        if (current && cards[Number(current)]) {
            select.value = current;
        }
    });
}

function buildSchemaFromSelectedExample(pathBlock, kind) {
    const exampleSelect = pathBlock.querySelector(`.${kind}-example-select`);
    if (!exampleSelect || exampleSelect.value === "") {
        alert(`Please select a ${kind} example first.`);
        return;
    }

    const examples = collectExamples(pathBlock.querySelector(`.${kind}-examples-container`));
    const selectedExample = examples[Number(exampleSelect.value)];

    if (!selectedExample || !selectedExample.value.trim()) {
        alert(`Selected ${kind} example is empty.`);
        return;
    }

    ensureSchemaVariantExists(pathBlock, kind);
    const variantCard = getSelectedVariantCard(pathBlock, kind);

    if (!variantCard) {
        alert(`No ${kind} schema variant found.`);
        return;
    }

    try {
        const exampleObj = JSON.parse(selectedExample.value);
        const schema = inferSchemaFromExample(exampleObj);
        const visualFields = openApiSchemaToVisualFields(schema);

        createSchemaBuilder(
            variantCard.querySelector(`.${kind}-schema-builder`),
            visualFields
        );

        triggerGenerateIfAllowed();
    } catch (e) {
        console.error(e);
        alert(`Invalid selected ${kind} example JSON.`);
    }
}

/* -------------------- Servers -------------------- */

function addServer(url = "") {
    const container = document.getElementById("servers-container");
    if (!container) return;

    const div = document.createElement("div");
    div.className = "server-block";
    div.innerHTML = `
        <label>Server URL</label>
        <input type="text" class="server-url" value="${escapeHtml(url)}" placeholder="https://api.example.com">
        <button class="small-btn" type="button" onclick="this.parentElement.remove(); triggerGenerateIfAllowed();">Remove</button>
    `;
    container.appendChild(div);
}

/* -------------------- Headers -------------------- */

function addHeader(pathBlock, headerData = {}) {
    const headersContainer = pathBlock.querySelector(".headers-container");
    if (!headersContainer) return;

    const div = document.createElement("div");
    div.className = "header-block";

    div.innerHTML = `
        <div class="inline-row">
            <div>
                <label>Header Name</label>
                <input type="text" class="header-name" value="${escapeHtml(headerData.name || "")}" placeholder="X-Request-ID">
            </div>
            <div>
                <label>Type</label>
                <select class="header-type">
                    <option value="string" ${(headerData.type || "") === "string" ? "selected" : ""}>string</option>
                    <option value="integer" ${(headerData.type || "") === "integer" ? "selected" : ""}>integer</option>
                    <option value="number" ${(headerData.type || "") === "number" ? "selected" : ""}>number</option>
                    <option value="boolean" ${(headerData.type || "") === "boolean" ? "selected" : ""}>boolean</option>
                    <option value="object" ${(headerData.type || "") === "object" ? "selected" : ""}>object</option>
                    <option value="array" ${(headerData.type || "") === "array" ? "selected" : ""}>array</option>
                </select>
            </div>
            <div>
                <label>Required</label>
                <select class="header-required">
                    <option value="false" ${headerData.required ? "" : "selected"}>No</option>
                    <option value="true" ${headerData.required ? "selected" : ""}>Yes</option>
                </select>
            </div>
        </div>

        <label>Header Description</label>
        <input type="text" class="header-description" value="${escapeHtml(headerData.description || "")}" placeholder="Header description">

        <label>Header Example</label>
        <input type="text" class="header-example" value="${escapeHtml(headerData.example || "")}" placeholder="abc-123">

        <button class="small-btn" type="button" onclick="this.parentElement.remove(); triggerGenerateIfAllowed();">Remove Header</button>
    `;

    headersContainer.appendChild(div);
}

/* -------------------- Path Builder -------------------- */

function addCollapsibleSubsection(title, contentHtml, open = true) {
    return `
        <div class="section-card">
            <div class="section-header collapsible-header" onclick="toggleSectionBody(this)">
                <span>${title}</span>
                <span class="collapse-icon">${open ? "▼" : "▶"}</span>
            </div>
            <div class="section-body ${open ? "" : "collapsed"}">
                ${contentHtml}
            </div>
        </div>
    `;
}

function methodBadgeClass(method) {
    const m = (method || "get").toLowerCase();
    return `badge-method badge-${m}`;
}

function addPath(pathData = {}) {
    const container = document.getElementById("paths-container");
    if (!container) return;

    const method = (pathData.method || "get").toLowerCase();
    const pathUrl = pathData.url || "/new-path";

    const card = document.createElement("div");
    card.className = "path-card";

    const headersHtml = `
        <div class="headers-container"></div>
        <button type="button" class="success-btn add-header-btn">+ Add Header</button>
    `;

    const requestSchemaHtml = `
        <div class="inline-row">
            <div>
                <label>Schema Mode</label>
                <select class="request-schema-mode">
                    <option value="single" ${(pathData.request_schema_mode || "single") === "single" ? "selected" : ""}>single</option>
                    <option value="oneOf" ${pathData.request_schema_mode === "oneOf" ? "selected" : ""}>oneOf</option>
                    <option value="anyOf" ${pathData.request_schema_mode === "anyOf" ? "selected" : ""}>anyOf</option>
                    <option value="allOf" ${pathData.request_schema_mode === "allOf" ? "selected" : ""}>allOf</option>
                </select>
            </div>
            <div>
                <label>Use Request Example</label>
                <select class="request-example-select">
                    <option value="">Select Request Example</option>
                </select>
            </div>
        </div>

        <div class="inline-row">
            <div>
                <label>Target Variant</label>
                <select class="request-schema-variant-select">
                    <option value="">Select request schema variant</option>
                </select>
            </div>
            <div></div>
        </div>

        <div class="inline-actions">
            <button type="button" class="success-btn build-request-schema-btn">Build Schema From Selected Request Example</button>
            <button type="button" class="success-btn add-request-schema-variant-btn">+ Add Request Schema Variant</button>
        </div>

        <div class="request-schema-variants"></div>
    `;

    const requestExamplesHtml = `
        <div class="request-examples-container"></div>
        <button type="button" class="success-btn add-request-example-btn">+ Add Request Example</button>
    `;

    const responseSchemaHtml = `
        <div class="inline-row">
            <div>
                <label>Schema Mode</label>
                <select class="response-schema-mode">
                    <option value="single" ${(pathData.response_schema_mode || "single") === "single" ? "selected" : ""}>single</option>
                    <option value="oneOf" ${pathData.response_schema_mode === "oneOf" ? "selected" : ""}>oneOf</option>
                    <option value="anyOf" ${pathData.response_schema_mode === "anyOf" ? "selected" : ""}>anyOf</option>
                    <option value="allOf" ${pathData.response_schema_mode === "allOf" ? "selected" : ""}>allOf</option>
                </select>
            </div>
            <div>
                <label>Use Response Example</label>
                <select class="response-example-select">
                    <option value="">Select Response Example</option>
                </select>
            </div>
        </div>

        <div class="inline-row">
            <div>
                <label>Target Variant</label>
                <select class="response-schema-variant-select">
                    <option value="">Select response schema variant</option>
                </select>
            </div>
            <div></div>
        </div>

        <div class="inline-actions">
            <button type="button" class="success-btn build-response-schema-btn">Build Schema From Selected Response Example</button>
            <button type="button" class="success-btn add-response-schema-variant-btn">+ Add Response Schema Variant</button>
        </div>

        <div class="response-schema-variants"></div>
    `;

    const responseExamplesHtml = `
        <div class="response-examples-container"></div>
        <button type="button" class="success-btn add-response-example-btn">+ Add Response Example</button>
    `;

    card.innerHTML = `
        <div class="path-card-header" onclick="togglePathCard(this)">
            <div>
                <span class="${methodBadgeClass(method)}">${method}</span>
                <span class="path-card-title">${escapeHtml(pathUrl)}</span>
            </div>
            <span class="collapse-icon">▼</span>
        </div>

        <div class="path-card-body">
            <div class="inline-row">
                <div>
                    <label>URL</label>
                    <input type="text" class="path-url" value="${escapeHtml(pathData.url || "")}" placeholder="/users">
                </div>
                <div>
                    <label>HTTP Method</label>
                    <select class="path-method">
                        <option value="get" ${method === "get" ? "selected" : ""}>GET</option>
                        <option value="post" ${method === "post" ? "selected" : ""}>POST</option>
                        <option value="put" ${method === "put" ? "selected" : ""}>PUT</option>
                        <option value="delete" ${method === "delete" ? "selected" : ""}>DELETE</option>
                        <option value="patch" ${method === "patch" ? "selected" : ""}>PATCH</option>
                    </select>
                </div>
            </div>

            <label>Summary</label>
            <input type="text" class="path-summary" value="${escapeHtml(pathData.summary || "")}" placeholder="Get users">

            <label>Description</label>
            <textarea class="path-description" placeholder="Describe this endpoint">${escapeHtml(pathData.description || "")}</textarea>

            ${addCollapsibleSubsection("Request Headers", headersHtml, false)}
            ${addCollapsibleSubsection("Request Schemas", requestSchemaHtml, true)}
            ${addCollapsibleSubsection("Request Examples", requestExamplesHtml, false)}
            ${addCollapsibleSubsection("Response Schemas", responseSchemaHtml, true)}
            ${addCollapsibleSubsection("Response Examples", responseExamplesHtml, false)}

            <button class="small-btn" type="button" onclick="this.closest('.path-card').remove(); triggerGenerateIfAllowed();">Remove Path</button>
        </div>
    `;

    container.appendChild(card);

    const body = card.querySelector(".path-card-body");

    body.querySelector(".add-header-btn").addEventListener("click", () => {
        addHeader(body);
        triggerGenerateIfAllowed();
    });

    body.querySelector(".add-request-example-btn").addEventListener("click", () => {
        addExampleBlock(body.querySelector(".request-examples-container"), {}, "Request Example");
        refreshExampleSelectors(body);
        triggerGenerateIfAllowed();
    });

    body.querySelector(".add-response-example-btn").addEventListener("click", () => {
        addExampleBlock(body.querySelector(".response-examples-container"), {}, "Response Example");
        refreshExampleSelectors(body);
        triggerGenerateIfAllowed();
    });

    body.querySelector(".add-request-schema-variant-btn").addEventListener("click", () => {
        addSchemaVariant(body.querySelector(".request-schema-variants"), "request-schema-builder", {}, "Request Variant");
        ensureSchemaVariantExists(body, "request");
        refreshVariantSelectors(body);
        triggerGenerateIfAllowed();
    });

    body.querySelector(".add-response-schema-variant-btn").addEventListener("click", () => {
        addSchemaVariant(body.querySelector(".response-schema-variants"), "response-schema-builder", {}, "Response Variant");
        ensureSchemaVariantExists(body, "response");
        refreshVariantSelectors(body);
        triggerGenerateIfAllowed();
    });

    body.querySelector(".build-request-schema-btn").addEventListener("click", () => {
        buildSchemaFromSelectedExample(body, "request");
    });

    body.querySelector(".build-response-schema-btn").addEventListener("click", () => {
        buildSchemaFromSelectedExample(body, "response");
    });

    body.querySelector(".request-schema-mode").addEventListener("change", () => {
        ensureSchemaVariantExists(body, "request");
        refreshVariantSelectors(body);
        triggerGenerateIfAllowed();
    });

    body.querySelector(".response-schema-mode").addEventListener("change", () => {
        ensureSchemaVariantExists(body, "response");
        refreshVariantSelectors(body);
        triggerGenerateIfAllowed();
    });

    if (Array.isArray(pathData.headers) && pathData.headers.length > 0) {
        pathData.headers.forEach(header => addHeader(body, header));
    }

    const reqVariants = (pathData.request_schema_variants && pathData.request_schema_variants.length)
        ? pathData.request_schema_variants
        : [{ name: "requestVariant1", fields: pathData.request_schema_fields || [] }];

    const resVariants = (pathData.response_schema_variants && pathData.response_schema_variants.length)
        ? pathData.response_schema_variants
        : [{ name: "responseVariant1", fields: pathData.response_schema_fields || [] }];

    reqVariants.forEach(v => addSchemaVariant(body.querySelector(".request-schema-variants"), "request-schema-builder", v, "Request Variant"));
    resVariants.forEach(v => addSchemaVariant(body.querySelector(".response-schema-variants"), "response-schema-builder", v, "Response Variant"));

    (pathData.request_examples || []).forEach(ex => addExampleBlock(body.querySelector(".request-examples-container"), ex, "Request Example"));
    (pathData.response_examples || []).forEach(ex => addExampleBlock(body.querySelector(".response-examples-container"), ex, "Response Example"));

    ensureSchemaVariantExists(body, "request");
    ensureSchemaVariantExists(body, "response");
    refreshExampleSelectors(body);
    refreshVariantSelectors(body);
}

/* -------------------- Collect Form -------------------- */

function collectFormData() {
    const servers = Array.from(document.querySelectorAll(".server-block")).map(block => ({
        url: block.querySelector(".server-url").value
    }));

    const paths = Array.from(document.querySelectorAll(".path-card-body")).map(block => {
        const headers = Array.from(block.querySelectorAll(".header-block")).map(headerBlock => ({
            name: headerBlock.querySelector(".header-name").value,
            description: headerBlock.querySelector(".header-description").value,
            required: headerBlock.querySelector(".header-required").value === "true",
            type: headerBlock.querySelector(".header-type").value,
            example: headerBlock.querySelector(".header-example").value
        }));

        const requestSchemaMode = block.querySelector(".request-schema-mode")?.value || "single";
        const responseSchemaMode = block.querySelector(".response-schema-mode")?.value || "single";

        return {
            url: block.querySelector(".path-url").value,
            method: block.querySelector(".path-method").value,
            summary: block.querySelector(".path-summary").value,
            description: block.querySelector(".path-description").value,
            headers,
            request_schema_mode: requestSchemaMode,
            request_schema_variants: collectSchemaVariants(
                block.querySelector(".request-schema-variants"),
                "request-schema-builder",
                requestSchemaMode
            ),
            request_examples: collectExamples(block.querySelector(".request-examples-container")),
            response_schema_mode: responseSchemaMode,
            response_schema_variants: collectSchemaVariants(
                block.querySelector(".response-schema-variants"),
                "response-schema-builder",
                responseSchemaMode
            ),
            response_examples: collectExamples(block.querySelector(".response-examples-container"))
        };
    });

    return {
        title: document.getElementById("title")?.value || "",
        description: document.getElementById("description")?.value || "",
        version: document.getElementById("version")?.value || "1.0.0",
        servers,
        paths
    };
}

/* -------------------- Generate / Parse -------------------- */

async function generateFromForm() {
    if (suppressAutoGenerate) return;
    if (isUpdatingFromEditor) return;

    isUpdatingFromGui = true;

    try {
        const payload = collectFormData();

        const response = await fetch("/generate_yaml", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        const result = await response.json();
        lastParsedSpec = result.json;
        window.lastGeneratedYaml = result.yaml;
        window.lastGeneratedJson = result.json;

        if (editorMode === "yaml") {
            setEditorText(result.yaml);
        } else {
            setEditorText(JSON.stringify(result.json, null, 2));
        }

        initSwaggerUIWithErrorFallback(result.json);
        updatePathCardHeaders();
    } catch (e) {
        console.error(e);
    } finally {
        isUpdatingFromGui = false;
    }
}

async function updatePreviewFromYaml() {
    if (isUpdatingFromGui) return;

    isUpdatingFromEditor = true;

    try {
        const text = getEditorText();
        let parsed;

        if (editorMode === "json") {
            parsed = JSON.parse(text);
        } else {
            parsed = jsyaml.load(text);
        }

        lastParsedSpec = parsed;
        window.lastGeneratedJson = parsed;
        window.lastGeneratedYaml = specToYaml(parsed);

        initSwaggerUIWithErrorFallback(parsed);

        suppressAutoGenerate = true;
        populateFormFromSpec(parsed);
        suppressAutoGenerate = false;

        updatePathCardHeaders();
    } catch (e) {
        console.error(e);
    } finally {
        isUpdatingFromEditor = false;
    }
}

/* -------------------- Reverse Sync -------------------- */

function schemaObjectToVariants(schemaObj, prefix) {
    if (!schemaObj) {
        return {
            mode: "single",
            variants: [{ name: `${prefix}Variant1`, fields: [] }]
        };
    }

    if (schemaObj.oneOf) {
        return {
            mode: "oneOf",
            variants: schemaObj.oneOf.map((s, i) => ({
                name: `${prefix}Variant${i + 1}`,
                fields: openApiSchemaToVisualFields(s)
            }))
        };
    }

    if (schemaObj.anyOf) {
        return {
            mode: "anyOf",
            variants: schemaObj.anyOf.map((s, i) => ({
                name: `${prefix}Variant${i + 1}`,
                fields: openApiSchemaToVisualFields(s)
            }))
        };
    }

    if (schemaObj.allOf) {
        return {
            mode: "allOf",
            variants: schemaObj.allOf.map((s, i) => ({
                name: `${prefix}Variant${i + 1}`,
                fields: openApiSchemaToVisualFields(s)
            }))
        };
    }

    return {
        mode: "single",
        variants: [{
            name: `${prefix}Variant1`,
            fields: openApiSchemaToVisualFields(schemaObj)
        }]
    };
}

function examplesObjectToList(examplesObj, prefix) {
    if (!examplesObj) return [];
    return Object.keys(examplesObj).map((key, i) => ({
        key: key || `${prefix}${i + 1}`,
        summary: examplesObj[key]?.summary || "",
        value: prettyJson(examplesObj[key]?.value)
    }));
}

function updatePathCardHeaders() {
    document.querySelectorAll(".path-card").forEach(card => {
        const method = card.querySelector(".path-method")?.value || "get";
        const path = card.querySelector(".path-url")?.value || "/new-path";
        const badge = card.querySelector(".badge-method");
        if (!badge) return;

        badge.className = methodBadgeClass(method);
        badge.textContent = method;

        const title = card.querySelector(".path-card-title");
        if (title) title.textContent = path;
    });
}

function populateFormFromSpec(spec) {
    const titleEl = document.getElementById("title");
    const descEl = document.getElementById("description");
    const versionEl = document.getElementById("version");

    if (titleEl) titleEl.value = spec?.info?.title || "";
    if (descEl) descEl.value = spec?.info?.description || "";
    if (versionEl) versionEl.value = spec?.info?.version || "";

    const serversContainer = document.getElementById("servers-container");
    if (serversContainer) serversContainer.innerHTML = "";

    const servers = spec?.servers || [];
    if (servers.length > 0) {
        servers.forEach(server => addServer(server.url || ""));
    } else {
        addServer("");
    }

    const pathsContainer = document.getElementById("paths-container");
    if (pathsContainer) pathsContainer.innerHTML = "";

    let pathCount = 0;

    Object.keys(spec?.paths || {}).forEach(pathUrl => {
        const methodsObj = spec.paths[pathUrl] || {};

        Object.keys(methodsObj).forEach(method => {
            const operation = methodsObj[method] || {};

            const requestMedia = operation?.requestBody?.content?.["application/json"] || {};
            const requestSchemaInfo = schemaObjectToVariants(requestMedia.schema || null, "request");
            const requestExamples = examplesObjectToList(requestMedia.examples || null, "requestExample");

            const responses = operation?.responses || {};
            const firstResponseCode = Object.keys(responses)[0];
            let responseSchemaInfo = { mode: "single", variants: [{ name: "responseVariant1", fields: [] }] };
            let responseExamples = [];

            if (firstResponseCode) {
                const responseMedia = responses[firstResponseCode]?.content?.["application/json"] || {};
                responseSchemaInfo = schemaObjectToVariants(responseMedia.schema || null, "response");
                responseExamples = examplesObjectToList(responseMedia.examples || null, "responseExample");
            }

            const headers = (operation.parameters || [])
                .filter(param => param.in === "header")
                .map(param => ({
                    name: param.name || "",
                    description: param.description || "",
                    required: !!param.required,
                    type: param?.schema?.type || "string",
                    example: prettyJson(param.example)
                }));

            addPath({
                url: pathUrl,
                method,
                summary: operation.summary || "",
                description: operation.description || "",
                headers,
                request_schema_mode: requestSchemaInfo.mode,
                request_schema_variants: requestSchemaInfo.variants,
                request_examples: requestExamples,
                response_schema_mode: responseSchemaInfo.mode,
                response_schema_variants: responseSchemaInfo.variants,
                response_examples: responseExamples
            });

            pathCount++;
        });
    });

    if (pathCount === 0) {
        addPath({});
    }
}

/* -------------------- Spec Browser -------------------- */

async function refreshSpecList(query = "") {
    const response = await fetch(`/api/specs?q=${encodeURIComponent(query)}`);
    const specs = await response.json();

    const list = document.getElementById("spec-list");
    if (!list) return;

    list.innerHTML = "";

    if (!specs.length) {
        list.innerHTML = `<div class="empty-specs">No stored specifications found.</div>`;
        return;
    }

    const currentId = document.getElementById("current-spec-id")?.value;

    specs.forEach(spec => {
        const item = document.createElement("div");
        item.className = "spec-item" + (String(currentId) === String(spec.id) ? " active" : "");
        item.innerHTML = `
            <div class="spec-item-title">${escapeHtml(spec.name)}</div>
            <div class="spec-item-meta">#${spec.id}</div>
            <div class="spec-item-meta">Updated: ${escapeHtml(spec.updated_at)}</div>
        `;
        item.addEventListener("click", () => loadSpecById(spec.id));
        list.appendChild(item);
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

    isUpdatingFromGui = true;
    try {
        setEditorText(spec.yaml_text);
    } finally {
        isUpdatingFromGui = false;
    }

    await updatePreviewFromYaml();
    await refreshSpecList(document.getElementById("spec-search")?.value || "");
}

/* -------------------- SQLite CRUD -------------------- */

async function saveAsNewSpec() {
    const name = document.getElementById("spec-name")?.value.trim();
    const yamlText = editorMode === "yaml"
        ? getEditorText()
        : (window.lastGeneratedYaml || specToYaml(lastParsedSpec || {}));

    if (!name) {
        alert("Please enter a spec name.");
        return;
    }

    const response = await fetch("/api/specs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, yaml_text: yamlText })
    });

    const result = await response.json();

    if (result.success) {
        document.getElementById("current-spec-id").value = result.id;
        await refreshSpecList(document.getElementById("spec-search")?.value || "");
        alert("Saved as new spec.");
    } else {
        alert(result.error || "Failed to save.");
    }
}

async function updateCurrentSpec() {
    const specId = document.getElementById("current-spec-id")?.value;
    const name = document.getElementById("spec-name")?.value.trim();
    const yamlText = editorMode === "yaml"
        ? getEditorText()
        : (window.lastGeneratedYaml || specToYaml(lastParsedSpec || {}));

    if (!specId) {
        alert("No loaded spec selected. Use Save As New first.");
        return;
    }

    if (!name) {
        alert("Please enter a spec name.");
        return;
    }

    const response = await fetch(`/api/specs/${specId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, yaml_text: yamlText })
    });

    const result = await response.json();

    if (result.success) {
        await refreshSpecList(document.getElementById("spec-search")?.value || "");
        alert("Spec updated.");
    } else {
        alert(result.error || "Failed to update.");
    }
}

async function deleteCurrentSpec() {
    const specId = document.getElementById("current-spec-id")?.value;
    if (!specId) {
        alert("No loaded spec selected.");
        return;
    }

    if (!confirm("Delete this stored specification?")) return;

    const response = await fetch(`/api/specs/${specId}`, {
        method: "DELETE"
    });

    const result = await response.json();

    if (result.success) {
        document.getElementById("current-spec-id").value = "";
        document.getElementById("spec-name").value = "";
        await refreshSpecList(document.getElementById("spec-search")?.value || "");
        alert("Stored specification deleted.");
    } else {
        alert(result.error || "Failed to delete.");
    }
}

/* -------------------- Events -------------------- */

function setupAutoPreview() {
    document.addEventListener("input", (e) => {
        const target = e.target;

        if (
            target.id === "title" ||
            target.id === "description" ||
            target.id === "version" ||
            target.classList.contains("server-url") ||
            target.classList.contains("path-url") ||
            target.classList.contains("path-summary") ||
            target.classList.contains("path-description") ||
            target.classList.contains("header-name") ||
            target.classList.contains("header-description") ||
            target.classList.contains("header-example") ||
            target.classList.contains("schema-name") ||
            target.classList.contains("schema-variant-name") ||
            target.classList.contains("example-key") ||
            target.classList.contains("example-summary") ||
            target.classList.contains("example-value")
        ) {
            const pathBlock = target.closest(".path-card-body");
            if (pathBlock) {
                refreshExampleSelectors(pathBlock);
                refreshVariantSelectors(pathBlock);
            }
            triggerGenerateIfAllowed();
            updatePathCardHeaders();
        }

        if (target.id === "spec-search") {
            debouncedSpecSearch();
        }
    });

    document.addEventListener("change", (e) => {
        const target = e.target;

        if (
            target.classList.contains("path-method") ||
            target.classList.contains("header-type") ||
            target.classList.contains("header-required") ||
            target.classList.contains("schema-type") ||
            target.classList.contains("schema-array-item-type") ||
            target.classList.contains("schema-required") ||
            target.classList.contains("request-schema-mode") ||
            target.classList.contains("response-schema-mode")
        ) {
            const pathBlock = target.closest(".path-card-body");
            if (pathBlock) {
                ensureSchemaVariantExists(pathBlock, "request");
                ensureSchemaVariantExists(pathBlock, "response");
                refreshVariantSelectors(pathBlock);
            }
            triggerGenerateIfAllowed();
            updatePathCardHeaders();
        }
    });
}

const debouncedYamlSync = debounce(() => {
    updatePreviewFromYaml();
}, 1000);

const debouncedSpecSearch = debounce(() => {
    refreshSpecList(document.getElementById("spec-search")?.value || "");
}, 250);

/* -------------------- Initial Load -------------------- */

window.onload = async function () {
    const savedTheme = localStorage.getItem("neo-swagger-theme") || "dark";
    applyTheme(savedTheme);

    editorMode = "yaml";
    updateEditorModeUi();

    const titleEl = document.getElementById("title");
    const descEl = document.getElementById("description");
    const versionEl = document.getElementById("version");

    if (titleEl) titleEl.value = "";
    if (descEl) descEl.value = "";
    if (versionEl) versionEl.value = "";

    addServer("https://api.example.com");

    addPath({
        url: "/users",
        method: "post",
        summary: "Create user",
        description: "Creates a new user",
        headers: [
            {
                name: "X-Request-ID",
                description: "Tracking ID",
                required: false,
                type: "string",
                example: "abc-123"
            }
        ],
        request_schema_mode: "single",
        request_schema_variants: [
            {
                name: "requestVariant1",
                fields: [
                    { name: "name", type: "string", required: true },
                    { name: "email", type: "string", required: false }
                ]
            }
        ],
        request_examples: [
            {
                key: "basicUser",
                summary: "Basic user",
                value: `{
  "name": "John",
  "email": "john@example.com"
}`
            },
            {
                key: "adminUser",
                summary: "Admin user",
                value: `{
  "name": "Alice",
  "email": "alice@example.com",
  "role": "admin"
}`
            }
        ],
        response_schema_mode: "single",
        response_schema_variants: [
            {
                name: "responseVariant1",
                fields: [
                    { name: "id", type: "integer", required: true },
                    { name: "name", type: "string", required: true }
                ]
            }
        ],
        response_examples: [
            {
                key: "successBasic",
                summary: "Success response",
                value: `{
  "id": 1,
  "name": "John"
}`
            }
        ]
    });

    initMonacoEditor(window.INITIAL_YAML || "");

    const waitForMonaco = setInterval(async () => {
        if (monacoEditor) {
            clearInterval(waitForMonaco);
            await updatePreviewFromYaml();
            setupAutoPreview();
            initResizablePanels();
            updateSplitterVisibility();
            updatePathCardHeaders();
            await refreshSpecList();
        }
    }, 100);
};
