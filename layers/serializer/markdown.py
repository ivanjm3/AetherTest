"""
AetherTest Markdown Formatter
Converts TestStrategy objects into human-readable Markdown documents.
"""

from __future__ import annotations
from .models import TestStrategy, Priority


def to_markdown(strategy: TestStrategy) -> str:
    """
    Format a TestStrategy as a human-readable Markdown document.

    Args:
        strategy: TestStrategy instance to format.

    Returns:
        Markdown string suitable for display or storage.
    """
    lines = []

    lines.append(f"# Test Strategy: {strategy.strategy_id}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Field | Value |")
    lines.append(f"|---|---|")
    lines.append(f"| Tenant | `{strategy.tenant_id}` |")
    lines.append(f"| AUT ID | `{strategy.aut_id}` |")
    lines.append(f"| AUT Version | `{strategy.aut_version}` |")
    lines.append(f"| Strategy Version | `{strategy.version}` |")
    lines.append(f"| Environment | `{strategy.execution_environment}` |")
    lines.append(f"| Created At | `{strategy.created_at}` |")
    lines.append(f"| Triggered By | `{strategy.triggering_event}` |")
    lines.append(f"| Estimated Duration | `{strategy.estimated_duration_seconds}s` |")
    lines.append(f"| S3 Key | `{strategy.s3_key}` |")
    lines.append("")

    # Group by priority
    high = [c for c in strategy.coverage if c.priority == Priority.HIGH]
    medium = [c for c in strategy.coverage if c.priority == Priority.MEDIUM]
    low = [c for c in strategy.coverage if c.priority == Priority.LOW]

    lines.append("## Coverage Plan")
    lines.append("")

    for label, group in [("🔴 High Priority", high), ("🟡 Medium Priority", medium), ("🟢 Low Priority", low)]:
        if not group:
            continue
        lines.append(f"### {label}")
        lines.append("")
        lines.append("| Component ID | Risk Score | Agents Assigned | Coverage Target |")
        lines.append("|---|---|---|---|")
        for c in sorted(group, key=lambda x: x.risk_score, reverse=True):
            agents = ", ".join(c.assigned_agent_types)
            lines.append(
                f"| `{c.component_id}` | {c.risk_score:.1f} | {agents} | {c.coverage_target} |"
            )
        lines.append("")

    lines.append("## Statistics")
    lines.append("")
    lines.append(f"- Total components: **{len(strategy.coverage)}**")
    lines.append(f"- High priority: **{len(high)}**")
    lines.append(f"- Medium priority: **{len(medium)}**")
    lines.append(f"- Low priority: **{len(low)}**")

    return "\n".join(lines)
