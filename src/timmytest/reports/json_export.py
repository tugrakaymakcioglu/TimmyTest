"""JSON export formatter for TimmyTest audits."""

from pathlib import Path

from timmytest.detector.models import ProjectAudit


def export_audit_to_json(audit: ProjectAudit, output_path: Path | None = None) -> str:
    """Exports a ProjectAudit to JSON string, and optionally writes it to a file."""
    json_str = audit.model_dump_json(indent=2)
    if output_path:
        output_path.write_text(json_str, encoding="utf-8")
    return json_str
