package terraform.analysis

# Deny rules for protected resources
# These resources should not be deleted without explicit override

import future.keywords.if
import future.keywords.in

# List of protected resource types
protected_types = {
    "aws_db_instance",
    "aws_rds_cluster",
    "aws_kms_key",
    "aws_s3_bucket",
    "aws_dynamodb_table",
    "aws_elasticache_cluster",
    "aws_redshift_cluster",
    "aws_mq_broker",
}

# Deny deletion of protected resources
deny[msg] if {
    resource := input.resource_changes[_]
    resource.type in protected_types
    resource.change.actions[_] in ["delete", "replace"]
    not input.emergency_override
    
    msg := sprintf(
        "CRITICAL: Protected resource %s of type %s is scheduled for %s. Use --break-glass if this is an emergency.",
        [resource.address, resource.type, resource.change.actions[_]]
    )
}

# Deny deletion of resources with "production" in the name
deny[msg] if {
    resource := input.resource_changes[_]
    contains(resource.address, "production")
    resource.change.actions[_] == "delete"
    not input.emergency_override
    
    msg := sprintf(
        "CRITICAL: Resource %s with 'production' in name is scheduled for deletion",
        [resource.address]
    )
}

# Warn on replacement of stateful resources
warn[msg] if {
    resource := input.resource_changes[_]
    resource.type in protected_types
    resource.change.actions[_] == "replace"
    not input.emergency_override
    
    msg := sprintf(
        "WARNING: Protected resource %s of type %s is scheduled for replacement. This will cause downtime.",
        [resource.address, resource.type]
    )
}
