#!/usr/bin/env python3
"""
Terraform Gatekeeper - Security Analysis Tool
Analyzes Terraform plans for security risks and policy violations
"""

import json
import sys
import argparse
import yaml
from datetime import datetime, time
from typing import Dict, List, Any, Optional
import logging
from ai_analyzer import AIAnalyzer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('gatekeeper.log')
    ]
)
logger = logging.getLogger(__name__)


class Risk:
    def __init__(self, level: str, message: str, resource_type: str, resource_name: str):
        self.level = level
        self.message = message
        self.resource_type = resource_type
        self.resource_name = resource_name

    def __repr__(self):
        return f"[{self.level}] {self.resource_type}.{self.resource_name}: {self.message}"


class TerraformGatekeeper:
    def __init__(self, config_file: str = "config.yaml"):
        self.config = self.load_config(config_file)
        self.risks: List[Risk] = []
        self.protected_resources = self.config.get('protected_resources', {})
        self.critical_risks_found = False
        self.drift_detection = self.config.get('drift_detection', {}).get('enabled', False)
        self.ai_analyzer = AIAnalyzer(self.config.get('ai_integration', {}))

    def load_config(self, config_file: str) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open(config_file, 'r') as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            logger.warning(f"Config file {config_file} not found, using defaults")
            return self.get_default_config()

    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            'protected_resources': {
                'aws_db_instance': True,
                'aws_kms_key': True,
                'aws_s3_bucket': True,
                'aws_security_group': True
            },
            'security_rules': {
                'allow_wildcard_ingress': False,
                'allow_wildcard_egress': False
            }
        }

    def load_plan_file(self, plan_file: str) -> Dict[str, Any]:
        """Load Terraform plan JSON file"""
        try:
            with open(plan_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Plan file {plan_file} not found")
            sys.exit(1)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in plan file {plan_file}: {e}")
            sys.exit(1)

    def filter_changes(self, plan_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Filter resource changes to only include delete or update actions"""
        if 'resource_changes' not in plan_data:
            return []

        filtered_changes = []
        for resource_change in plan_data['resource_changes']:
            change = resource_change.get('change', {})
            actions = change.get('actions', [])

            if 'delete' in actions or 'update' in actions:
                filtered_changes.append(resource_change)

        logger.info(f"Filtered {len(filtered_changes)} resources with delete/update actions")
        return filtered_changes

    def check_protected_resources(self, resource_change: Dict[str, Any]) -> Optional[Risk]:
        """Check if protected resource is being deleted"""
        resource = resource_change.get('address', '')
        resource_type = resource.split('.')[0] if '.' in resource else resource

        if self.protected_resources.get(resource_type, False):
            change = resource_change.get('change', {})
            actions = change.get('actions', [])

            if 'delete' in actions:
                return Risk(
                    level="CRITICAL",
                    message="Protected resource deletion detected",
                    resource_type=resource_type,
                    resource_name=resource
                )

        return None

    def check_security_group_risks(self, resource_change: Dict[str, Any]) -> Optional[Risk]:
        """Check security group configurations for risky settings"""
        resource_type = resource_change.get('address', '').split('.')[0] if '.' in resource_change.get('address', '') else ''

        if resource_type == 'aws_security_group':
            change = resource_change.get('change', {})
            after_block = change.get('after', {})

            # Check ingress rules
            ingress_rules = after_block.get('ingress', [])
            for rule in ingress_rules:
                if (rule.get('from_port') == 0 and 
                    rule.get('to_port') == 0 and
                    rule.get('protocol') == '-1' and
                    '0.0.0.0/0' in rule.get('cidr_blocks', [])):
                    return Risk(
                        level="SECURITY RISK",
                        message="Security group allows unrestricted access (0.0.0.0/0, all ports)",
                        resource_type=resource_type,
                        resource_name=resource_change.get('address', '')
                    )

            # Check egress rules
            egress_rules = after_block.get('egress', [])
            for rule in egress_rules:
                if (rule.get('from_port') == 0 and 
                    rule.get('to_port') == 0 and
                    rule.get('protocol') == '-1' and
                    '0.0.0.0/0' in rule.get('cidr_blocks', [])):
                    return Risk(
                        level="SECURITY RISK",
                        message="Security group allows unrestricted egress (0.0.0.0/0, all ports)",
                        resource_type=resource_type,
                        resource_name=resource_change.get('address', '')
                    )

        return None

    def check_drift_conflicts(self, resource_change: Dict[str, Any], drift_data: Dict[str, Any]) -> Optional[Risk]:
        """Check for conflicts between current state and drift"""
        resource_address = resource_change.get('address', '')
        
        # Find corresponding drift change
        drift_changes = self.filter_changes(drift_data)
        
        for drift_change in drift_changes:
            if drift_change.get('address') == resource_address:
                # Check if plan is reverting manual changes
                plan_actions = resource_change.get('change', {}).get('actions', [])
                drift_actions = drift_change.get('change', {}).get('actions', [])
                
                # If drift shows manual changes and plan shows revert
                if 'update' in drift_actions and 'update' in plan_actions:
                    # Check if the plan is reverting to a previous state
                    plan_after = resource_change.get('change', {}).get('after', {})
                    drift_after = drift_change.get('change', {}).get('after', {})
                    
                    # Simple comparison - in real implementation, you'd want more sophisticated comparison
                    if plan_after != drift_after:
                        return Risk(
                            level="DRIFT CONFLICT",
                            message="Plan may be reverting manually modified resources",
                            resource_type=resource_address.split('.')[0],
                            resource_name=resource_address
                        )
        
        return None

    def apply_time_based_rules(self) -> None:
        """Upgrade warnings to critical based on time"""
        now = datetime.now()
        current_time = now.time()
        current_day = now.weekday()  # Monday=0, Sunday=6

        # Check if it's Friday after 3 PM or weekend
        if (current_day == 4 and current_time >= time(15, 0)) or (current_day >= 5):
            logger.info("Time-based rule activated: Upgrading warnings to CRITICAL")
            for risk in self.risks:
                if risk.level == "WARNING":
                    risk.level = "CRITICAL"
                    if risk.level == "CRITICAL":
                        self.critical_risks_found = True

    def analyze_plan(self, plan_file: str, drift_file: Optional[str] = None) -> None:
        """Analyze Terraform plan for security risks"""
        logger.info(f"🔍 Analyzing plan file: {plan_file}")

        # Load plan data
        plan_data = self.load_plan_file(plan_file)

        # Load drift data if provided
        drift_data = None
        if drift_file and self.drift_detection:
            try:
                drift_data = self.load_plan_file(drift_file)
                logger.info(f"🔍 Loaded drift file: {drift_file}")
            except FileNotFoundError:
                logger.warning(f"Drift file {drift_file} not found, skipping drift comparison")

        # Filter changes
        filtered_changes = self.filter_changes(plan_data)

        # Analyze each change
        for resource_change in filtered_changes:
            # Check protected resources
            protected_risk = self.check_protected_resources(resource_change)
            if protected_risk:
                self.risks.append(protected_risk)
                if protected_risk.level == "CRITICAL":
                    self.critical_risks_found = True
                continue

            # Check security group risks
            security_risk = self.check_security_group_risks(resource_change)
            if security_risk:
                self.risks.append(security_risk)
                if security_risk.level == "CRITICAL":
                    self.critical_risks_found = True

            # Check for drift conflicts
            if drift_data:
                drift_risk = self.check_drift_conflicts(resource_change, drift_data)
                if drift_risk:
                    self.risks.append(drift_risk)
                    if drift_risk.level == "CRITICAL":
                        self.critical_risks_found = True

        # Apply time-based rules
        self.apply_time_based_rules()

    def analyze_intent_mismatch(self, commit_message: str, filtered_changes: List[Dict[str, Any]]) -> str:
        """Analyze if commit message matches actual changes"""
        if not commit_message:
            return "No commit message provided for AI analysis"
        
        return self.ai_analyzer.analyze_intent_mismatch(commit_message, filtered_changes)

    def generate_ai_summary(self, filtered_changes: List[Dict[str, Any]]) -> str:
        """Generate AI-powered risk summary"""
        risks_data = [{'level': risk.level, 'message': risk.message} for risk in self.risks]
        return self.ai_analyzer.generate_risk_summary(filtered_changes, risks_data)

    def generate_recommendations(self, filtered_changes: List[Dict[str, Any]]) -> List[str]:
        """Generate AI-powered security recommendations"""
        risks_data = [{'level': risk.level, 'message': risk.message} for risk in self.risks]
        return self.ai_analyzer.provide_recommendations(filtered_changes, risks_data)

    def print_results(self, commit_message: Optional[str] = None) -> None:
        """Print analysis results"""
        if not self.risks:
            print("✅ No security risks detected")
            return

        print(f"\n🚨 Security Analysis Results ({len(self.risks)} risks found):")
        print("=" * 60)

        for risk in self.risks:
            icon = "🔴" if risk.level == "CRITICAL" else "🟡" if risk.level == "SECURITY RISK" else "🔵"
            print(f"{icon} {risk}")

        print("=" * 60)

        # Summary by severity
        critical_count = len([r for r in self.risks if r.level == "CRITICAL"])
        security_risk_count = len([r for r in self.risks if r.level == "SECURITY RISK"])
        warning_count = len([r for r in self.risks if r.level == "WARNING"])

        print(f"\n📊 Summary:")
        print(f"   Critical: {critical_count}")
        print(f"   Security Risk: {security_risk_count}")
        print(f"   Warnings: {warning_count}")

        # AI Analysis
        if commit_message:
            filtered_changes = self.filter_changes(self.load_plan_file('plan.json'))
            
            print(f"\n🤖 AI Analysis:")
            
            # Intent mismatch detection
            intent_result = self.analyze_intent_mismatch(commit_message, filtered_changes)
            print(f"   Intent Analysis: {intent_result}")
            
            if "MISMATCH" in intent_result:
                print("   ⚠️  WARNING: Intent mismatch detected! Review changes carefully.")
                self.critical_risks_found = True

            # AI-powered risk summary
            ai_summary = self.generate_ai_summary(filtered_changes)
            print(f"   AI Summary: {ai_summary}")

            # Recommendations
            recommendations = self.generate_recommendations(filtered_changes)
            if recommendations:
                print(f"\n💡 AI Recommendations:")
                for i, rec in enumerate(recommendations, 1):
                    print(f"   {i}. {rec}")

        if self.critical_risks_found:
            print(f"\n❌ CRITICAL RISKS FOUND - Pipeline should be blocked!")
            sys.exit(1)
        else:
            print(f"\n✅ Analysis complete - Pipeline can proceed")


def main():
    parser = argparse.ArgumentParser(description='Terraform Gatekeeper - Security Analysis Tool')
    parser.add_argument('--plan', required=True, help='Path to Terraform plan JSON file')
    parser.add_argument('--drift', help='Path to drift JSON file')
    parser.add_argument('--config', default='config.yaml', help='Path to configuration file')
    parser.add_argument('--commit-message', help='Git commit message for AI analysis')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Initialize gatekeeper
    gatekeeper = TerraformGatekeeper(args.config)

    # Analyze plan
    gatekeeper.analyze_plan(args.plan, args.drift)

    # Print results
    gatekeeper.print_results(args.commit_message)


if __name__ == "__main__":
    main()