#!/usr/bin/env python3
"""Test script for tf-gate with multiple blast radius scenarios.

This script tests the tf-gate validation pipeline with GREEN, YELLOW, and RED
blast radius plans to ensure all phases work correctly.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tf_gate.phases.phase1_ingest import ingest_plan
from tf_gate.phases.phase2_opa import run_phase2_validation
from tf_gate.phases.phase3_context import run_phase3_context_analysis, RiskLevel
from tf_gate.phases.phase4_intent import run_phase4_intent_validation, ChangeImpactReport
from tf_gate.utils.blast_radius import BlastRadiusLevel
from tf_gate.utils.config import Config


def get_default_policy_dir() -> Path:
    """Get the default policy directory."""
    return Path(__file__).parent.parent / "policies"


def save_report_to_file(plan_name: str, report: str, output_dir: Path) -> Path:
    """Save the AI-generated report to a markdown file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{plan_name}_report_{timestamp}.md"
    filepath = output_dir / filename
    
    with open(filepath, 'w') as f:
        f.write(report)
    
    return filepath


def display_report(report: str, indent: int = 3):
    """Display the report with proper formatting."""
    indent_str = "   " * indent
    lines = report.split('\n')
    
    for line in lines:
        if line.startswith('#'):
            # Header line - make it bold
            print(f"{indent_str}\033[1m{line}\033[0m")
        elif line.startswith('**') and line.endswith('**'):
            # Bold line
            print(f"{indent_str}\033[1m{line}\033[0m")
        elif line.startswith('- ') or line.startswith('* '):
            # List item
            print(f"{indent_str}  {line}")
        elif line.strip() == '':
            # Empty line
            print()
        else:
            print(f"{indent_str}{line}")


