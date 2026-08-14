"""Tests for the data-driven detection registry and newly-added ecosystems."""

import pytest

from timmytest.detector.ecosystem import detect_ecosystem
from timmytest.detector.models import Ecosystem, TestFramework
from timmytest.registry.loader import load_registry


def test_registry_ids_map_to_valid_enums():
    """Every registry ecosystem/framework id must have a matching enum member."""
    registry = load_registry()
    for eco in registry["ecosystems"]:
        assert Ecosystem(eco["id"]) != Ecosystem.UNKNOWN, f"missing Ecosystem enum for {eco['id']}"
        for fw in eco.get("frameworks", []):
            assert (
                TestFramework(fw["id"]) != TestFramework.UNKNOWN
            ), f"missing TestFramework enum for {fw['id']}"


@pytest.mark.parametrize(
    ("config_file", "config_content", "expected_eco", "expected_fw", "expected_cmd"),
    [
        # (config file to create, its content, expected ecosystem, framework, command substring)
        ("Package.swift", "// swift-tools-version:5.7\n", Ecosystem.SWIFT, TestFramework.XCTEST, "swift test"),
        ("pubspec.yaml", "name: demo\n", Ecosystem.DART, TestFramework.DART_TEST, "dart test"),
        ("mix.exs", 'defmodule Demo.MixProject do\nend\n', Ecosystem.ELIXIR, TestFramework.EXUNIT, "mix test"),
        ("stack.yaml", "resolver: lts-21\n", Ecosystem.HASKELL, TestFramework.HSPEC, "stack test"),
        ("build.gradle.kts", "plugins { kotlin(\"jvm\") }\n", Ecosystem.KOTLIN, TestFramework.KOTLIN_TEST, "gradlew test"),
        ("build.sbt", 'scalaVersion := "3.3.0"\n', Ecosystem.SCALA, TestFramework.SCALATEST, "sbt test"),
        ("foo.rockspec", "package = \"demo\"\n", Ecosystem.LUA, TestFramework.BUSTED, "busted"),
        ("Makefile.PL", "use ExtUtils::MakeMaker;\n", Ecosystem.PERL, TestFramework.PROVE, "prove"),
        ("build.zig", 'const std = @import("std");\n', Ecosystem.ZIG, TestFramework.ZIG_TEST, "zig build test"),
        ("shard.yml", "name: demo\n", Ecosystem.CRYSTAL, TestFramework.CRYSTAL_SPEC, "crystal spec"),
        ("project.clj", "(defproject demo \"0.1.0\")\n", Ecosystem.CLOJURE, TestFramework.CLOJURE_TEST, "lein test"),
        # --- vibe-coding agent favorites + completeness ---
        ("foundry.toml", "[profile.default]\nsrc = \"src\"\n", Ecosystem.SOLIDITY, TestFramework.FOUNDRY, "forge test"),
        ("dbt_project.yml", "name: demo\nversion: 1.0.0\n", Ecosystem.SQL, TestFramework.DBT, "dbt test"),
        ("main.tf", 'resource "null_resource" "x" {}\n', Ecosystem.TERRAFORM, TestFramework.TERRAFORM_TEST, "terraform test"),
        ("foo.psd1", "@{\n    RootModule = 'Demo'\n}\n", Ecosystem.POWERSHELL, TestFramework.PESTER, "Invoke-Pester"),
        ("DESCRIPTION", "Package: demo\nTitle: Demo\n", Ecosystem.R, TestFramework.TESTTHAT, "testthat"),
        ("Project.toml", 'name = "Demo"\nuuid = "123e4567"\n', Ecosystem.JULIA, TestFramework.JULIA_TEST, "Pkg.test"),
        ("Jenkinsfile", "pipeline {\n    agent any\n}\n", Ecosystem.GROOVY, TestFramework.SPOCK, "gradlew test"),
        ("rebar.config", "{erl_opts, [debug_info]}.\n", Ecosystem.ERLANG, TestFramework.EUNIT, "rebar3 eunit"),
        ("foo.nimble", 'version = "0.1.0"\n', Ecosystem.NIM, TestFramework.NIM_TEST, "nimble test"),
        ("dune-project", "(lang dune 3.0)\n", Ecosystem.OCAML, TestFramework.DUNE_TEST, "dune runtest"),
        ("elm.json", '{"type": "application"}\n', Ecosystem.ELM, TestFramework.ELM_TEST, "elm-test"),
        ("dub.json", '{"name": "demo"}\n', Ecosystem.D, TestFramework.DUB_TEST, "dub test"),
        ("v.mod", "Module {\n    name: 'demo'\n}\n", Ecosystem.V, TestFramework.V_TEST, "v test ."),
        ("foo.bats", "@test \"addition works\" {}\n", Ecosystem.SHELL, TestFramework.BATS, "bats test"),
    ],
)
def test_detect_new_ecosystems(
    temp_project_dir, config_file, config_content, expected_eco, expected_fw, expected_cmd
):
    (temp_project_dir / config_file).write_text(config_content, encoding="utf-8")
    # Kotlin needs a .kt source file to disambiguate it from Java (they share build.gradle.kts).
    if expected_eco == Ecosystem.KOTLIN:
        (temp_project_dir / "Main.kt").write_text("fun main() {}\n", encoding="utf-8")
    # Solidity needs a .sol source file to disambiguate it from Node (Hardhat has package.json).
    if expected_eco == Ecosystem.SOLIDITY:
        (temp_project_dir / "Contract.sol").write_text("contract C {}\n", encoding="utf-8")
    eco, fw, cmd, configs = detect_ecosystem(temp_project_dir)
    assert eco == expected_eco, f"expected {expected_eco}, got {eco}"
    assert fw == expected_fw, f"expected {expected_fw}, got {fw}"
    assert expected_cmd in cmd


