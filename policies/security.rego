package terraform.analysis

# Security-focused policy rules
# Blocks dangerous security configurations

import future.keywords.if
import future.keywords.in

# Deny security group rules that open all ports to the world
deny[msg] if {
    resource := input.resource_changes[_]
    resource.type == "aws_security_group_rule"
    resource.change.after.cidr_blocks[_] == "0.0.0.0/0"
    resource.change.after.from_port == 0
    resource.change.after.to_port == 65535
    
    msg := sprintf(
        "SECURITY: Resource %s opens all ports (0-65535) to 0.0.0.0/0. " +
        "This is a critical security risk.",
        [resource.address]
    )
}

# Deny security group rules with common sensitive ports open to world
# SSH (22), RDP (3389), MongoDB (27017), Redis (6379), PostgreSQL (5432), MySQL (3306)
deny[msg] if {
    resource := input.resource_changes[_]
    resource.type == "aws_security_group_rule"
    resource.change.after.cidr_blocks[_] == "0.0.0.0/0"
    resource.change.after.from_port in {22, 3389, 27017, 6379, 5432, 3306}
    
    msg := sprintf(
        "SECURITY: Resource %s opens sensitive port %d to 0.0.0.0/0. " +
        "This violates security policy.",
        [resource.address, resource.change.after.from_port]
    )
}

# Warn on overly permissive IAM policy statements
warn[msg] if {
    resource := input.resource_changes[_]
    resource.type == "aws_iam_policy"
    policy := json.unmarshal(resource.change.after.policy)
    statement := policy.Statement[_]
    statement.Effect == "Allow"
    statement.Action == "*"
    statement.Resource == "*"
    
    msg := sprintf(
        "WARNING: IAM policy %s has overly permissive statement (Action: *, Resource: *). " +
        "Consider using least-privilege access.",
        [resource.address]
    )
}

# Deny unencrypted storage resources
deny[msg] if {
    resource := input.resource_changes[_]
    resource.type in {"aws_db_instance", "aws_rds_cluster", "aws_ebs_volume"}
    not resource.change.after.storage_encrypted
    
    msg := sprintf(
        "SECURITY: Resource %s does not have storage encryption enabled. " +
        "Encryption is mandatory for all storage resources.",
        [resource.address]
    )
}

# Deny unencrypted S3 buckets
deny[msg] if {
    resource := input.resource_changes[_]
    resource.type == "aws_s3_bucket"
    not resource.change.after.server_side_encryption_configuration
    
    msg := sprintf(
        "SECURITY: S3 bucket %s does not have server-side encryption enabled. " +
        "Encryption is mandatory for all S3 buckets.",
        [resource.address]
    )
}

# Warn on IAM users (prefer roles)
warn[msg] if {
    resource := input.resource_changes[_]
    resource.type == "aws_iam_user"
    
    msg := sprintf(
        "WARNING: IAM user %s is being created. Consider using IAM roles instead " +
        "for better security posture.",
        [resource.address]
    )
}
