from __future__ import annotations

import functools
import io
import importlib
import random
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any
from urllib.request import urlopen

import qrcode
from flask import Flask, Response, jsonify, request

ROOT_DIR = Path(__file__).resolve().parent.parent
COMMAND_GENERATOR_REPO_DIR = ROOT_DIR / "CommandGenerator"
COMMAND_GENERATOR_JP_DIR = COMMAND_GENERATOR_REPO_DIR / "CommandGeneratorJP"
CACHE_ROOT_DIR = Path(tempfile.gettempdir()) / "command_generator_web_cache"

COMMAND_GENERATOR_BRANCH = "rcj25_for_opl"
COMMAND_GENERATOR_REPO_ZIP_URL = (
    f"https://codeload.github.com/RoboCupAtHomeJP/CommandGenerator/zip/refs/heads/{COMMAND_GENERATOR_BRANCH}"
)
COMMAND_GENERATOR_JP_ZIP_URLS = [
    "https://codeload.github.com/RoboCupAtHomeJP/CommandGeneratorJP/zip/refs/heads/main",
    "https://codeload.github.com/RoboCupAtHomeJP/CommandGeneratorJP/zip/refs/heads/master",
]


def _required_data_files_exist(repo_dir: Path, jp_dir: Path) -> bool:
    required_paths = [
        repo_dir / "names" / "names.md",
        repo_dir / "maps" / "location_names.md",
        repo_dir / "maps" / "room_names.md",
        repo_dir / "objects" / "object_names.md",
        jp_dir / "gpsr_commands.py",
        jp_dir / "egpsr_commands.py",
    ]
    return all(path.exists() for path in required_paths)


