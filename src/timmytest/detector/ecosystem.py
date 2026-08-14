"""Ecosystem and test runner detection engine with modern package manager support."""

import json
from pathlib import Path

from timmytest.detector.models import Ecosystem, TestFramework


def detect_ecosystem(root_path: Path) -> tuple[Ecosystem, TestFramework, str, list[str]]:
    """
    Detects the primary ecosystem, test framework, recommended test command,
    and detected configuration files for a given directory.

    Returns:
        (Ecosystem, TestFramework, test_command, config_files)
    """
    root = root_path.resolve()
    configs_found: list[str] = []

    # 1. Check Python & modern toolchains (uv, poetry, pdm, pipenv)
    pyproject = root / "pyproject.toml"
    uv_lock = root / "uv.lock"
    poetry_lock = root / "poetry.lock"
    pdm_lock = root / "pdm.lock"
    pipfile = root / "Pipfile"
    setup_py = root / "setup.py"
    setup_cfg = root / "setup.cfg"
    reqs_txt = root / "requirements.txt"
    pytest_ini = root / "pytest.ini"
    tox_ini = root / "tox.ini"

    python_configs = [
        p
        for p in [
            pyproject,
            uv_lock,
            poetry_lock,
            pdm_lock,
            pipfile,
            setup_py,
            setup_cfg,
            reqs_txt,
            pytest_ini,
            tox_ini,
        ]
        if p.exists()
    ]
    if python_configs:
        configs_found.extend([p.name for p in python_configs])
        framework = TestFramework.PYTEST
        cmd = "pytest -ra"

        if uv_lock.exists():
            cmd = "uv run pytest -ra"
        elif poetry_lock.exists():
            cmd = "poetry run pytest -ra"
        elif pdm_lock.exists():
            cmd = "pdm run pytest -ra"
        elif pipfile.exists():
            cmd = "pipenv run pytest -ra"

        # Check if pyproject or requirements specifically mentions unittest or pytest
        if pyproject.exists():
            try:
                content = pyproject.read_text(encoding="utf-8", errors="ignore")
                if "unittest" in content and "pytest" not in content:
                    framework = TestFramework.UNITTEST
                    cmd = "python -m unittest discover -s tests"
            except Exception:
                pass

        return Ecosystem.PYTHON, framework, cmd, configs_found

    # 2. Check Node / TypeScript / JavaScript (pnpm, yarn, bun, deno, npm)
    pkg_json_path = root / "package.json"
    deno_json = root / "deno.json"
    deno_jsonc = root / "deno.jsonc"

    if deno_json.exists() or deno_jsonc.exists():
        cfg_name = "deno.json" if deno_json.exists() else "deno.jsonc"
        configs_found.append(cfg_name)
        return Ecosystem.NODE, TestFramework.CUSTOM, "deno test", configs_found

    if pkg_json_path.exists():
        configs_found.append("package.json")
        for extra in [
            "tsconfig.json",
            "vitest.config.ts",
            "vitest.config.js",
            "jest.config.js",
            "jest.config.ts",
            "pnpm-lock.yaml",
            "yarn.lock",
            "bun.lockb",
            "bun.lock",
        ]:
            if (root / extra).exists():
                configs_found.append(extra)

        # Detect package runner
        pkg_runner = "npm test"
        if (root / "pnpm-lock.yaml").exists():
            pkg_runner = "pnpm test"
        elif (root / "yarn.lock").exists():
            pkg_runner = "yarn test"
        elif (root / "bun.lockb").exists() or (root / "bun.lock").exists():
            pkg_runner = "bun test"

        framework = TestFramework.JEST
        cmd = pkg_runner

        try:
            pkg_data = json.loads(pkg_json_path.read_text(encoding="utf-8", errors="ignore"))
            scripts = pkg_data.get("scripts", {})
            dev_deps = pkg_data.get("devDependencies", {})
            deps = pkg_data.get("dependencies", {})
            all_deps = {**deps, **dev_deps}

            if "vitest" in all_deps or "vitest" in scripts.get("test", ""):
                framework = TestFramework.VITEST
                cmd = "npx vitest run" if pkg_runner == "npm test" else f"{pkg_runner.split()[0]} vitest run"
            elif "jest" in all_deps or "jest" in scripts.get("test", ""):
                framework = TestFramework.JEST
                cmd = "npx jest" if pkg_runner == "npm test" else f"{pkg_runner.split()[0]} jest"
            elif "mocha" in all_deps:
                framework = TestFramework.MOCHA
                cmd = "npx mocha"
            elif "playwright" in all_deps:
                framework = TestFramework.PLAYWRIGHT
                cmd = "npx playwright test"
            elif "test" in scripts:
                cmd = pkg_runner
        except Exception:
            pass

        return Ecosystem.NODE, framework, cmd, configs_found

    # 3. Check Rust
    cargo_toml = root / "Cargo.toml"
    if cargo_toml.exists():
        configs_found.append("Cargo.toml")
        return Ecosystem.RUST, TestFramework.CARGO, "cargo test", configs_found

    # 4. Check Go
    go_mod = root / "go.mod"
    if go_mod.exists() or any(root.glob("*.go")):
        if go_mod.exists():
            configs_found.append("go.mod")
        return Ecosystem.GO, TestFramework.GO_TEST, "go test ./...", configs_found

    # 5. Check Java / Kotlin (Maven / Gradle)
    pom_xml = root / "pom.xml"
    if pom_xml.exists():
        configs_found.append("pom.xml")
        return Ecosystem.JAVA, TestFramework.MAVEN, "mvn test", configs_found

    build_gradle = root / "build.gradle"
    build_gradle_kts = root / "build.gradle.kts"
    if build_gradle.exists() or build_gradle_kts.exists():
        if build_gradle.exists():
            configs_found.append("build.gradle")
        if build_gradle_kts.exists():
            configs_found.append("build.gradle.kts")
        cmd = "./gradlew test" if (root / "gradlew").exists() else "gradle test"
        return Ecosystem.JAVA, TestFramework.GRADLE, cmd, configs_found

    # 6. Check C# / .NET
    if any(root.glob("*.csproj")) or any(root.glob("*.sln")):
        configs_found.extend([p.name for p in root.glob("*.csproj")])
        configs_found.extend([p.name for p in root.glob("*.sln")])
        return Ecosystem.DOTNET, TestFramework.DOTNET_TEST, "dotnet test", configs_found

    # 7. Check PHP
    composer_json = root / "composer.json"
    if composer_json.exists():
        configs_found.append("composer.json")
        return Ecosystem.PHP, TestFramework.PHPUNIT, "vendor/bin/phpunit", configs_found

    # 8. Check Ruby
    gemfile = root / "Gemfile"
    if gemfile.exists():
        configs_found.append("Gemfile")
        return Ecosystem.RUBY, TestFramework.RSPEC, "bundle exec rspec", configs_found

    # 9. Fallback search for source files
    py_files = list(root.glob("**/*.py"))
    if py_files:
        return Ecosystem.PYTHON, TestFramework.PYTEST, "pytest -ra", []

    js_files = list(root.glob("**/*.js")) + list(root.glob("**/*.ts"))
    if js_files:
        return Ecosystem.NODE, TestFramework.CUSTOM, "npm test", []

    return Ecosystem.UNKNOWN, TestFramework.UNKNOWN, "", []
