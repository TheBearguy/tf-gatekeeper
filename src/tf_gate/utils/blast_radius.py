"""Blast radius calculation utilities."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class BlastRadiusLevel(Enum):
    """Blast radius severity levels."""

    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


@dataclass
class BlastRadius:
    """Blast radius calculation result."""

    level: BlastRadiusLevel
    total_resources: int
    create_count: int
    update_count: int
    delete_count: int
    replace_count: int
    critical_resources: list[str]

    def __str__(self) -> str:
        """String representation of blast radius."""
        emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴"}[self.level.value]
        return (
            f"{emoji} Blast Radius: {self.level.value.upper()}\n"
            f"   Total Resources: {self.total_resources}\n"
            f"   Create: {self.create_count}, Update: {self.update_count}, "
            f"   Delete: {self.delete_count}, Replace: {self.replace_count}"
        )


# Resource types considered critical/stateful
CRITICAL_RESOURCE_TYPES = {
    "aws_db_instance",
    "aws_rds_cluster",
    "aws_kms_key",
    "aws_s3_bucket",
    "aws_dynamodb_table",
    "aws_elasticache_cluster",
    "aws_redshift_cluster",
    "aws_mq_broker",
    "aws_docdb_cluster",
    "aws_neptune_cluster",
    "aws_memorydb_cluster",
    "aws_qldb_ledger",
    "azurerm_sql_database",
    "azurerm_sql_server",
    "azurerm_storage_account",
    "azurerm_key_vault",
    "azurerm_cosmosdb_account",
    "google_sql_database_instance",
    "google_storage_bucket",
    "google_kms_key_ring",
}


def calculate_blast_radius(
    resource_changes: list[dict],
    thresholds: Optional[dict[str, int]] = None,
) -> BlastRadius:
    """Calculate blast radius from resource changes.

    Args:
        resource_changes: List of resource change dictionaries.
        thresholds: Dictionary with green, yellow, red thresholds.
                   Defaults: green=5, yellow=20, red=50

    Returns:
        BlastRadius object with calculated metrics.
    """
    thresholds = thresholds or {"green": 5, "yellow": 20, "red": 50}

    create_count = 0
    update_count = 0
    delete_count = 0
    replace_count = 0
    total_resources = len(resource_changes)
    critical_resources = []

    for resource in resource_changes:
        actions = resource.get("change", {}).get("actions", [])
        resource_type = resource.get("type", "")
        address = resource.get("address", "")

        # Count by action type
        if "create" in actions and "delete" in actions:
            replace_count += 1
        elif "create" in actions:
            create_count += 1
        elif "delete" in actions:
            delete_count += 1
        elif "update" in actions:
            update_count += 1

        # Track critical resources
        if resource_type in CRITICAL_RESOURCE_TYPES:
            if any(a in actions for a in ["delete", "replace"]):
                critical_resources.append(address)

    # Determine level
    destructive_count = delete_count + replace_count

    if total_resources >= thresholds["red"] or destructive_count > 5 or len(critical_resources) > 0:
        level = BlastRadiusLevel.RED
    elif total_resources >= thresholds["yellow"] or destructive_count > 0:
        level = BlastRadiusLevel.YELLOW
    else:
        level = BlastRadiusLevel.GREEN

    return BlastRadius(
        level=level,
        total_resources=total_resources,
        create_count=create_count,
        update_count=update_count,
        delete_count=delete_count,
        replace_count=replace_count,
        critical_resources=critical_resources,
    )


def get_blast_radius_summary(blast_radius: BlastRadius) -> str:
    """Get a human-readable summary of blast radius.

    Args:
        blast_radius: BlastRadius object.

    Returns:
        Summary string.
    """
    return str(blast_radius)
