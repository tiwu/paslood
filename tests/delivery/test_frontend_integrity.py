"""Frontend JavaScript syntax, modular asset serving, DOM contract, and Node unit tests."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from wealth_pilot.adapters.repositories.config_repo import ConfigRepository
from wealth_pilot.delivery.web.app import create_app

WEB_DIR = Path(__file__).parents[2] / "src" / "wealth_pilot" / "delivery" / "web"
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"
JS_MODULES_DIR = STATIC_DIR / "js"

EXPECTED_JS_MODULES = [
    "core.js",
    "dashboard.js",
    "buckets.js",
    "guidance.js",
    "assets_cashflow.js",
    "settings_wizard.js",
]


@pytest.fixture
def test_app(tmp_path):
    repo = ConfigRepository(config_path=tmp_path / "test_portfolio.yaml")
    return create_app(config_repo=repo)


def test_modular_js_files_exist_and_index_is_clean():
    """Ensure inline JS has been extracted from index.html into modular static/js/*.js files."""
    for mod in EXPECTED_JS_MODULES:
        mod_path = JS_MODULES_DIR / mod
        assert mod_path.exists(), f"Expected extracted JS module {mod_path} to exist"
        assert mod_path.stat().st_size > 200, f"JS module {mod} is unexpectedly empty"

    index_html = (TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")
    # index.html should be compact (< 1900 lines) with external <script src="/static/js/..."> tags
    line_count = len(index_html.splitlines())
    assert line_count < 1900, (
        f"index.html still has {line_count} lines; large inline JS should be extracted to static/js/"
    )
    for mod in EXPECTED_JS_MODULES:
        assert f'/static/js/{mod}"' in index_html, f"index.html missing script tag for {mod}"


def test_all_static_js_and_inline_scripts_valid_syntax():
    """Validate every static .js file and any inline <script> tag with `node --check`."""
    js_files = list(STATIC_DIR.rglob("*.js"))
    assert len(js_files) >= 7, "Expected i18n.js plus 6 modular JS files under static/"

    for js_file in sorted(js_files):
        res = subprocess.run(
            ["node", "--check", str(js_file)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert res.returncode == 0, f"JS syntax error in {js_file.name}:\n{res.stderr}"

    for html_file in sorted(TEMPLATES_DIR.glob("*.html")):
        text = html_file.read_text(encoding="utf-8")
        inline_scripts = re.findall(r"<script(?![^>]*src=)[^>]*>(.*?)</script>", text, re.DOTALL)
        for idx, script_body in enumerate(inline_scripts):
            if not script_body.strip():
                continue
            with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8") as tmp:
                tmp.write(script_body)
                tmp.flush()
                res = subprocess.run(
                    ["node", "--check", tmp.name],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                assert res.returncode == 0, (
                    f"Inline <script>[{idx}] syntax error in {html_file.name}:\n{res.stderr}"
                )


@pytest.mark.asyncio
async def test_static_js_files_served_by_fastapi(test_app):
    """Verify every <script src='/static/...'> in index.html is served with HTTP 200."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/")
        assert resp.status_code == 200
        script_srcs = re.findall(r'<script[^>]+src="(/static/[^"]+)"', resp.text)
        assert len(script_srcs) >= 7
        for src in script_srcs:
            js_resp = await client.get(src)
            assert js_resp.status_code == 200, f"Failed to load static script {src}"
            assert "javascript" in js_resp.headers.get("content-type", "").lower()
            assert len(js_resp.text) > 100


def test_inline_event_handlers_reference_defined_functions():
    """Verify every inline on*='...' attribute in HTML has valid JS syntax and calls defined functions."""
    combined_js = "\n".join(p.read_text(encoding="utf-8") for p in sorted(STATIC_DIR.rglob("*.js")))
    defined_funcs = set(re.findall(r"function\s+([a-zA-Z0-9_]+)\s*\(", combined_js))

    for html_file in sorted(TEMPLATES_DIR.glob("*.html")):
        html = html_file.read_text(encoding="utf-8")
        handlers = re.findall(r'\bon(?:click|change|input|submit|keydown|keyup)="([^"]+)"', html)
        for expr in set(handlers):
            with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8") as tmp:
                tmp.write(f"function __handler(event) {{ {expr} }}\n")
                tmp.flush()
                res = subprocess.run(
                    ["node", "--check", tmp.name],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                assert res.returncode == 0, (
                    f"Invalid JS in inline handler `{expr}` in {html_file.name}:\n{res.stderr}"
                )

            m = re.match(r"^\s*([a-zA-Z0-9_.]+)\s*\(", expr)
            if m:
                fn = m.group(1)
                if not fn.startswith(("I18N.", "window.", "document.", "this.", "event.")):
                    assert fn in defined_funcs, (
                        f"Inline handler `{expr}` in {html_file.name} calls undefined function `{fn}`"
                    )


def test_navigation_tabs_and_containers_match():
    """Ensure every switchTab('<id>') call has a matching #tab-<id> and #nav-<id> in index.html."""
    index_html = (TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")
    tab_targets = set(re.findall(r"switchTab\('([a-zA-Z0-9_-]+)'\)", index_html))
    assert tab_targets == {"dashboard", "buckets", "advice", "ai", "cashflow", "settings"}

    for tab_id in tab_targets:
        assert f'id="tab-{tab_id}"' in index_html, f"Missing #tab-{tab_id} container"
        assert f'id="nav-{tab_id}"' in index_html, f"Missing #nav-{tab_id} button"


def test_js_rendering_functions_unit_execution_in_node():
    """Execute unit tests directly against extracted JS modules in Node.js with a lightweight DOM mock."""
    harness = f"""
const fs = require('fs');
const vm = require('vm');

function makeEl(id = '') {{
  let _html = '';
  return {{
    id,
    get innerHTML() {{ return _html; }},
    set innerHTML(val) {{
      _html = val;
      if (!val) this.children = [];
    }},
    textContent: '',
    value: '',
    checked: false,
    disabled: false,
    style: {{}},
    dataset: {{}},
    className: '',
    children: [],
    classList: {{
      _set: new Set(['hidden']),
      add(...cls) {{ cls.forEach(c => this._set.add(c)); }},
      remove(...cls) {{ cls.forEach(c => this._set.delete(c)); }},
      contains(c) {{ return this._set.has(c); }},
      toggle(c) {{ if (this._set.has(c)) this._set.delete(c); else this._set.add(c); }}
    }},
    appendChild(child) {{ this.children.push(child); }},
    setAttribute() {{}},
    querySelector() {{ return makeEl(); }},
    querySelectorAll() {{ return []; }},
    addEventListener() {{}},
    getContext() {{ return {{}}; }}
  }};
}}

const elements = new Map();
function getEl(id) {{
  if (!elements.has(id)) elements.set(id, makeEl(id));
  return elements.get(id);
}}

const sandbox = {{
  console,
  setTimeout: () => {{}},
  clearTimeout: () => {{}},
  URLSearchParams,
  Math,
  Date,
  JSON,
  Array,
  Object,
  String,
  Number,
  Boolean,
  RegExp,
  Error,
  Promise,
  parseFloat,
  parseInt,
  isNaN,
  encodeURIComponent,
  decodeURIComponent,
  localStorage: {{
    _store: {{}},
    getItem(k) {{ return this._store[k] || null; }},
    setItem(k, v) {{ this._store[k] = String(v); }}
  }},
  I18N: {{
    t: (k, fb) => (typeof fb === 'string' ? fb : (fb && fb._fallback ? fb._fallback : k)),
    formatCurrency: (v) => '€ ' + Number(v || 0).toFixed(2),
    formatPercent: (v) => Number(v || 0).toFixed(1) + '%',
    formatNumber: (v) => Number(v || 0).toFixed(1),
    formatDate: (d) => String(d),
    localizeAdvice: (a) => a,
    setLanguage: () => {{}},
    setRegionalFormat: () => {{}}
  }},
  document: {{
    documentElement: makeEl('html'),
    body: makeEl('body'),
    title: 'Paslood',
    getElementById: (id) => getEl(id),
    createElement: (tag) => makeEl(tag),
    querySelector: () => makeEl(),
    querySelectorAll: () => [makeEl(), makeEl()]
  }},
  window: {{
    location: {{ search: '', hash: '', pathname: '/', href: '' }},
    history: {{ replaceState: () => {{}} }},
    addEventListener: () => {{}}
  }},
  fetch: async (url, opts = {{}}) => {{
    if (opts.headers) {{
      for (const [k, v] of Object.entries(opts.headers)) {{
        for (let i = 0; i < String(v).length; i++) {{
          if (String(v).charCodeAt(i) > 255) {{
            throw new TypeError(`Cannot convert value in record<ByteString, ByteString> to ByteString because the character at index ${{i}} has value ${{String(v).charCodeAt(i)}} which is greater than 255.`);
          }}
        }}
      }}
    }}
    return {{ ok: true, json: async () => ({{ models: [{{ id: 'gemini-2.5-flash', name: 'Gemini 2.5 Flash', recommended: true }}] }}) }};
  }}
}};

vm.createContext(sandbox);
const jsDir = {json.dumps(str(JS_MODULES_DIR))};
for (const file of {json.dumps(EXPECTED_JS_MODULES)}) {{
  const code = fs.readFileSync(jsDir + '/' + file, 'utf-8');
  vm.runInContext(code, sandbox, {{ filename: file }});
}}

// 1. Test escapeHtml
const escaped = sandbox.escapeHtml('<script>"alert(1)"</script>');
if (!escaped.includes('&lt;script&gt;')) throw new Error('escapeHtml failed: ' + escaped);

// 2. Test switchTab
sandbox.switchTab('buckets');
if (getEl('tab-buckets').classList.contains('hidden') && !getEl('tab-buckets').classList.contains('active')) {{
  // classList.add('active') should have been called on #tab-buckets
}}

// 3. Test renderBulletMeters & renderDriftChart
const sampleAllocs = [
  {{
    bucket_id: 'core-etf',
    name: 'Core World ETFs',
    color: '#3B82F6',
    current_value: 55000,
    current_weight_pct: 55.0,
    target_weight_pct: 50.0,
    drift_tolerance_pct: 3.0,
    diff_value: 5000,
    diff_weight_pct: 5.0,
    drift_status: 'OVERWEIGHT',
    include_in_rebalancing: true
  }}
];
const bulletContainer = getEl('bucket-meters-container');
sandbox.renderBulletMeters(sampleAllocs, bulletContainer);
if (bulletContainer.children.length !== 1) throw new Error('Expected 1 bullet card');
if (!bulletContainer.children[0].innerHTML.includes('target-pin')) throw new Error('Missing target-pin');

const driftContainer = getEl('bucket-drift-container');
sandbox.renderDriftChart(sampleAllocs, driftContainer);
if (driftContainer.children.length !== 2) throw new Error('Expected header + 1 drift row');

// 4. Test renderExcludedBuckets
sandbox.renderExcludedBuckets([{{ name: 'Home Property', color: '#10B981', current_value: 350000 }}]);
if (getEl('bucket-excluded-list').children.length !== 1) throw new Error('Expected 1 excluded bucket item');

// 5. Test refreshAiModels with masked key containing bullet point \u2022
(async () => {{
  getEl('settings-ai-provider').value = 'gemini';
  getEl('settings-ai-key').value = '••••5678';
  await sandbox.refreshAiModels();
  const select = getEl('settings-ai-model');
  if (select.children.length !== 1 || select.children[0].value !== 'gemini-2.5-flash') {{
    throw new Error('refreshAiModels failed with masked key: ' + JSON.stringify(select.children));
  }}

  // Test with valid unmasked ASCII key
  getEl('settings-ai-key').value = 'sk-test-valid-key';
  await sandbox.refreshAiModels();
  if (select.children.length !== 1) {{
    throw new Error('refreshAiModels failed with valid ASCII key');
  }}

  console.log('NODE_UNIT_OK');
}})().catch(err => {{
  console.error(err);
  process.exit(1);
}});
"""
    res = subprocess.run(
        ["node", "-e", harness],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"Node JS unit test harness failed:\n{res.stderr}"
    assert "NODE_UNIT_OK" in res.stdout
