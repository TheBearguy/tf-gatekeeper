"""Phase 3: Context Engine.

This module provides:
- Temporal safety (time-based risk escalation)
- Drift detection via terraform plan -refresh-only
- Provider version checking
"""

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Union


class RiskLevel(Enum):
    """Risk severity levels."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class TemporalContext:
    """Temporal safety context."""

    current_time: datetime
    is_weekend: bool
    is_after_hours: bool
    is_friday_afternoon: bool
    risk_level: RiskLevel

    def __str__(self) -> str:
        """String representation."""
        risk_emoji = {
            RiskLevel.LOW: "🟢",
            RiskLevel.MEDIUM: "🟡",
            RiskLevel.HIGH: "🔴",
            RiskLevel.CRITICAL: "🔥",
        }
        emoji = risk_emoji.get(self.risk_level, "⚪")
        return (
            f"{emoji} Temporal Risk: {self.risk_level.name}\n"
            f"   Weekend: {self.is_weekend}, After Hours: {self.is_after_hours}, "
            f"Friday Afternoon: {self.is_friday_afternoon}"
        )


@dataclass
class DriftResult:
    """Drift detection result."""

    has_drift: bool
    drifted_resources: list[dict[str, Any]]
    conflict_resources: list[dict[str, Any]]

    def __str__(self) -> str:
        """String representation."""
        if self.has_drift:
            return (
                f"🔄 Drift Detected: {len(self.drifted_resources)} resources\n"
                f"   Conflicts: {len(self.conflict_resources)} resources"
            )
        return "✅ No drift detected"


class ContextEngine:
    """Context engine for temporal and drift analysis."""

    def __init__(
        self,
        friday_cutoff_hour: int = 15,
        weekend_blocking: bool = True,
        after_hours_start: int = 18,
        after_hours_end: int = 9,
    ):
        """Initialize context engine.

        Args:
            friday_cutoff_hour: Hour (24h format) after which Friday is risky.
            weekend_blocking: Whether to escalate risk on weekends.
            after_hours_start: Hour when after-hours begins.
            after_hours_end: Hour when after-hours ends.
        """
        self.friday_cutoff_hour = friday_cutoff_hour
        self.weekend_blocking = weekend_blocking
        self.after_hours_start = after_hours_start
        self.after_hours_end = after_hours_end

    def analyze_temporal_context(
        self,
        base_risk: RiskLevel = RiskLevel.LOW,
    ) -> TemporalContext:
        """Analyze temporal context and calculate risk level.

        Args:
            base_risk: Starting risk level before temporal adjustments.

        Returns:
            TemporalContext with risk assessment.
        """
        now = datetime.now()

        # Determine time factors
        is_weekend = now.weekday() >= 5  # Saturday=5, Sunday=6
        is_friday_afternoon = now.weekday() == 4 and now.hour >= self.friday_cutoff_hour
        is_after_hours = now.hour >= self.after_hours_start or now.hour < self.after_hours_end

        # Calculate risk escalation
        risk_value = base_risk.value

        if self.weekend_blocking and is_weekend:
            risk_value += 1

        if is_friday_afternoon:
            risk_value += 1

        if is_after_hours:
            risk_value += 1

        # Cap at CRITICAL
        risk_value = min(risk_value, 4)

        return TemporalContext(
            current_time=now,
            is_weekend=is_weekend,
            is_after_hours=is_after_hours,
            is_friday_afternoon=is_friday_afternoon,
            risk_level=RiskLevel(risk_value),
        )

    def detect_drift(
        self,
        terraform_dir: Union[str, Path],
        plan_resources: list[dict[str, Any]],
    ) -> DriftResult:
        """Detect drift by comparing plan with refreshed state.

        Args:
            terraform_dir: Directory containing Terraform configuration.
            plan_resources: Resources from the current plan.

        Returns:
            DriftResult with drift analysis.
        """
        terraform_dir = Path(terraform_dir)

        try:
            # Run terraform plan -refresh-only
            subprocess.run(
                ["terraform", "plan", "-refresh-only", "-out=drift.tfplan", "-no-color"],
                cwd=terraform_dir,
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )

            # Convert drift plan to JSON
            show_result = subprocess.run(
                ["terraform", "show", "-json", "drift.tfplan"],
                cwd=terraform_dir,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if show_result.returncode != 0:
                # If no drift plan exists or command fails, assume no drift
                return DriftResult(
                    has_drift=False,
                    drifted_resources=[],
                    conflict_resources=[],
                )

            drift_plan = json.loads(show_result.stdout)
            drift_changes = drift_plan.get("resource_changes", [])

            # Find resources with drift (changes detected by refresh-only)
            drifted_resources = []
            for resource in drift_changes:
                actions = resource.get("change", {}).get("actions", [])
                if "update" in actions or "no-op" in actions:
                    # Check if there's a difference between before and after
                    before = resource.get("change", {}).get("before", {})
                    after = resource.get("change", {}).get("after", {})
                    if before != after:
                        drifted_resources.append(resource)

            # Check for conflicts: resources that are both drifted and being modified
            plan_addresses = {r.get("address") for r in plan_resources}
            conflict_resources = [
                r for r in drifted_resources if r.get("address") in plan_addresses
            ]

            return DriftResult(
                has_drift=len(drifted_resources) > 0,
                drifted_resources=drifted_resources,
                conflict_resources=conflict_resources,
            )

        except subprocess.TimeoutExpired:
            # If drift detection times out, continue without drift info
            return DriftResult(
                has_drift=False,
                drifted_resources=[],
                conflict_resources=[],
            )
        except (subprocess.SubprocessError, json.JSONDecodeError):
            # If drift detection fails, continue without drift info
            return DriftResult(
                has_drift=False,
                drifted_resources=[],
                conflict_resources=[],
            )

    def check_version_lock(
        self,
        current_version: str,
        last_applied_version: Optional[str] = None,
    ) -> dict[str, Any]:
        """Check for Terraform version drift.

        Args:
            current_version: Current Terraform version from plan.
            last_applied_version: Version last used to apply (from state).

        Returns:
            Dictionary with version check results.
        """
        result = {
            "current_version": current_version,
            "last_applied_version": last_applied_version,
            "version_drift": False,
            "warning": None,
        }

        if last_applied_version and current_version != last_applied_version:
            result["version_drift"] = True
            result["warning"] = (
                f"Terraform version drift: Plan uses {current_version}, "
                f"but state was last touched by {last_applied_version}"
            )

        return result


def run_phase3_context_analysis(
    terraform_dir: Union[str, Path],
    plan_resources: list[dict[str, Any]],
    terraform_version: str,
    base_risk: RiskLevel = RiskLevel.LOW,
    friday_cutoff_hour: int = 15,
    weekend_blocking: bool = True,
    last_applied_version: Optional[str] = None,
) -> dict[str, Any]:
    """Run Phase 3 context analysis.

    Args:
        terraform_dir: Directory containing Terraform configuration.
        plan_resources: Resources from the current plan.
        terraform_version: Current Terraform version.
        base_risk: Starting risk level.
        friday_cutoff_hour: Hour after which Friday is risky.
        weekend_blocking: Whether to escalate on weekends.
        last_applied_version: Last Terraform version used to apply.

    Returns:
        Dictionary with temporal context, drift result, and version check.
    """
    engine = ContextEngine(
        friday_cutoff_hour=friday_cutoff_hour,
        weekend_blocking=weekend_blocking,
    )

    temporal = engine.analyze_temporal_context(base_risk)
    drift = engine.detect_drift(terraform_dir, plan_resources)
    version_check = engine.check_version_lock(terraform_version, last_applied_version)

    return {
        "temporal_context": temporal,
        "drift_result": drift,
        "version_check": version_check,
        "risk_escalation": temporal.risk_level.value > base_risk.value,
    }
