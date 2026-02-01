"""OPA (Open Policy Agent) integration utilities for tf-gate.

This module provides functionality to:
- Detect OPA binary location
- Compile and evaluate Rego policies
- Download OPA if not present (optional)
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class OPANotFoundError(Exception):
    """Raised when OPA binary is not found."""
    pass


class OPAPolicyError(Exception):
    """Raised when there's an error compiling or evaluating OPA policies."""
    pass


class OPAClient:
    """Client for interacting with OPA (Open Policy Agent).
    
    This client can work with either a system-installed OPA binary or
    the opa-python library if available.
    """
    
    def __init__(self, binary_path: Optional[str] = None):
        """Initialize OPA client.
        
        Args:
            binary_path: Path to OPA binary. If None, will auto-detect.
        
        Raises:
            OPANotFoundError: If OPA binary cannot be found.
        """
        if binary_path:
            self.binary_path = binary_path
        else:
            found_path = self._find_opa_binary()
            if not found_path:
                raise OPANotFoundError(
                    "OPA binary not found. Please install OPA: "
                    "https://www.openpolicyagent.org/docs/latest/#running-opa"
                )
            self.binary_path = found_path
    
    def _find_opa_binary(self) -> Optional[str]:
        """Find OPA binary in system PATH.
        
        Returns:
            Path to OPA binary or None if not found.
        """
        # Check common locations
        locations = [
            "opa",
            "/usr/local/bin/opa",
            "/usr/bin/opa",
            "/opt/opa/opa",
            os.path.expanduser("~/.local/bin/opa"),
            os.path.expanduser("~/bin/opa"),
        ]
        
        for location in locations:
            try:
                result = subprocess.run(
                    [location, "version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    return location
            except (subprocess.SubprocessError, FileNotFoundError):
                continue
        
        return None
    
    def check_version(self) -> str:
        """Get OPA version.
        
        Returns:
            OPA version string.
        
        Raises:
            OPAPolicyError: If version check fails.
        """
        try:
            result = subprocess.run(
                [self.binary_path, "version"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise OPAPolicyError(f"Failed to check OPA version: {e.stderr}")
    
    def compile_policies(self, policy_dir: Union[str, Path]) -> bool:
        """Compile Rego policies to check for syntax errors.
        
        Args:
            policy_dir: Directory containing .rego policy files.
        
        Returns:
            True if compilation succeeds.
        
        Raises:
            OPAPolicyError: If compilation fails.
        """
        policy_path = Path(policy_dir)
        
        if not policy_path.exists():
            raise OPAPolicyError(f"Policy directory not found: {policy_dir}")
        
        rego_files = list(policy_path.glob("*.rego"))
        if not rego_files:
            raise OPAPolicyError(f"No .rego files found in {policy_dir}")
        
        try:
            # Build command to compile policies
            cmd = [self.binary_path, "build", str(policy_path)]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            if result.returncode != 0:
                raise OPAPolicyError(f"Policy compilation failed: {result.stderr}")
            
            return True
            
        except subprocess.TimeoutExpired:
            raise OPAPolicyError("Policy compilation timed out")
        except subprocess.SubprocessError as e:
            raise OPAPolicyError(f"Failed to compile policies: {e}")
    
    def evaluate(
        self,
        policy_dir: Union[str, Path],
        input_data: Dict[str, Any],
        query: str = "data.terraform.analysis",
    ) -> Dict[str, Any]:
        """Evaluate policies against input data.
        
        Args:
            policy_dir: Directory containing .rego policy files.
            input_data: Input data to evaluate (Terraform plan + metadata).
            query: Rego query path to evaluate.
        
        Returns:
            Dictionary containing evaluation results (deny, warn, etc.).
        
        Raises:
            OPAPolicyError: If evaluation fails.
        """
        policy_path = Path(policy_dir)
        
        if not policy_path.exists():
            raise OPAPolicyError(f"Policy directory not found: {policy_dir}")
        
        # Create temporary input file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(input_data, f)
            input_file = f.name
        
        try:
            # Run OPA evaluation
            cmd = [
                self.binary_path,
                "eval",
                "--data", str(policy_path),
                "--input", input_file,
                query,
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            if result.returncode != 0:
                raise OPAPolicyError(f"Policy evaluation failed: {result.stderr}")
            
            # Parse output
            try:
                output = json.loads(result.stdout)
                return self._parse_eval_output(output)
            except json.JSONDecodeError as e:
                raise OPAPolicyError(f"Failed to parse OPA output: {e}")
                
        except subprocess.TimeoutExpired:
            raise OPAPolicyError("Policy evaluation timed out")
        except subprocess.SubprocessError as e:
            raise OPAPolicyError(f"Failed to evaluate policies: {e}")
        finally:
            # Cleanup temporary file
            try:
                os.unlink(input_file)
            except OSError:
                pass
    
    def _parse_eval_output(self, output: Dict[str, Any]) -> Dict[str, Any]:
        """Parse OPA eval output into structured format.
        
        Args:
            output: Raw OPA eval JSON output.
        
        Returns:
            Parsed results with deny, warn, and other rule outputs.
        """
        results = {
            "deny": [],
            "warn": [],
            "info": [],
        }
        
        # Extract results from OPA output
        if "result" in output and len(output["result"]) > 0:
            result = output["result"][0]
            
            # Extract deny rules
            if "deny" in result.get("expressions", [{}])[0].get("value", {}):
                deny_msgs = result["expressions"][0]["value"]["deny"]
                if isinstance(deny_msgs, list):
                    results["deny"] = deny_msgs
            
            # Extract warn rules
            if "warn" in result.get("expressions", [{}])[0].get("value", {}):
                warn_msgs = result["expressions"][0]["value"]["warn"]
                if isinstance(warn_msgs, list):
                    results["warn"] = warn_msgs
            
            # Extract info rules
            if "info" in result.get("expressions", [{}])[0].get("value", {}):
                info_msgs = result["expressions"][0]["value"]["info"]
                if isinstance(info_msgs, list):
                    results["info"] = info_msgs
        
        return results


def get_default_policy_dir() -> Path:
    """Get the default policy directory path.
    
    Returns:
        Path to default policies directory.
    """
    # Look for policies relative to package
    package_dir = Path(__file__).parent.parent
    policies_dir = package_dir / "policies"
    
    if policies_dir.exists():
        return policies_dir
    
    # Fallback to current working directory
    return Path.cwd() / "policies"
