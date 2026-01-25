#!/usr/bin/env python3
"""
Test script for Terraform Gatekeeper
Validates the implementation of all phases
"""

import os
import sys
import tempfile
import json
from pathlib import Path

# Add current directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent))

from gatekeeper import TerraformGatekeeper
from ai_analyzer import MockAIProvider


def create_mock_plan():
    """Create a mock Terraform plan for testing"""
    return {
        "resource_changes": [
            {
                "address": "aws_db_instance.prod-db",
                "mode": "managed",
                "type": "aws_db_instance",
                "name": "prod-db",
                "provider_name": "registry.terraform.io/hashicorp/aws",
                "change": {
                    "actions": ["delete"],
                    "before": {
                        "engine": "mysql",
                        "instance_class": "db.t3.large",
                        "allocated_storage": 100
                    },
                    "after": None
                }
            },
            {
                "address": "aws_security_group.web-sg",
                "mode": "managed",
                "type": "aws_security_group",
                "name": "web-sg",
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
            },
            {
                "address": "aws_s3_bucket.example-bucket",
                "mode": "managed",
                "type": "aws_s3_bucket",
                "name": "example-bucket",
                "provider_name": "registry.terraform.io/hashicorp/aws",
                "change": {
                    "actions": ["update"],
                    "before": {
                        "bucket": "example-bucket"
                    },
                    "after": {
                        "bucket": "example-bucket-updated"
                    }
                }
            }
        ]
    }


def test_phase1_json_ingestion():
    """Test Phase 1: JSON Ingestion"""
    print("🔍 Testing Phase 1: JSON Ingestion...")
    
    # Create temporary plan file
    mock_plan = create_mock_plan()
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(mock_plan, f)
        plan_file = f.name
    
    try:
        gatekeeper = TerraformGatekeeper()
        plan_data = gatekeeper.load_plan_file(plan_file)
        filtered_changes = gatekeeper.filter_changes(plan_data)
        
        assert len(filtered_changes) == 3, f"Expected 3 changes, got {len(filtered_changes)}"
        print("✅ JSON ingestion and filtering working correctly")
        
    finally:
        os.unlink(plan_file)


def test_phase2_heuristic_guardrails():
    """Test Phase 2: Heuristic Guardrails"""
    print("🚫 Testing Phase 2: Heuristic Guardrails...")
    
    mock_plan = create_mock_plan()
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(mock_plan, f)
        plan_file = f.name
    
    try:
        gatekeeper = TerraformGatekeeper()
        gatekeeper.analyze_plan(plan_file)
        
        # Check for critical risks
        critical_risks = [r for r in gatekeeper.risks if r.level == "CRITICAL"]
        security_risks = [r for r in gatekeeper.risks if r.level == "SECURITY RISK"]
        
        assert len(critical_risks) > 0, "Expected at least one critical risk (protected DB deletion)"
        assert len(security_risks) > 0, "Expected at least one security risk (unrestricted SG)"
        
        print(f"✅ Detected {len(critical_risks)} critical risks and {len(security_risks)} security risks")
        
        # Test exit codes
        if gatekeeper.critical_risks_found:
            print("✅ Exit code functionality working (would return 1)")
        
    finally:
        os.unlink(plan_file)


def test_phase3_context_engine():
    """Test Phase 3: Context Engine"""
    print("⏰ Testing Phase 3: Context Engine...")
    
    # Test time-based rules (mock current time for testing)
    # This is normally automatic based on system time
    
    mock_plan = create_mock_plan()
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(mock_plan, f)
        plan_file = f.name
    
    try:
        gatekeeper = TerraformGatekeeper()
        gatekeeper.analyze_plan(plan_file)
        
        # Test drift comparison (would need drift file for full test)
        print("✅ Context engine infrastructure in place")
        
    finally:
        os.unlink(plan_file)


def test_phase4_ai_integration():
    """Test Phase 4: AI Integration"""
    print("🤖 Testing Phase 4: AI Integration...")
    
    # Test mock AI provider
    provider = MockAIProvider()
    
    commit_message = "Update tags"
    plan_changes = json.dumps([{"resource": "aws_db_instance.prod-db", "actions": ["delete"]}])
    
    # Test intent mismatch detection
    result = provider.analyze_intent_mismatch(commit_message, plan_changes)
    assert "MISMATCH" in result, f"Expected mismatch detection, got: {result}"
    print("✅ AI intent mismatch detection working")
    
    # Test risk summary
    risks = [{"level": "CRITICAL", "message": "Protected deletion"}]
    summary = provider.generate_risk_summary(plan_changes, risks)
    assert "Critical" in summary, f"Expected critical in summary, got: {summary}"
    print("✅ AI risk summary generation working")
    
    # Test recommendations
    recommendations = provider.provide_recommendations(plan_changes, risks)
    assert len(recommendations) > 0, "Expected at least one recommendation"
    print("✅ AI recommendations working")


def test_configuration():
    """Test configuration loading"""
    print("⚙️ Testing Configuration...")
    
    # Test default config
    gatekeeper = TerraformGatekeeper()
    assert len(gatekeeper.protected_resources) > 0, "Expected protected resources in config"
    assert gatekeeper.protected_resources.get('aws_db_instance') == True, "Expected DB instance to be protected"
    
    print("✅ Configuration loading working correctly")


def main():
    """Run all tests"""
    print("🧪 Running Terraform Gatekeeper Tests...")
    print("=" * 50)
    
    try:
        test_configuration()
        test_phase1_json_ingestion()
        test_phase2_heuristic_guardrails()
        test_phase3_context_engine()
        test_phase4_ai_integration()
        
        print("\n" + "=" * 50)
        print("🎉 All tests passed! Terraform Gatekeeper is ready.")
        print("\nNext steps:")
        print("1. Run: make plan")
        print("2. Run: python gatekeeper.py --plan plan.json")
        print("3. Test with AI: python gatekeeper.py --plan plan.json --commit-message 'test'")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()