def test_plan(plan_file: str, description: str, commit_message: str | None = None) -> dict:
    """Test a single plan file through all 4 phases."""
    print(f"\n{'='*60}")
    print(f"Testing: {description}")
    print(f"Plan File: {plan_file}")
    print('='*60)
    
    plan_path = Path(__file__).parent / plan_file
    config = Config()
    policy_dir = get_default_policy_dir()
    
    results = {
        "plan_file": str(plan_file),
        "description": description,
        "timestamp": datetime.now().isoformat(),
        "phases": {}
    }
    
    try:
        # Phase 1: Ingestion & Blast Radius
        print("\n📝 Phase 1: Ingestion & Blast Radius")
        changes, blast_radius, metadata = ingest_plan(
            plan_path,
            thresholds=config.get("blast_radius.thresholds"),
        )
        
        print(f"   Total resources: {blast_radius.total_resources}")
        print(f"   Create: {blast_radius.create_count}, Update: {blast_radius.update_count}")
        print(f"   Delete: {blast_radius.delete_count}, Replace: {blast_radius.replace_count}")
        
        level_emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴"}[blast_radius.level.value]
        print(f"   {level_emoji} Blast Radius Level: {blast_radius.level.value.upper()}")
        
        if blast_radius.critical_resources:
            print(f"   ⚠️  Critical resources affected:")
            for resource in blast_radius.critical_resources:
                print(f"      - {resource}")
        
        results["phases"]["phase1"] = {
            "status": "passed",
            "blast_radius": {
                "level": blast_radius.level.value,
                "total_resources": blast_radius.total_resources,
                "create_count": blast_radius.create_count,
                "update_count": blast_radius.update_count,
                "delete_count": blast_radius.delete_count,
                "replace_count": blast_radius.replace_count,
                "critical_resources": blast_radius.critical_resources
            }
        }
        
        # Phase 2: Policy Validation
        print("\n🔒 Phase 2: Policy Validation (OPA)")
        try:
            validation_results = run_phase2_validation(
                policy_dir=policy_dir,
                resource_changes=changes,
                blast_radius=blast_radius,
                metadata=metadata,
                strict_mode=config.get("opa.strict_mode", True),
                emergency_override=False,
            )
            
            deny_count = len(validation_results.get("deny", []))
            warn_count = len(validation_results.get("warn", []))
            
            if deny_count > 0:
                print(f"   ❌ {deny_count} policy violations (deny)")
                for msg in validation_results["deny"]:
                    print(f"      - {msg}")
            else:
                print("   ✅ No policy violations")
            
            if warn_count > 0:
                print(f"   ⚠️  {warn_count} warnings")
                for msg in validation_results["warn"]:
                    print(f"      - {msg}")
            
            results["phases"]["phase2"] = {
                "status": "passed",
                "deny_count": deny_count,
                "warn_count": warn_count,
                "deny_messages": validation_results.get("deny", []),
                "warn_messages": validation_results.get("warn", [])
            }
            
        except Exception as e:
            print(f"   ⚠️  Phase 2 Error: {e}")
            results["phases"]["phase2"] = {"status": "error", "error": str(e)}
        
        # Phase 3: Context Analysis
        print("\n🌐 Phase 3: Context Analysis")
        try:
            # Use a dummy terraform directory for testing
            terraform_dir = Path(__file__).parent
            
            context_results = run_phase3_context_analysis(
                terraform_dir=terraform_dir,
                plan_resources=changes,
                terraform_version=metadata.get("terraform_version", "unknown"),
                base_risk=RiskLevel.LOW,
                friday_cutoff_hour=config.get("phases.phase_3_time_gating.friday_cutoff_hour", 15),
                weekend_blocking=config.get("phases.phase_3_time_gating.weekend_blocking", True),
            )
            
            temporal = context_results["temporal_context"]
            drift = context_results["drift_result"]
            
            risk_emoji = {
                1: "🟢",
                2: "🟡",
                3: "🔴",
                4: "🔥",
            }.get(temporal.risk_level.value, "⚪")
            
            print(f"   {risk_emoji} Temporal Risk: {temporal.risk_level.name}")
            if temporal.is_weekend:
                print("   ⚠️  Weekend deployment detected")
            if temporal.is_friday_afternoon:
                print("   ⚠️  Friday afternoon deployment detected")
            
            if drift.has_drift:
                print(f"   🔄 Drift detected: {len(drift.drifted_resources)} resources")
            else:
                print("   ✅ No drift detected")
            
            results["phases"]["phase3"] = {
                "status": "passed",
                "temporal_risk": temporal.risk_level.name,
                "is_weekend": temporal.is_weekend,
                "is_friday_afternoon": temporal.is_friday_afternoon,
                "has_drift": drift.has_drift
            }
            
        except Exception as e:
            print(f"   ⚠️  Phase 3 Error: {e}")
            results["phases"]["phase3"] = {"status": "error", "error": str(e)}
        
        # Phase 4: Intent Validation & Impact Report
        print("\n🧠 Phase 4: Intent Validation & Impact Analysis")
        if commit_message:
            # First test without LLM (keyword-based)
            print("\n   📊 Keyword-based validation:")
            try:
                intent_result_keyword = run_phase4_intent_validation(
                    commit_message=commit_message,
                    resource_changes=changes,
                    use_llm=False,
                )
                
                if intent_result_keyword.aligned:
                    print("   ✅ Intent aligned (keyword-based)")
                else:
                    print("   ⚠️  Intent mismatch (keyword-based)")
                    print(f"   Explanation: {intent_result_keyword.explanation}")
                
                print(f"   Confidence: {intent_result_keyword.confidence:.0%}")
                
                results["phases"]["phase4_keyword"] = {
                    "status": "passed",
                    "aligned": intent_result_keyword.aligned,
                    "confidence": intent_result_keyword.confidence,
                    "explanation": intent_result_keyword.explanation
                }
                
            except Exception as e:
                print(f"   ⚠️  Phase 4 Keyword Error: {e}")
                results["phases"]["phase4_keyword"] = {"status": "error", "error": str(e)}
            
            # Then test with LLM and generate detailed report
            print("\n   🤖 LLM-based validation with Impact Report (LMStudio):")
            print("   ⏳ Generating AI analysis... (this may take 10-30 seconds)")
            try:
                intent_result_llm = run_phase4_intent_validation(
                    commit_message=commit_message,
                    resource_changes=changes,
                    use_llm=True,
                    llm_provider="lmstudio",
                    generate_report=True,  # Generate detailed report
                )
                
                if intent_result_llm.aligned:
                    print("   ✅ Intent aligned (LLM)")
                else:
                    print("   ⚠️  Intent mismatch (LLM)")
                    print(f"   Explanation: {intent_result_llm.explanation}")
                
                print(f"   Confidence: {intent_result_llm.confidence:.0%}")
                
                results["phases"]["phase4_llm"] = {
                    "status": "passed",
                    "aligned": intent_result_llm.aligned,
                    "confidence": intent_result_llm.confidence,
                    "explanation": intent_result_llm.explanation
                }
                
                # Display and save the report if available
                if intent_result_llm.report:
                    print("\n   📊 AI-GENERATED IMPACT REPORT FOR MANAGERS:")
                    print("   " + "=" * 56)
                    display_report(intent_result_llm.report, indent=3)
                    print("   " + "=" * 56)
                    
                    # Save report to file
                    reports_dir = Path(__file__).parent / "reports"
                    reports_dir.mkdir(exist_ok=True)
                    plan_name = Path(plan_file).stem
                    report_path = save_report_to_file(plan_name, intent_result_llm.report, reports_dir)
                    print(f"\n   💾 Report saved to: {report_path}")
                    
                    results["phases"]["phase4_llm"]["has_report"] = True
                    results["phases"]["phase4_llm"]["report_file"] = str(report_path)
                
            except Exception as e:
                print(f"   ⚠️  Phase 4 LLM Error: {e}")
                print("   💡 Make sure LMStudio is running with the model loaded!")
                results["phases"]["phase4_llm"] = {"status": "error", "error": str(e)}
        else:
            print("   ⏭️  Skipped (no commit message provided)")
            results["phases"]["phase4"] = {"status": "skipped"}
        
        # Summary
        print("\n📊 Summary")
        should_block = (
            blast_radius.level == BlastRadiusLevel.RED or
            results["phases"]["phase2"].get("deny_count", 0) > 0
        )
        
        if should_block:
            print("   🔴 VALIDATION WOULD BLOCK THIS PLAN")
        else:
            print("   ✅ VALIDATION WOULD ALLOW THIS PLAN")
        
        results["should_block"] = should_block
        results["status"] = "completed"
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        results["status"] = "failed"
        results["error"] = str(e)
    
    return results


