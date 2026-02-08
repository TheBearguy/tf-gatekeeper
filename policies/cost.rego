package terraform.analysis

# Cost-related policy rules
# Flags expensive resources and cost increases

import future.keywords.if
import future.keywords.in

# List of expensive instance types
expensive_instance_types = {
    "p3.2xlarge", "p3.8xlarge", "p3.16xlarge",
    "p4d.24xlarge", "p4de.24xlarge",
    "g5.xlarge", "g5.2xlarge", "g5.12xlarge", "g5.48xlarge",
    "inf1.24xlarge", "inf2.48xlarge",
    "x1.32xlarge", "x1e.32xlarge",
    "u-6tb1.112xlarge", "u-9tb1.112xlarge", "u-12tb1.112xlarge",
    "u-18tb1.112xlarge", "u-24tb1.112xlarge",
}

# Deny creation of extremely expensive instance types
deny[msg] if {
    resource := input.resource_changes[_]
    resource.type in {"aws_instance", "aws_launch_template"}
    resource.change.after.instance_type in expensive_instance_types
    not input.emergency_override
    
    msg := sprintf(
        "COST: Resource %s uses expensive instance type %s. This instance costs >$10/hour. Verify this is necessary.",
        [resource.address, resource.change.after.instance_type]
    )
}

# Warn on large instance types
warn[msg] if {
    resource := input.resource_changes[_]
    resource.type in {"aws_instance", "aws_launch_template"}
    instance_type := resource.change.after.instance_type
    startswith(instance_type, "m5.16xlarge")
    
    msg := sprintf(
        "COST: Resource %s uses large instance type %s. Consider if smaller instances would suffice.",
        [resource.address, instance_type]
    )
}

# Warn on unused NAT Gateways (check if there are no private subnets)
warn[msg] if {
    resource := input.resource_changes[_]
    resource.type == "aws_nat_gateway"
    
    # Count NAT gateways being created
    nat_count := count([r | r := input.resource_changes[_]; r.type == "aws_nat_gateway"; r.change.actions[_] == "create"])
    
    nat_count > 1
    
    msg := sprintf(
        "COST: Creating %d NAT gateways. Each NAT gateway costs ~$32/month plus data processing fees. Consider consolidating or using alternatives if possible.",
        [nat_count]
    )
}

# Info on potential cost savings
info[msg] if {
    resource := input.resource_changes[_]
    resource.type == "aws_instance"
    resource.change.after.instance_type == "t2.micro"
    
    msg := "COST: Consider using t3/t4g instances instead of t2 for better price-performance."
}

# Deny large number of expensive resources
deny[msg] if {
    expensive_count := count([r | r := input.resource_changes[_]; r.type == "aws_instance"; r.change.after.instance_type in {"m5.4xlarge", "m5.8xlarge", "m5.12xlarge", "m5.16xlarge", "m5.24xlarge"}])
    expensive_count > 5
    
    msg := sprintf(
        "COST: Creating %d expensive EC2 instances. Total estimated cost >$2000/month. Verify capacity requirements and consider reserved instances for long-term usage.",
        [expensive_count]
    )
}
