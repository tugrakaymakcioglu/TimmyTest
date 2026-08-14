"""Data-driven ecosystem detection engine.

Loads the declarative ``ecosystems.yaml`` registry and resolves a project into
raw ``(ecosystem_id, framework_id, command, config_files)`` strings. Enum
conversion happens in ``timmytest.detector.ecosystem`` to avoid a circular
import between this package and ``timmytest.detector``.
"""

from __future__ import annotations

import copy
import functools
import json
from pathlib import Path
from typing import Any

import yaml

_REGISTRY_PATH = Path(__file__).parent / "ecosystems.yaml"
_LEARNED_PATH = Path(__file__).parent / "learned.yaml"

# List fields that the learned overlay is allowed to extend. Everything else -
# most importantly ``command`` - stays hand-curated: a mined rule that widens
# detection is a small mistake, a mined rule that rewrites the command a user's
# test suite runs under is a large one.
_MERGEABLE_ECO_LISTS = ("extensions", "config_files", "test_dirs", "requires_extensions")
_MERGEABLE_FW_LISTS = ("config_files", "dependency_in", "script_contains", "test_patterns")


def _extend_unique(base: list[Any], extra: list[Any]) -> list[Any]:
    """Append items of ``extra`` that are not already in ``base``, keeping order."""
    merged = list(base)
    for item in extra:
        if item not in merged:
            merged.append(item)
    return merged


def _merge_framework(base_fw: dict[str, Any], learned_fw: dict[str, Any]) -> None:
    for field in _MERGEABLE_FW_LISTS:
        extra = learned_fw.get(field)
        if isinstance(extra, list) and extra:
            base_fw[field] = _extend_unique(base_fw.get(field, []), extra)


def _merge_ecosystem(base_eco: dict[str, Any], learned_eco: dict[str, Any]) -> None:
    for field in _MERGEABLE_ECO_LISTS:
        extra = learned_eco.get(field)
        if isinstance(extra, list) and extra:
            base_eco[field] = _extend_unique(base_eco.get(field, []), extra)

    learned_fws = learned_eco.get("frameworks")
    if not isinstance(learned_fws, list):
        return
    base_fws = base_eco.setdefault("frameworks", [])
    for learned_fw in learned_fws:
        if not isinstance(learned_fw, dict) or "id" not in learned_fw:
            continue
        existing = next((f for f in base_fws if f.get("id") == learned_fw["id"]), None)
        if existing is not None:
            _merge_framework(existing, learned_fw)
        elif learned_fw.get("command"):
            # A genuinely new framework needs its command; it is appended last so
            # it can never win over a curated framework by ordering alone.
            new_fw = dict(learned_fw)
            new_fw.pop("default", None)
            base_fws.append(new_fw)