def _extract_zip_bytes(zip_bytes: bytes, output_dir: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / "archive.zip"
    archive_path.write_bytes(zip_bytes)
    with zipfile.ZipFile(archive_path, "r") as archive:
        archive.extractall(output_dir)
    archive_path.unlink(missing_ok=True)


def _first_dir(path: Path) -> Path:
    for child in path.iterdir():
        if child.is_dir():
            return child
    raise RuntimeError(f"No extracted directory found in {path}")


def _download_zip(url: str) -> bytes:
    with urlopen(url, timeout=30) as response:
        return response.read()


def _prepare_fallback_sources() -> tuple[Path, Path]:
    repo_cache = CACHE_ROOT_DIR / "CommandGenerator"
    jp_cache = CACHE_ROOT_DIR / "CommandGeneratorJP"
    prepared_marker = CACHE_ROOT_DIR / ".prepared"

    if prepared_marker.exists():
        repo_dir = repo_cache / "repo"
        jp_dir = jp_cache / "repo"
        if _required_data_files_exist(repo_dir, jp_dir):
            return repo_dir, jp_dir

    repo_zip = _download_zip(COMMAND_GENERATOR_REPO_ZIP_URL)
    _extract_zip_bytes(repo_zip, repo_cache)
    extracted_repo_root = _first_dir(repo_cache)
    repo_dir = repo_cache / "repo"
    if repo_dir.exists():
        shutil.rmtree(repo_dir)
    extracted_repo_root.rename(repo_dir)

    jp_dir = jp_cache / "repo"
    jp_download_error: Exception | None = None
    for jp_url in COMMAND_GENERATOR_JP_ZIP_URLS:
        try:
            jp_zip = _download_zip(jp_url)
            _extract_zip_bytes(jp_zip, jp_cache)
            extracted_jp_root = _first_dir(jp_cache)
            if jp_dir.exists():
                shutil.rmtree(jp_dir)
            extracted_jp_root.rename(jp_dir)
            jp_download_error = None
            break
        except Exception as error:  # pragma: no cover - network dependent branch
            jp_download_error = error

    if jp_download_error is not None:
        raise RuntimeError("Failed to download CommandGeneratorJP fallback source") from jp_download_error

    prepared_marker.write_text("ok", encoding="utf-8")

    if not _required_data_files_exist(repo_dir, jp_dir):
        raise RuntimeError("Fallback sources are incomplete after download")

    return repo_dir, jp_dir


@functools.lru_cache(maxsize=1)
def _resolve_source_dirs() -> tuple[Path, Path]:
    if _required_data_files_exist(COMMAND_GENERATOR_REPO_DIR, COMMAND_GENERATOR_JP_DIR):
        return COMMAND_GENERATOR_REPO_DIR, COMMAND_GENERATOR_JP_DIR
    return _prepare_fallback_sources()


@functools.lru_cache(maxsize=1)
def _load_generator_classes() -> tuple[Any, Any]:
    _, jp_dir = _resolve_source_dirs()

    if str(jp_dir) not in sys.path:
        sys.path.insert(0, str(jp_dir))

    gpsr_module = importlib.import_module("gpsr_commands")
    egpsr_module = importlib.import_module("egpsr_commands")
    return gpsr_module.CommandGenerator, egpsr_module.EgpsrCommandGenerator

app = Flask(__name__, static_folder=str(ROOT_DIR / "public"), static_url_path="")


EMBEDDED_STYLE = """
:root { --bg:#f6f1e8; --surface:#fffdf8; --text:#1f2a37; --muted:#4c5a67; --accent:#006d77; --line:#c7d3db; }
* { box-sizing:border-box; }
body { margin:0; min-height:100vh; font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif; color:var(--text); background:var(--bg); display:grid; place-items:center; padding:20px; }
.app { width:min(820px,100%); border:1px solid var(--line); border-radius:18px; background:var(--surface); padding:18px; }
h1 { margin:0 0 8px; font-size:1.6rem; }
p { margin:0 0 14px; color:var(--muted); }
select, button { width:100%; min-height:44px; border-radius:10px; border:1px solid var(--line); font-size:1rem; }
button { cursor:pointer; }
.primary { border:0; background:var(--accent); color:#fff; font-weight:700; margin-top:10px; }
.row { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; margin-top:10px; }
.result { margin-top:12px; min-height:160px; border:1px solid var(--line); border-radius:10px; background:#f9fcff; padding:12px; white-space:pre-wrap; line-height:1.55; font-family:ui-monospace,Consolas,monospace; }
.status { margin-top:10px; color:var(--muted); font-size:.9rem; }
details { margin-top:10px; border:1px solid var(--line); border-radius:10px; padding:8px 10px; }
label { display:block; margin:.4rem 0; font-size:.9rem; color:var(--muted); }
.qr { margin-top:12px; border:1px solid var(--line); border-radius:10px; background:#fff; padding:10px; display:grid; justify-items:center; gap:8px; }
.qr img { width:min(220px,74vw); aspect-ratio:1/1; border:1px solid var(--line); border-radius:8px; background:#fff; }
.qr a { color:var(--accent); font-weight:600; text-decoration:none; }
"""

EMBEDDED_SCRIPT = """
const modeEl = document.getElementById('mode');
const resultEl = document.getElementById('result');
const statusEl = document.getElementById('status');
const generateBtn = document.getElementById('generateBtn');
const copyBtn = document.getElementById('copyBtn');
const speakBtn = document.getElementById('speakBtn');
const qrBtn = document.getElementById('qrBtn');
const qrSection = document.getElementById('qrSection');
const qrImage = document.getElementById('qrImage');
const qrDownload = document.getElementById('qrDownload');
const voiceSelect = document.getElementById('voiceSelect');
const rateRange = document.getElementById('rateRange');
const rateValue = document.getElementById('rateValue');

const speechSupported = 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window;
let cleanEnglishVoices = [];
const presetVoiceMap = new Map();

const VOICE_PRESETS = [
    { id: 'devis', label: 'devis', keywords: ['devis', 'davis', 'guy', 'daniel', 'arthur'] },
    { id: 'ryan', label: 'ryan', keywords: ['ryan', 'george', 'liam', 'james'] },
    { id: 'andrew', label: 'andrew', keywords: ['andrew', 'christopher', 'mark', 'brian'] },
    { id: 'david', label: 'david', keywords: ['microsoft david', 'david', 'alex'] },
    { id: 'aria', label: 'aria', keywords: ['aria', 'samantha', 'jenny', 'emma'] },
    { id: 'natasha', label: 'natasha', keywords: ['natasha', 'ava', 'olivia', 'victoria'] },
    { id: 'susan', label: 'susan', keywords: ['susan', 'michelle', 'karen', 'allison', 'joanna'] },
    { id: 'zira', label: 'zira', keywords: ['microsoft zira', 'zira', 'serena'] }
];

const BAD_VOICE_NAME_PATTERN = /whisper|novelty|robot|child|kid|silly|bells|boing|trinoids|bad news|hysterical|sing/i;
const STORAGE_KEYS = { rate: 'cg_voice_rate', voice: 'cg_voice_preset' };

const initialRate = Number(localStorage.getItem(STORAGE_KEYS.rate) || '1.0');
rateRange.value = String(Number.isFinite(initialRate) ? initialRate : 1.0);
rateValue.textContent = Number(rateRange.value).toFixed(2);

if (!speechSupported) {
    speakBtn.disabled = true;
    voiceSelect.disabled = true;
    rateRange.disabled = true;
}

function setStatus(text) { statusEl.textContent = text; }

function findPresetVoice(preset, voices, usedVoiceNames) {
    const lowerKeywords = preset.keywords.map((k) => k.toLowerCase());
    const direct = voices.find((v) => {
        const name = v.name.toLowerCase();
        return !usedVoiceNames.has(name) && lowerKeywords.some((k) => name.includes(k));
    });
    if (direct) return direct;
    return voices.find((v) => !usedVoiceNames.has(v.name.toLowerCase())) || null;
}

function loadVoices() {
        if (!speechSupported) {
            return;
        }

        cleanEnglishVoices = speechSynthesis.getVoices().filter((v) => {
            return /^en([-_]|$)/i.test(v.lang) && !BAD_VOICE_NAME_PATTERN.test(v.name);
        });

        presetVoiceMap.clear();
        const usedVoiceNames = new Set();

        VOICE_PRESETS.forEach((preset) => {
            const match = findPresetVoice(preset, cleanEnglishVoices, usedVoiceNames);
            presetVoiceMap.set(preset.id, match);
            if (match) usedVoiceNames.add(match.name.toLowerCase());
        });

    voiceSelect.innerHTML = '';
        const savedPreset = localStorage.getItem(STORAGE_KEYS.voice) || 'aria';
        VOICE_PRESETS.forEach((preset, i) => {
            const op = document.createElement('option');
            op.value = preset.id;
            op.textContent = preset.label;
            if (preset.id === savedPreset || (!savedPreset && i === 0)) op.selected = true;
            voiceSelect.appendChild(op);
    });
}

async function generateCommand() {
    setStatus('Generating...');
    generateBtn.disabled = true;
    try {
        const res = await fetch('/api/generate', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ mode: modeEl.value }) });
        const payload = await res.json();
        if (!res.ok) throw new Error(payload.error || 'Generation failed');
        resultEl.textContent = payload.text || 'No result';
        setStatus('Done');
    } catch (e) {
        resultEl.textContent = `Error: ${e.message}`;
        setStatus('Error');
    } finally {
        generateBtn.disabled = false;
    }
}

async function copyResult() {
    const text = resultEl.textContent.trim();
    if (!text || text.includes('ここに生成結果')) return;
    try { await navigator.clipboard.writeText(text); setStatus('Copied'); } catch { setStatus('Copy failed'); }
}

async function showQrCode() {
    const text = resultEl.textContent.trim();
    if (!text || text.includes('ここに生成結果')) { setStatus('No text for QR'); return; }
    qrBtn.disabled = true;
    setStatus('Generating QR...');
    try {
        const res = await fetch(`/api/qrcode?text=${encodeURIComponent(text)}`);
        if (!res.ok) throw new Error('QR generation failed');
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        if (qrImage.dataset.url) URL.revokeObjectURL(qrImage.dataset.url);
        qrImage.src = url;
        qrImage.dataset.url = url;
        qrDownload.href = url;
        qrSection.hidden = false;
        setStatus('QR ready');
    } catch {
        setStatus('QR failed');
    } finally {
        qrBtn.disabled = false;
    }
}

function speakResult() {
    if (!speechSupported) { setStatus('Speech not supported'); return; }
    const text = resultEl.textContent.trim();
    if (!text || text.includes('ここに生成結果')) { setStatus('No text'); return; }
    if (speechSynthesis.speaking) { speechSynthesis.cancel(); speakBtn.textContent = 'Speak'; setStatus('Stopped'); return; }
    const ut = new SpeechSynthesisUtterance(text);
    ut.rate = Number(rateRange.value);
    ut.lang = 'en-US';
        const selectedPresetId = voiceSelect.value;
        const voice = presetVoiceMap.get(selectedPresetId) || cleanEnglishVoices[0] || null;
    if (voice) { ut.voice = voice; ut.lang = voice.lang; }
    ut.onstart = () => { speakBtn.textContent = 'Stop'; setStatus('Speaking...'); };
    ut.onend = () => { speakBtn.textContent = 'Speak'; setStatus('Done speaking'); };
    ut.onerror = () => { speakBtn.textContent = 'Speak'; setStatus('Speech failed'); };
    speechSynthesis.speak(ut);
}

rateRange.addEventListener('input', () => {
    const r = Number(rateRange.value);
    rateValue.textContent = r.toFixed(2);
    localStorage.setItem(STORAGE_KEYS.rate, String(r));
});
voiceSelect.addEventListener('change', () => { localStorage.setItem(STORAGE_KEYS.voice, voiceSelect.value); });
generateBtn.addEventListener('click', generateCommand);
copyBtn.addEventListener('click', copyResult);
speakBtn.addEventListener('click', speakResult);
qrBtn.addEventListener('click', showQrCode);
if (speechSupported) {
    loadVoices();
    speechSynthesis.addEventListener('voiceschanged', loadVoices);
}
"""

EMBEDDED_INDEX_HTML = f"""
<!doctype html>
<html lang=\"ja\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>RCJ Command Generator</title>
<style>{EMBEDDED_STYLE}</style></head><body>
<main class=\"app\">
<h1>Command Generator</h1>
<p>Vercel fallback UI (mobile friendly)</p>
<select id=\"mode\"><option value=\"any\">1: Any command</option><option value=\"people\">2: Without manipulation</option><option value=\"objects\">3: With manipulation</option><option value=\"batch\">4: Batch of three</option><option value=\"egpsr\">5: EGPSR setup</option></select>
<button id=\"generateBtn\" class=\"primary\" type=\"button\">Generate</button>
<div class=\"row\"><button id=\"copyBtn\" type=\"button\">Copy Result</button><button id=\"speakBtn\" type=\"button\">Speak</button><button id=\"qrBtn\" type=\"button\">Show QR</button></div>
<details><summary>Voice Settings</summary><label for=\"voiceSelect\">Voice</label><select id=\"voiceSelect\"></select><label for=\"rateRange\">Speed: <span id=\"rateValue\">1.00</span>x</label><input id=\"rateRange\" type=\"range\" min=\"0.6\" max=\"1.6\" step=\"0.05\" value=\"1.0\"></details>
<div id=\"status\" class=\"status\">Ready</div>
<pre id=\"result\" class=\"result\">ここに生成結果が表示されます。</pre>
<section id=\"qrSection\" class=\"qr\" hidden><img id=\"qrImage\" alt=\"Generated QR code\"><a id=\"qrDownload\" download=\"command_qr.png\">Download QR</a></section>
</main>
<script>{EMBEDDED_SCRIPT}</script></body></html>
"""



def _read_data(file_path: Path) -> str:
    return file_path.read_text(encoding="utf-8")



def _parse_names(data: str) -> list[str]:
    parsed_names = re.findall(r"\|\s*([A-Za-z]+)\s*\|", data, re.DOTALL)
    parsed_names = [name.strip() for name in parsed_names]
    return parsed_names[1:] if parsed_names else []



def _parse_locations(data: str) -> tuple[list[str], list[str]]:
    parsed_locations = re.findall(r"\|\s*([0-9]+)\s*\|\s*([A-Za-z,\s, \(,\)]+)\|", data, re.DOTALL)
    parsed_locations = [location.strip() for (_, location) in parsed_locations]

    parsed_placement_locations = [location for location in parsed_locations if location.endswith("(p)")]
    parsed_locations = [location.replace("(p)", "").strip() for location in parsed_locations]
    parsed_placement_locations = [location.replace("(p)", "").strip() for location in parsed_placement_locations]

    return parsed_locations, parsed_placement_locations



def _parse_rooms(data: str) -> list[str]:
    parsed_rooms = re.findall(r"\|\s*(\w+ \w*)\s*\|", data, re.DOTALL)
    parsed_rooms = [room.strip() for room in parsed_rooms]
    return parsed_rooms[1:] if parsed_rooms else []



def _parse_objects(data: str) -> tuple[list[str], list[str], list[str]]:
    parsed_objects = re.findall(r"\|\s*(\w+)\s*\|", data, re.DOTALL)
    parsed_objects = [obj for obj in parsed_objects if obj != "Objectname"]
    parsed_objects = [obj.replace("_", " ").strip() for obj in parsed_objects]

    parsed_categories = re.findall(r"# Class \s*([\w,\s, \(,\)]+)\s*", data, re.DOTALL)
    parsed_categories = [category.strip().replace("(", "").replace(")", "").split() for category in parsed_categories]

    plural = [category[0].replace("_", " ") for category in parsed_categories]
    singular = [category[1].replace("_", " ") for category in parsed_categories]

    return parsed_objects, plural, singular



def _capitalize_first(text: str) -> str:
    text = text.strip()
    if not text:
        return text
    return text[0].upper() + text[1:]


def _safe_generate_command(generator: Any, category: str) -> str:
    for _ in range(20):
        command = _capitalize_first(generator.generate_command_start(cmd_category=category))
        if command and command != "WARNING":
            return command
    raise RuntimeError("Failed to generate a valid command after multiple retries")


@functools.lru_cache(maxsize=1)
def _build_generators() -> tuple[Any, Any]:
    repo_dir, _ = _resolve_source_dirs()
    CommandGenerator, EgpsrCommandGenerator = _load_generator_classes()

    names = _parse_names(_read_data(repo_dir / "names" / "names.md"))
    locations, placement_locations = _parse_locations(_read_data(repo_dir / "maps" / "location_names.md"))
    rooms = _parse_rooms(_read_data(repo_dir / "maps" / "room_names.md"))
    objects, categories_plural, categories_singular = _parse_objects(
        _read_data(repo_dir / "objects" / "object_names.md")
    )

    generator = CommandGenerator(
        names,
        locations,
        placement_locations,
        rooms,
        objects,
        categories_plural,
        categories_singular,
    )
    egpsr_generator = EgpsrCommandGenerator(generator)
    return generator, egpsr_generator



def _generate(mode: str) -> dict[str, object]:
    generator, egpsr_generator = _build_generators()

    if mode == "any":
        command = _safe_generate_command(generator, "")
        return {"mode": mode, "commands": [command], "text": command}

    if mode == "people":
        command = _safe_generate_command(generator, "people")
        return {"mode": mode, "commands": [command], "text": command}

    if mode == "objects":
        command = _safe_generate_command(generator, "objects")
        return {"mode": mode, "commands": [command], "text": command}

    if mode == "batch":
        commands = [
            _safe_generate_command(generator, "people"),
            _safe_generate_command(generator, "objects"),
            _safe_generate_command(generator, ""),
        ]
        random.shuffle(commands)
        return {"mode": mode, "commands": commands, "text": "\n".join(commands)}

    if mode == "egpsr":
        setup = egpsr_generator.generate_setup().strip()
        return {"mode": mode, "commands": [setup], "text": setup}

    raise ValueError(f"Unsupported mode: {mode}")


@app.get("/api/health")
def health() -> tuple[dict[str, str], int]:
    try:
        repo_dir, jp_dir = _resolve_source_dirs()
        source = "submodule" if repo_dir == COMMAND_GENERATOR_REPO_DIR else "fallback-download"
        return {"status": "ok", "generator_source": source, "repo_dir": str(repo_dir), "jp_dir": str(jp_dir)}, 200
    except Exception as error:
        return {"status": "degraded", "error": str(error)}, 200


@app.route("/api/generate", methods=["GET", "POST"])
def generate() -> tuple[object, int]:
    mode = "any"

    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        mode = str(payload.get("mode", "any"))
    else:
        mode = request.args.get("mode", "any")

    mode = mode.lower().strip()

    try:
        result = _generate(mode)
        return jsonify(result), 200
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except RuntimeError as error:
        return jsonify({"error": str(error)}), 500
    except Exception as error:
        return jsonify({"error": f"Unexpected generator error: {error}"}), 500


@app.route("/api/qrcode", methods=["GET", "POST"])
def generate_qrcode():
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        text = str(payload.get("text", "")).strip()
    else:
        text = str(request.args.get("text", "")).strip()

    if not text:
        return jsonify({"error": "text is required"}), 400
    if len(text) > 2500:
        return jsonify({"error": "text is too long"}), 400

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(text)
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color="black", back_color="white")

    png_buffer = io.BytesIO()
    qr_image.save(png_buffer, format="PNG")
    png_buffer.seek(0)

    return Response(png_buffer.getvalue(), mimetype="image/png")


@app.get("/")
def root():
    index_file = ROOT_DIR / "public" / "index.html"
    if index_file.exists():
        return app.send_static_file("index.html")
    return Response(EMBEDDED_INDEX_HTML, mimetype="text/html")


@app.get("/<path:asset_path>")
def static_assets(asset_path: str):
    asset_file = ROOT_DIR / "public" / asset_path
    if asset_file.exists() and asset_file.is_file():
        return app.send_static_file(asset_path)
    return Response(EMBEDDED_INDEX_HTML, mimetype="text/html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
