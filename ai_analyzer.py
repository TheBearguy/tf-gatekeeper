"""
AI Integration Module for Terraform Gatekeeper
Handles intent detection, mismatch analysis, and AI-powered risk assessment
"""

import json
import os
from typing import Dict, Any, Optional, List
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseAIProvider(ABC):
    """Abstract base class for AI providers"""
    
    @abstractmethod
    def analyze_intent_mismatch(self, commit_message: str, plan_changes: str) -> str:
        """Analyze if commit message matches plan changes"""
        pass
    
    @abstractmethod
    def generate_risk_summary(self, plan_changes: str, risks: List[Dict[str, Any]]) -> str:
        """Generate human-readable risk summary"""
        pass
    
    @abstractmethod
    def provide_recommendations(self, plan_changes: str, risks: List[Dict[str, Any]]) -> List[str]:
        """Provide security recommendations"""
        pass


class OpenAIProvider(BaseAIProvider):
    """OpenAI GPT provider implementation"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4"):
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.model = model
        
        if not self.api_key:
            logger.warning("OpenAI API key not found. AI features will be disabled.")
    
    def _make_api_call(self, prompt: str, max_tokens: int = 1000) -> str:
        """Make API call to OpenAI"""
        if not self.api_key:
            return "AI analysis disabled: API key not configured"
        
        try:
            import openai
            openai.api_key = self.api_key
            
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
            
        except ImportError:
            logger.error("OpenAI package not installed. Install with: pip install openai")
            return "AI analysis disabled: OpenAI package not installed"
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return f"AI analysis error: {str(e)}"
    
    def analyze_intent_mismatch(self, commit_message: str, plan_changes: str) -> str:
        """Analyze if commit message matches plan changes"""
        prompt = f"""
        Analyze the following Terraform plan changes against the user's stated intent.
        
        User's Commit Message (Intent):
        {commit_message}
        
        Terraform Plan Changes (Reality):
        {plan_changes}
        
        Question: Does the user's stated intent match the actual changes being made?
        If there's a significant mismatch (e.g., user says they're updating tags but plan shows database deletion),
        respond with "MISMATCH" followed by a brief explanation.
        If the intent matches the changes, respond with "MATCH".
        """
        
        return self._make_api_call(prompt, max_tokens=200)
    
    def generate_risk_summary(self, plan_changes: str, risks: List[Dict[str, Any]]) -> str:
        """Generate human-readable risk summary"""
        risks_text = "\n".join([f"- {risk.get('level', 'UNKNOWN')}: {risk.get('message', 'No message')}" 
                               for risk in risks])
        
        prompt = f"""
        Generate a concise 2-line summary of the security risks found in this Terraform plan.
        Focus on the most critical risks that should be immediately addressed.
        
        Plan changes:
        {plan_changes}
        
        Identified risks:
        {risks_text}
        
        Summary:
        """
        
        return self._make_api_call(prompt, max_tokens=200)
    
    def provide_recommendations(self, plan_changes: str, risks: List[Dict[str, Any]]) -> List[str]:
        """Provide security recommendations"""
        risks_text = "\n".join([f"- {risk.get('level', 'UNKNOWN')}: {risk.get('message', 'No message')}" 
                               for risk in risks])
        
        prompt = f"""
        Based on the Terraform plan changes and identified risks, provide 1-3 specific recommendations
        for improving the security posture of this infrastructure change.
        
        Changes:
        {plan_changes}
        
        Risks identified:
        {risks_text}
        
        Provide the recommendations as a numbered list:
        """
        
        response = self._make_api_call(prompt, max_tokens=300)
        # Split response into individual recommendations
        return [rec.strip() for rec in response.split('\n') if rec.strip() and rec.strip()[0].isdigit()]


class MockAIProvider(BaseAIProvider):
    """Mock AI provider for testing purposes"""
    
    def analyze_intent_mismatch(self, commit_message: str, plan_changes: str) -> str:
        """Mock analysis - returns MATCH for most cases"""
        if 'delete' in plan_changes.lower() and 'update' in commit_message.lower():
            return "MISMATCH: Intent suggests updates but plan shows deletions"
        return "MATCH: Intent matches observed changes"
    
    def generate_risk_summary(self, plan_changes: str, risks: List[Dict[str, Any]]) -> str:
        """Mock risk summary"""
        critical_count = len([r for r in risks if r.get('level') == 'CRITICAL'])
        security_risk_count = len([r for r in risks if r.get('level') == 'SECURITY RISK'])
        
        if critical_count > 0:
            return f"Critical security risks detected: {critical_count} critical issues requiring immediate attention."
        elif security_risk_count > 0:
            return f"Security risks identified: {security_risk_count} security concerns should be reviewed."
        else:
            return "No critical security risks detected in this plan."
    
    def provide_recommendations(self, plan_changes: str, risks: List[Dict[str, Any]]) -> List[str]:
        """Mock recommendations"""
        recommendations = []
        
        if any('SECURITY RISK' in r.get('level', '') for r in risks):
            recommendations.append("Review and restrict security group rules to prevent unauthorized access")
        
        if any('CRITICAL' in r.get('level', '') for r in risks):
            recommendations.append("Address critical security issues before proceeding with deployment")
        
        if not recommendations:
            recommendations.append("Consider implementing additional security controls for production workloads")
        
        return recommendations


class AIAnalyzer:
    """Main AI analyzer class that coordinates different providers"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get('enabled', False)
        self.provider = self._create_provider()
    
    def _create_provider(self) -> BaseAIProvider:
        """Create appropriate AI provider"""
        if not self.enabled:
            return MockAIProvider()
        
        provider_config = self.config.get('provider', {})
        provider_type = provider_config.get('type', 'mock')
        
        if provider_type == 'openai':
            return OpenAIProvider(
                api_key=provider_config.get('api_key'),
                model=provider_config.get('model', 'gpt-4')
            )
        else:
            return MockAIProvider()
    
    def analyze_intent_mismatch(self, commit_message: str, filtered_changes: List[Dict[str, Any]]) -> str:
        """Analyze intent mismatch"""
        if not self.enabled:
            logger.info("AI analysis disabled, using mock results")
        
        plan_changes = self._format_plan_changes(filtered_changes)
        return self.provider.analyze_intent_mismatch(commit_message, plan_changes)
    
    def generate_risk_summary(self, filtered_changes: List[Dict[str, Any]], risks: List[Dict[str, Any]]) -> str:
        """Generate risk summary"""
        if not self.enabled:
            logger.info("AI analysis disabled, using mock results")
        
        plan_changes = self._format_plan_changes(filtered_changes)
        return self.provider.generate_risk_summary(plan_changes, risks)
    
    def provide_recommendations(self, filtered_changes: List[Dict[str, Any]], risks: List[Dict[str, Any]]) -> List[str]:
        """Provide security recommendations"""
        if not self.enabled:
            logger.info("AI analysis disabled, using mock results")
        
        plan_changes = self._format_plan_changes(filtered_changes)
        return self.provider.provide_recommendations(plan_changes, risks)
    
    def _format_plan_changes(self, filtered_changes: List[Dict[str, Any]]) -> str:
        """Format plan changes for AI analysis"""
        formatted_changes = []
        
        for change in filtered_changes:
            address = change.get('address', 'Unknown')
            actions = change.get('change', {}).get('actions', [])
            after = change.get('change', {}).get('after', {})
            
            change_info = {
                'resource': address,
                'actions': actions,
                'after': after
            }
            formatted_changes.append(change_info)
        
        return json.dumps(formatted_changes, indent=2)