def test_detect_c_vs_cpp_disambiguation(temp_project_dir):
    # C project: Makefile + a .c source file -> C (not C++).
    (temp_project_dir / "Makefile").write_text("all:\n", encoding="utf-8")
    (temp_project_dir / "main.c").write_text("int main(void){return 0;}\n", encoding="utf-8")
    eco, fw, cmd, _ = detect_ecosystem(temp_project_dir)
    assert eco == Ecosystem.C
    assert fw == TestFramework.CTEST

    # C++ project: Makefile + a .cpp source file -> C++.
    (temp_project_dir / "main.c").unlink()
    (temp_project_dir / "main.cpp").write_text("int main(){return 0;}\n", encoding="utf-8")
    eco, fw, cmd, _ = detect_ecosystem(temp_project_dir)
    assert eco == Ecosystem.CPP
    assert fw == TestFramework.GTEST


def test_detect_java_gradle_wrapper_vs_system(temp_project_dir):
    """Gradle projects use ./gradlew only when the wrapper is present."""
    (temp_project_dir / "build.gradle").write_text("plugins { id 'java' }\n", encoding="utf-8")
    (temp_project_dir / "App.java").write_text("class App {}\n", encoding="utf-8")

    eco, fw, cmd, _ = detect_ecosystem(temp_project_dir)
    assert eco == Ecosystem.JAVA
    assert fw == TestFramework.GRADLE
    assert cmd == "gradle test"  # no gradlew wrapper present

    (temp_project_dir / "gradlew").write_text("#!/bin/sh\n", encoding="utf-8")
    _, _, cmd, _ = detect_ecosystem(temp_project_dir)
    assert cmd == "./gradlew test"  # wrapper now present


def test_registry_covers_expected_language_count():
    """A smoke guard that the registry has grown well beyond the original 8 ecosystems."""
    registry = load_registry()
    ids = {eco["id"] for eco in registry["ecosystems"]}
    assert len(ids) >= 34
    for expected in {
        "python", "node", "rust", "go", "java", "swift", "dart", "elixir", "zig", "crystal",
        "solidity", "shell", "sql", "terraform", "powershell", "r", "julia", "groovy",
        "erlang", "nim", "ocaml", "elm", "d", "v",
    }:
        assert expected in ids
