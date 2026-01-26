#!/usr/bin/env python3
"""
Test script to verify time-based rules functionality
"""

import json
import tempfile
import os
from pathlib import Path
from datetime import datetime, time
import sys

# Add current directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent))

from gatekeeper import TerraformGatekeeper

def create_warning_plan():
    """Create a mock plan with warnings (non-critical risks)"""
    return {
        "resource_changes": [
            {
                "address": "aws_security_group.restrictive_sg",
                "mode": "managed",
                "type": "aws_security_group",
                "name": "restrictive_sg",
                "provider_name": "registry.terraform.io/hashicorp/aws",
                "change": {
                    "actions": ["update"],
                    "before": {
                        "ingress": [
                            {
                                "from_port": 80,
                                "to_port": 80,
                                "protocol": "tcp",
                                "cidr_blocks": ["192.168.1.0/24"]
                            }
                        ]
                    },
                    "after": {
                        "ingress": [
                            {
                                "from_port": 80,
                                "to_port": 80,
                                "protocol": "tcp",
                                "cidr_blocks": ["0.0.0.0/0"]
                            }
                        ]
                    }
                }
            }
        ]
    }

def test_time_based_rules():
    """Test time-based rules that upgrade warnings to critical"""
    print("⏰ Testing Time-Based Rules...")
    
    # Create mock plan with warnings
    mock_plan = create_warning_plan()
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(mock_plan, f)
        plan_file = f.name
    
    try:
        gatekeeper = TerraformGatekeeper()
        
        # Test normal time (should not upgrade warnings)
        print("\n📅 Testing normal time (Monday 10 AM)...")
        original_time = datetime.now()
        
        # Mock current time to Monday 10 AM
        test_time = datetime(2024, 1, 15, 10, 0)  # Monday 10 AM
        gatekeeper.apply_time_based_rules = lambda: None  # Disable time rules temporarily
        
        gatekeeper.analyze_plan(plan_file)
        warning_risks_normal = [r for r in gatekeeper.risks if r.level == "WARNING"]
        critical_risks_normal = [r for r in gatekeeper.risks if r.level == "CRITICAL"]
        
        print(f"   Warning risks at normal time: {len(warning_risks_normal)}")
        print(f"   Critical risks at normal time: {len(critical_risks_normal)}")
        
        # Test weekend time (should upgrade warnings to critical)
        print("\n📅 Testing weekend time (Saturday 2 PM)...")
        
        # Create a new gatekeeper instance and test time-based rules directly
        gatekeeper_weekend = TerraformGatekeeper()
        gatekeeper_weekend.risks = warning_risks_normal.copy() if warning_risks_normal else []
        
        # Mock current time to Saturday 2 PM
        class MockDateTime:
            @classmethod
            def now(cls):
                return datetime(2024, 1, 20, 14, 0)  # Saturday 2 PM
            
            @classmethod
            def weekday(cls):
                return 5  # Saturday (0=Monday, 6=Sunday)
        
        # Mock datetime to simulate weekend
        import gatekeeper
        original_datetime = gatekeeper.datetime
        gatekeeper.datetime = MockDateTime
        
        try:
            gatekeeper_weekend.apply_time_based_rules()
            
            warning_risks_weekend = [r for r in gatekeeper_weekend.risks if r.level == "WARNING"]
            critical_risks_weekend = [r for r in gatekeeper_weekend.risks if r.level == "CRITICAL"]
            
            print(f"   Warning risks at weekend: {len(warning_risks_weekend)}")
            print(f"   Critical risks at weekend: {len(critical_risks_weekend)}")
            
            # Test Friday afternoon
            print("\n📅 Testing Friday afternoon (Friday 4 PM)...")
            
            gatekeeper_friday = TerraformGatekeeper()
            gatekeeper_friday.risks = warning_risks_normal.copy() if warning_risks_normal else []
            
            class MockFridayDateTime:
                @classmethod
                def now(cls):
                    return datetime(2024, 1, 19, 16, 0)  # Friday 4 PM
                
                @classmethod
                def weekday(cls):
                    return 4  # Friday
                
                @property
                def time(self):
                    return time(16, 0)
            
            gatekeeper.datetime = MockFridayDateTime
            
            gatekeeper_friday.apply_time_based_rules()
            
            warning_risks_friday = [r for r in gatekeeper_friday.risks if r.level == "WARNING"]
            critical_risks_friday = [r for r in gatekeeper_friday.risks if r.level == "CRITICAL"]
            
            print(f"   Warning risks at Friday: {len(warning_risks_friday)}")
            print(f"   Critical risks at Friday: {len(critical_risks_friday)}")
            
            # Validate results
            success = True
            
            if len(critical_risks_weekend) > len(critical_risks_normal):
                print("✅ Weekend time-based rules working correctly")
            else:
                print("❌ Weekend time-based rules not working")
                success = False
                
            if len(critical_risks_friday) > len(critical_risks_normal):
                print("✅ Friday afternoon time-based rules working correctly")
            else:
                print("❌ Friday afternoon time-based rules not working")
                success = False
                
            # Restore original datetime
            gatekeeper.datetime = original_datetime
            
            return success
            
        except Exception as e:
            gatekeeper.datetime = original_datetime
            print(f"❌ Error testing time-based rules: {e}")
            return False
            
    finally:
        os.unlink(plan_file)

if __name__ == "__main__":
    success = test_time_based_rules()
    print(f"\n🎯 Time-based rules test result: {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)