def merge_learned(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Fold a learned overlay into the curated registry (pure, returns a new dict).

    Known ecosystems get their list fields widened; unknown ones are appended to
    the end of the list. Since ``detect_from_registry`` takes the first match,
    appending means a mined ecosystem can only ever catch projects the curated
    registry did not already claim.
    """
    learned_ecos = overlay.get("ecosystems")
    if not isinstance(learned_ecos, list):
        return base

    merged = copy.deepcopy(base)
    by_id = {eco["id"]: eco for eco in merged["ecosystems"] if isinstance(eco, dict) and "id" in eco}

    for learned_eco in learned_ecos:
        if not isinstance(learned_eco, dict) or "id" not in learned_eco:
            continue
        existing = by_id.get(learned_eco["id"])
        if existing is not None:
            _merge_ecosystem(existing, learned_eco)
        elif learned_eco.get("config_files"):
            merged["ecosystems"].append(copy.deepcopy(learned_eco))

    merged["learned_generation"] = overlay.get("generation", 0)
    return merged


def _load_learned() -> dict[str, Any] | None:
    """Read the machine-generated overlay, or ``None`` when it is off/absent.

    A malformed overlay is skipped rather than raised on: detection falling back
    to the curated registry is a smaller failure than the tool refusing to start.
    """
    from timmytest import flags

    if not flags.is_enabled("core.registry_learning"):
        return None
    if not _LEARNED_PATH.is_file():
        return None
    try:
        data = yaml.safe_load(_LEARNED_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, yaml.YAMLError):
        return None
    return data if isinstance(data, dict) else None


@functools.lru_cache(maxsize=1)
def load_registry() -> dict[str, Any]:
    """Load and cache the ecosystem registry, plus any learned overlay."""
    data = yaml.safe_load(_REGISTRY_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "ecosystems" not in data:
        raise ValueError("Invalid registry: missing 'ecosystems' list")

    overlay = _load_learned()
    if overlay is not None:
        data = merge_learned(data, overlay)
    return data


def _match_config_files(root: Path, patterns: list[str]) -> list[str]:
    """Return the config files (by name) present under ``root`` for the given globs."""
    found: list[str] = []
    for pattern in patterns:
        # Exact filename or glob.
        if any(ch in pattern for ch in "*?["):
            matches = list(root.glob(pattern))
            if matches:
                found.extend(m.name for m in matches if m.is_file())
        else:
            if (root / pattern).is_file():
                found.append(pattern)
    return found


def _read_package_json(root: Path) -> dict[str, Any]:
    pkg = root / "package.json"
    if not pkg.is_file():
        return {}
    try:
        return json.loads(pkg.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}


def _resolve_package_managers(eco: dict[str, Any], root: Path) -> dict[str, str]:
    """Map placeholder -> value: {runner} (npx/pnpm/yarn/bun) and {pm} (npm/pnpm/yarn/bun)."""
    pm = None
    default_pm = "npm"
    for entry in eco.get("package_managers", []):
        if "when_file" not in entry:
            default_pm = entry["name"]
        elif (root / entry["when_file"]).is_file():
            pm = entry["name"]
            break
    if pm is None:
        pm = default_pm

    runner = "npx" if pm == "npm" else pm
    return {"runner": runner, "pm": pm}


def _framework_matches(fw: dict[str, Any], root: Path, pkg: dict[str, Any]) -> bool:
    # 1. Explicit config files.
    if fw.get("config_files") and _match_config_files(root, fw["config_files"]):
        return True

    # 2. Package dependency presence.
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    if fw.get("dependency_in") and any(d in deps for d in fw["dependency_in"]):
        return True

    # 3. Test script content.
    script = pkg.get("scripts", {}).get("test", "")
    if fw.get("script_contains") and any(s in script for s in fw["script_contains"]):
        return True

    # 4. Config file content signals (e.g. pyproject mentions unittest, not pytest).
    cc = fw.get("config_content")
    if cc:
        for cfg_name in ["pyproject.toml", "setup.cfg", "setup.py", "pytest.ini", "tox.ini"]:
            p = root / cfg_name
            if not p.is_file():
                continue
            content = p.read_text(encoding="utf-8", errors="ignore")
            if cc.get("not_contains") and any(n in content for n in cc["not_contains"]):
                return False
            if cc.get("contains") and any(c in content for c in cc["contains"]):
                return True

    return False


def _pick_framework(eco: dict[str, Any], root: Path, pkg: dict[str, Any]) -> dict[str, Any]:
    frameworks = eco.get("frameworks", [])
    if not frameworks:
        return {}
    for fw in frameworks:
        if fw.get("default"):
            default = fw
            break
    else:
        default = frameworks[0]

    for fw in frameworks:
        if fw.get("default"):
            continue
        if _framework_matches(fw, root, pkg):
            return fw
    return default


def _resolve_command(fw: dict[str, Any], eco: dict[str, Any], root: Path) -> str:
    command = fw.get("command", "")
    for variant in fw.get("command_variants", []):
        if "when_file" in variant and (root / variant["when_file"]).is_file():
            command = variant["command"]
            break

    placeholders = _resolve_package_managers(eco, root)
    for key, value in placeholders.items():
        command = command.replace("{" + key + "}", value)
    return command


def detect_from_registry(root: Path) -> tuple[str, str, str, list[str]]:
    """Detect ecosystem + framework + command + config files from the registry.

    Returns raw string ids (``eco_id``, ``fw_id``) rather than enums so this
    module stays free of a ``timmytest.detector`` import.
    """
    root = root.resolve()
    registry = load_registry()

    for eco in registry["ecosystems"]:
        found = _match_config_files(root, eco.get("config_files", []))
        if not found:
            continue

        # Extension gate: for ecosystems whose config files are ambiguous
        # (e.g. C vs C++ share Makefile/CMakeLists.txt), require at least one
        # source file with a distinguishing extension.
        req_exts = eco.get("requires_extensions")
        if req_exts and not any(list(root.rglob(f"*{ext}")) for ext in req_exts):
            continue

        pkg = _read_package_json(root)
        fw = _pick_framework(eco, root, pkg)
        command = _resolve_command(fw, eco, root) if fw else eco.get("command", "")

        return (
            eco["id"],
            fw["id"] if fw else "unknown",
            command,
            found,
        )

    # Fallback: no config file matched — sniff by source file extensions.
    py_files = list(root.glob("**/*.py"))
    if py_files:
        return "python", "pytest", "pytest -ra", []

    js_files = list(root.glob("**/*.js")) + list(root.glob("**/*.ts"))
    if js_files:
        return "node", "custom", "npm test", []

    return "unknown", "unknown", "", []
