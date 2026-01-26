#!/usr/bin/env python3
"""
Test script to verify protected resource deletion detection
"""

import json
import tempfile
import os
import sys
from pathlib import Path

# Add current directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent))

from gatekeeper import TerraformGatekeeper

def create_deletion_plan():
    """Create a mock plan with protected resource deletions"""
    return {
        "resource_changes": [
            {
                "address": "aws_kms_key.production_key",
                "mode": "managed",
                "type": "aws_kms_key",
                "name": "production_key",
                "provider_name": "registry.terraform.io/hashicorp/aws",
                "change": {
                    "actions": ["delete"],
                    "before": {
                        "description": "Production KMS key for data encryption",
                        "is_enabled": True
                    },
                    "after": None
                }
            },
            {
                "address": "aws_vpc.production_vpc",
                "mode": "managed",
                "type": "aws_vpc",
                "name": "production_vpc",
                "provider_name": "registry.terraform.io/hashicorp/aws",
                "change": {
                    "actions": ["delete"],
                    "before": {
                        "cidr_block": "10.0.0.0/16",
                        "tags": {"Name": "production-vpc"}
                    },
                    "after": None
                }
            },
            {
                "address": "aws_security_group.unrestricted_sg",
                "mode": "managed",
                "type": "aws_security_group",
                "name": "unrestricted_sg",
                "provider_name": "registry.terraform.io/hashicorp/aws",
                "change": {
                    "actions": ["update"],
                    "before": {
                        "ingress": [
                            {
                                "from_port": 80,
                                "to_port": 80,
                                "protocol": "tcp",
                                "cidr_blocks": ["0.0.0.0/0"]
                            }
                        ]
                    },
                    "after": {
                        "ingress": [
                            {
                                "from_port": 0,
                                "to_port": 0,
                                "protocol": "-1",
                                "cidr_blocks": ["0.0.0.0/0"]
                            }
                        ]
                    }
                }
            }
        ]
    }

def test_protected_resource_deletions():
    """Test protected resource deletion detection"""
    print("🔒 Testing Protected Resource Deletion Detection...")
    
    # Create mock plan with deletions
    mock_plan = create_deletion_plan()
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(mock_plan, f)
        plan_file = f.name
    
    try:
        gatekeeper = TerraformGatekeeper()
        gatekeeper.analyze_plan(plan_file)
        
        # Check for critical risks (protected deletions)
        critical_risks = [r for r in gatekeeper.risks if r.level == "CRITICAL"]
        security_risks = [r for r in gatekeeper.risks if r.level == "SECURITY RISK"]
        
        print(f"📊 Results:")
        print(f"   Critical risks detected: {len(critical_risks)}")
        print(f"   Security risks detected: {len(security_risks)}")
        
        if len(critical_risks) >= 2:  # Should detect KMS key and VPC deletions
            print("✅ Protected resource deletion detection working correctly")
            for risk in critical_risks:
                print(f"   🔴 {risk}")
        else:
            print("❌ Expected to detect at least 2 critical risks")
            
        if len(security_risks) >= 1:  # Should detect security group update
            print("✅ Security risk detection working correctly")
            for risk in security_risks:
                print(f"   🟡 {risk}")
        else:
            print("❌ Expected to detect at least 1 security risk")
        
        # Test exit code functionality
        if gatekeeper.critical_risks_found:
            print("✅ Exit code functionality working (would return 1 for critical risks)")
            return True
        else:
            print("❌ Exit code not working as expected")
            return False
            
    finally:
        os.unlink(plan_file)

if __name__ == "__main__":
    import sys
    success = test_protected_resource_deletions()
    sys.exit(0 if success else 1)