def main():
    """Run all test scenarios."""
    print("🧪 tf-gate Test Suite with AI Impact Reports")
    print("=" * 60)
    print("\n📋 This test suite will:")
    print("   1. Test GREEN blast radius (low risk)")
    print("   2. Test YELLOW blast radius (medium risk)")
    print("   3. Test RED blast radius (high risk)")
    print("   4. Generate AI impact reports for each scenario")
    print("\n⚠️  Make sure LMStudio is running with qwen2.5-coder-7b-instruct model!")
    print("=" * 60)
    
    test_scenarios = [
        {
            "file": "tfplan_green.json",
            "description": "GREEN: Low risk - 3 new web servers (creates only)",
            "commit_message": "Add staging web servers for load testing"
        },
        {
            "file": "tfplan_yellow.json",
            "description": "YELLOW: Medium risk - 9 resources with 1 replacement",
            "commit_message": "Scale up worker pool and replace load balancer"
        },
        {
            "file": "tfplan_red.json",
            "description": "RED: High risk - 23 resources, deletions of critical DB/KMS/S3, security violation",
            "commit_message": "Update database configuration and security groups"
        }
    ]
    
    all_results = []
    reports_generated = []
    
    for scenario in test_scenarios:
        result = test_plan(
            scenario["file"],
            scenario["description"],
            scenario["commit_message"]
        )
        all_results.append(result)
        
        # Track generated reports
        if result.get("phases", {}).get("phase4_llm", {}).get("has_report"):
            reports_generated.append({
                "plan": scenario["file"],
                "report_file": result["phases"]["phase4_llm"]["report_file"]
            })
    
    # Final Summary
    print("\n" + "="*60)
    print("📋 FINAL TEST SUMMARY")
    print("="*60)
    
    for result in all_results:
        status = "✅" if result.get("status") == "completed" else "❌"
        block_status = "🚫 BLOCKED" if result.get("should_block") else "✅ ALLOWED"
        print(f"\n{status} {result['description']}")
        print(f"   Result: {block_status}")
        
        if "phases" in result and "phase1" in result["phases"]:
            br = result["phases"]["phase1"]["blast_radius"]
            print(f"   Blast Radius: {br['level'].upper()}")
            print(f"   Resources: {br['total_resources']} (C:{br['create_count']} U:{br['update_count']} D:{br['delete_count']} R:{br['replace_count']})")
        
        if "phases" in result and "phase2" in result["phases"]:
            p2 = result["phases"]["phase2"]
            if p2.get("status") == "passed":
                print(f"   Policy Violations: {p2.get('deny_count', 0)} deny, {p2.get('warn_count', 0)} warn")
        
        # Show Phase 4 comparison and report status
        if "phases" in result and "phase4_keyword" in result["phases"]:
            p4k = result["phases"]["phase4_keyword"]
            print(f"\n   Intent Validation:")
            print(f"   - Keyword-based: {'✅' if p4k.get('aligned') else '❌'} ({p4k.get('confidence', 0):.0%} confidence)")
            
            if "phase4_llm" in result["phases"]:
                p4l = result["phases"]["phase4_llm"]
                if p4l.get("status") == "passed":
                    print(f"   - LLM-based: {'✅' if p4l.get('aligned') else '❌'} ({p4l.get('confidence', 0):.0%} confidence)")
                    if p4l.get("has_report"):
                        print(f"   - 📊 AI Report: {p4l.get('report_file', 'Generated')}")
                else:
                    print(f"   - LLM-based: ❌ {p4l.get('error', 'Failed')}")
    
    # Save results to file
    results_file = Path(__file__).parent / "test_results.json"
    with open(results_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: {results_file}")
    
    # Reports summary
    if reports_generated:
        print(f"\n📊 AI IMPACT REPORTS GENERATED:")
        print("-" * 60)
        for report in reports_generated:
            print(f"   📄 {report['plan']}")
            print(f"      Report: {report['report_file']}")
        print("-" * 60)
        print("\n💡 These reports can be shared with tech managers for review.")
    
    print("\n✨ Test suite completed!")


if __name__ == "__main__":
    main()
