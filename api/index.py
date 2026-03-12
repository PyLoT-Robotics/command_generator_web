from __future__ import annotations

import functools
import importlib
import random
import re
import sys
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request

ROOT_DIR = Path(__file__).resolve().parent.parent
COMMAND_GENERATOR_REPO_DIR = ROOT_DIR / "CommandGenerator"
COMMAND_GENERATOR_JP_DIR = COMMAND_GENERATOR_REPO_DIR / "CommandGeneratorJP"

if str(COMMAND_GENERATOR_JP_DIR) not in sys.path:
    sys.path.insert(0, str(COMMAND_GENERATOR_JP_DIR))

gpsr_module = importlib.import_module("gpsr_commands")
egpsr_module = importlib.import_module("egpsr_commands")
CommandGenerator = gpsr_module.CommandGenerator
EgpsrCommandGenerator = egpsr_module.EgpsrCommandGenerator

app = Flask(__name__, static_folder=str(ROOT_DIR / "public"), static_url_path="")



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
    names = _parse_names(_read_data(COMMAND_GENERATOR_REPO_DIR / "names" / "names.md"))
    locations, placement_locations = _parse_locations(_read_data(COMMAND_GENERATOR_REPO_DIR / "maps" / "location_names.md"))
    rooms = _parse_rooms(_read_data(COMMAND_GENERATOR_REPO_DIR / "maps" / "room_names.md"))
    objects, categories_plural, categories_singular = _parse_objects(
        _read_data(COMMAND_GENERATOR_REPO_DIR / "objects" / "object_names.md")
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
    return {"status": "ok"}, 200


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


@app.get("/")
def root():
    return app.send_static_file("index.html")


@app.get("/<path:asset_path>")
def static_assets(asset_path: str):
    asset_file = ROOT_DIR / "public" / asset_path
    if asset_file.exists() and asset_file.is_file():
        return app.send_static_file(asset_path)
    return app.send_static_file("index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
