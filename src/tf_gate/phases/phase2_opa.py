"""Phase 2: Policy Validation using OPA.

This module integrates OPA policy evaluation into the validation pipeline.
"""

from pathlib import Path
from typing import Any, Optional, Union

from tf_gate.utils.opa import OPAClient, OPAPolicyError


class PolicyValidationError(Exception):
    """Raised when policy validation fails."""

    pass


class PolicyValidator:
    """Validates Terraform plans against OPA policies."""

    def __init__(
        self,
        policy_dir: Union[str, Path],
        opa_binary: Optional[str] = None,
        strict_mode: bool = True,
    ):
        """Initialize policy validator.

        Args:
            policy_dir: Directory containing .rego policy files.
            opa_binary: Optional path to OPA binary.
            strict_mode: If True, fail on any deny rule. If False, only fail on critical.
        """
        self.policy_dir = Path(policy_dir)
        self.opa_client = OPAClient(binary_path=opa_binary)
        self.strict_mode = strict_mode

    def validate(
        self,
        resource_changes: list[dict[str, Any]],
        blast_radius: Any,
        metadata: dict[str, Any],
        emergency_override: bool = False,
    ) -> dict[str, Any]:
        """Validate plan against all policies.

        Args:
            resource_changes: List of resource change dictionaries.
            blast_radius: BlastRadius object or dict with level info.
            metadata: Plan metadata dictionary.
            emergency_override: Whether emergency override is active.

        Returns:
            Validation results with deny, warn, and info messages.

        Raises:
            PolicyValidationError: If validation fails and strict_mode is enabled.
        """
        # Prepare input data for OPA
        input_data = {
            "resource_changes": resource_changes,
            "blast_radius": {
                "level": (
                    blast_radius.level.value
                    if hasattr(blast_radius, "level")
                    else blast_radius.get("level", "green")
                ),
                "total_resources": (
                    blast_radius.total_resources
                    if hasattr(blast_radius, "total_resources")
                    else blast_radius.get("total_resources", 0)
                ),
                "delete_count": (
                    blast_radius.delete_count
                    if hasattr(blast_radius, "delete_count")
                    else blast_radius.get("delete_count", 0)
                ),
                "replace_count": (
                    blast_radius.replace_count
                    if hasattr(blast_radius, "replace_count")
                    else blast_radius.get("replace_count", 0)
                ),
            },
            "terraform_version": metadata.get("terraform_version", "unknown"),
            "emergency_override": emergency_override,
            "timestamp": metadata.get("timestamp"),
            "git_commit": metadata.get("git_commit"),
        }

        try:
            # Compile policies first to check for syntax errors
            self.opa_client.compile_policies(self.policy_dir)

            # Evaluate policies
            results = self.opa_client.evaluate(
                policy_dir=self.policy_dir,
                input_data=input_data,
                query="data.terraform.analysis",
            )

            # Add validation status
            results["passed"] = len(results.get("deny", [])) == 0
            results["strict_mode"] = self.strict_mode

            return results

        except OPAPolicyError as e:
            raise PolicyValidationError(f"Policy validation failed: {e}") from e

    def should_block(
        self,
        validation_results: dict[str, Any],
        blast_radius_level: str = "green",
    ) -> tuple[bool, list[str]]:
        """Determine if plan should be blocked based on validation results.

        Args:
            validation_results: Results from validate() method.
            blast_radius_level: Current blast radius level.

        Returns:
            Tuple of (should_block, reasons).
        """
        deny_messages = validation_results.get("deny", [])
        strict_mode = validation_results.get("strict_mode", True)

        if not deny_messages:
            return False, []

        # In strict mode, any deny blocks
        if strict_mode:
            return True, deny_messages

        # In non-strict mode, only critical blocks (red blast radius + denies)
        if blast_radius_level == "red":
            return True, deny_messages

        return False, []


def run_phase2_validation(
    policy_dir: Union[str, Path],
    resource_changes: list[dict[str, Any]],
    blast_radius: Any,
    metadata: dict[str, Any],
    strict_mode: bool = True,
    emergency_override: bool = False,
) -> dict[str, Any]:
    """Run Phase 2 policy validation.

    Args:
        policy_dir: Directory containing .rego policy files.
        resource_changes: List of resource change dictionaries.
        blast_radius: BlastRadius object or dict.
        metadata: Plan metadata dictionary.
        strict_mode: Whether to fail on any deny rule.
        emergency_override: Whether emergency override is active.

    Returns:
        Validation results dictionary.
    """
    validator = PolicyValidator(
        policy_dir=policy_dir,
        strict_mode=strict_mode,
    )

    return validator.validate(
        resource_changes=resource_changes,
        blast_radius=blast_radius,
        metadata=metadata,
        emergency_override=emergency_override,
    )
