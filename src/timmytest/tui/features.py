"""Sidebar feature registry for the dashboard.

Icons are deliberately limited to glyphs that every common terminal font ships
(the CP437 / geometric-shapes corner of Unicode). Anything more exotic risks
either tofu boxes or a double-width cell, and a double-width cell would shear
the whole sidebar out of alignment.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Feature:
    key: str
    label_key: str
    icon: str


@dataclass(frozen=True)
class FeatureGroup:
    label_key: str
    accent: str
    features: tuple[Feature, ...]


GROUPS: tuple[FeatureGroup, ...] = (
    FeatureGroup(
        "grp.overview",
        "#2f9fa8",
        (
            Feature("overview", "f.overview", "■"),
            Feature("results", "f.results", "●"),
            Feature("gaps", "f.gaps", "○"),
            Feature("failures", "f.failures", "▼"),
            Feature("modules", "f.modules", "≡"),
            Feature("coverage", "f.coverage", "▪"),
            Feature("history", "f.history", "↑"),
        ),
    ),
    FeatureGroup(
        "grp.prompt",
        "#e0a72c",
        (
            Feature("prompt_preview", "f.prompt_preview", "►"),
            Feature("prompt_copy", "f.prompt_copy", "▪"),
            Feature("prompt_export", "f.prompt_export", "↓"),
            Feature("prompt_tokens", "f.prompt_tokens", "∑"),
            Feature("prompt_style", "f.prompt_style", "♦"),
        ),
    ),
    FeatureGroup(
        "grp.discord",
        "#7b86f4",
        (
            Feature("discord_webhook", "f.discord_webhook", "●"),
            Feature("discord_send", "f.discord_send", "→"),
            Feature("discord_rules", "f.discord_rules", "▲"),
            Feature("discord_preview", "f.discord_preview", "≡"),
            Feature("discord_status", "f.discord_status", "○"),
        ),
    ),
    FeatureGroup(
        "grp.agents",
        "#c43e2b",
        (
            Feature("agents_claude", "f.agents_claude", "♦"),
            Feature("agents_cursor", "f.agents_cursor", "♦"),
            Feature("agents_copilot", "f.agents_copilot", "♦"),
            Feature("agents_universal", "f.agents_universal", "♦"),
            Feature("agents_mcp", "f.agents_mcp", "■"),
            Feature("agents_ci", "f.agents_ci", "■"),
        ),
    ),
    FeatureGroup(
        "grp.tools",
        "#3fb950",
        (
            Feature("tools_scaffold", "f.tools_scaffold", "▪"),
            Feature("tools_config", "f.tools_config", "●"),
            Feature("tools_report", "f.tools_report", "↓"),
            Feature("tools_json", "f.tools_json", "↓"),
            Feature("tools_log", "f.tools_log", "≡"),
        ),
    ),
    FeatureGroup(
        "grp.settings",
        "#8b949e",
        (
            Feature("settings_language", "f.settings_language", "●"),
            Feature("settings_workspaces", "f.settings_workspaces", "■"),
            Feature("settings_about", "f.settings_about", "○"),
        ),
    ),
)

ALL_FEATURES: tuple[Feature, ...] = tuple(f for group in GROUPS for f in group.features)
FEATURE_KEYS: tuple[str, ...] = tuple(f.key for f in ALL_FEATURES)

#: Switch key namespace: the sidebar feature ``gaps`` is switched via ``tui.gaps``.
FLAG_PREFIX = "tui."


def flag_key(feature_key: str) -> str:
    return FLAG_PREFIX + feature_key


def accent_for(feature_key: str) -> str:
    for group in GROUPS:
        if any(f.key == feature_key for f in group.features):
            return group.accent
    return "#8b949e"


def enabled_groups() -> tuple[FeatureGroup, ...]:
    """``GROUPS`` minus everything switched off in the TimmyTestDev panel.

    Groups that lose all their features drop out entirely rather than leaving a
    dangling header. If a switch file somehow disables *everything*, the full
    registry comes back - an empty sidebar is a broken app, not a configured one.
    """
    from timmytest import flags

    kept: list[FeatureGroup] = []
    for group in GROUPS:
        features = tuple(f for f in group.features if flags.is_enabled(flag_key(f.key)))
        if features:
            kept.append(FeatureGroup(group.label_key, group.accent, features))
    return tuple(kept) if kept else GROUPS


def enabled_features() -> tuple[Feature, ...]:
    return tuple(f for group in enabled_groups() for f in group.features)


def default_feature_key() -> str:
    """The panel the dashboard opens on - ``overview`` unless it is switched off."""
    features = enabled_features()
    keys = {f.key for f in features}
    return "overview" if "overview" in keys else features[0].key
