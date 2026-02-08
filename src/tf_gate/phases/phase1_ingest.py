"""Phase 1: Ingestion & Blast Radius Calculation.

This module provides:
- Streaming JSON parser for large Terraform plan files using ijson
- Resource extraction from plan.json
- Blast radius calculation based on resource changes
"""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Optional, Union

import ijson

from tf_gate.utils.blast_radius import BlastRadius, BlastRadiusLevel


class PlanIngestor:
    """Streaming parser for Terraform plan JSON files."""

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
    }

    def __init__(self, thresholds: Optional[dict[str, int]] = None):
        """Initialize the plan ingestor.

        Args:
            thresholds: Dictionary with green, yellow, red thresholds.
                       Defaults: green=5, yellow=20, red=50
        """
        self.thresholds = thresholds or {"green": 5, "yellow": 20, "red": 50}

    def parse_streaming(self, plan_path: Union[str, Path]) -> Iterator[dict[str, Any]]:
        """Parse plan.json using streaming to handle large files.

        Args:
            plan_path: Path to the Terraform plan JSON file.

        Yields:
            Individual resource change objects.
        """
        plan_path = Path(plan_path)

        with open(plan_path, "rb") as f:
            # Stream resource_changes array items
            for resource in ijson.items(f, "resource_changes.item"):
                yield resource

    def parse_full(self, plan_path: Union[str, Path]) -> dict[str, Any]:
        """Parse entire plan.json into memory (for smaller files).

        Args:
            plan_path: Path to the Terraform plan JSON file.

        Returns:
            Complete plan dictionary.
        """
        plan_path = Path(plan_path)

        with open(plan_path) as f:
            return json.load(f)

    def extract_resource_changes(self, plan_path: Union[str, Path]) -> list[dict[str, Any]]:
        """Extract all resource changes from plan.

        Args:
            plan_path: Path to the Terraform plan JSON file.

        Returns:
            List of resource change dictionaries.
        """
        changes = []
        for resource in self.parse_streaming(plan_path):
            changes.append(resource)
        return changes

    def calculate_blast_radius(self, plan_path: Union[str, Path]) -> BlastRadius:
        """Calculate blast radius from plan file.

        Args:
            plan_path: Path to the Terraform plan JSON file.

        Returns:
            BlastRadius object with calculated metrics.
        """
        create_count = 0
        update_count = 0
        delete_count = 0
        replace_count = 0
        total_resources = 0
        critical_resources = []

        for resource in self.parse_streaming(plan_path):
            total_resources += 1

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
            if resource_type in self.CRITICAL_RESOURCE_TYPES:
                if any(a in actions for a in ["delete", "replace"]):
                    critical_resources.append(address)

        # Determine level
        destructive_count = delete_count + replace_count

        if (
            total_resources >= self.thresholds["red"]
            or destructive_count > 5
            or len(critical_resources) > 0
        ):
            level = BlastRadiusLevel.RED
        elif total_resources >= self.thresholds["yellow"] or destructive_count > 0:
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

    def get_plan_metadata(self, plan_path: Union[str, Path]) -> dict[str, Any]:
        """Extract metadata from plan file.

        Args:
            plan_path: Path to the Terraform plan JSON file.

        Returns:
            Dictionary with terraform_version, format_version, etc.
        """
        plan_path = Path(plan_path)
        metadata = {}

        with open(plan_path, "rb") as f:
            # Extract specific fields using streaming
            parser = ijson.parse(f)
            for prefix, _event, value in parser:
                if prefix == "terraform_version":
                    metadata["terraform_version"] = value
                elif prefix == "format_version":
                    metadata["format_version"] = value
                elif prefix == "timestamp":
                    metadata["timestamp"] = value
                elif prefix == "errored":
                    metadata["errored"] = value

                # Stop after we have the basic metadata
                if len(metadata) >= 4:
                    break

        return metadata


def ingest_plan(
    plan_path: Union[str, Path],
    thresholds: Optional[dict[str, int]] = None,
) -> tuple[list[dict[str, Any]], BlastRadius, dict[str, Any]]:
    """Complete Phase 1: Ingest plan and calculate blast radius.

    Args:
        plan_path: Path to the Terraform plan JSON file.
        thresholds: Optional blast radius thresholds.

    Returns:
        Tuple of (resource_changes, blast_radius, metadata).
    """
    ingestor = PlanIngestor(thresholds)

    # Extract all data
    changes = ingestor.extract_resource_changes(plan_path)
    blast_radius = ingestor.calculate_blast_radius(plan_path)
    metadata = ingestor.get_plan_metadata(plan_path)

    return changes, blast_radius, metadata
