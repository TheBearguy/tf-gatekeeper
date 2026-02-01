"""CLI entry point for tf-gate."""

import sys
from pathlib import Path

def main() -> int:
    """Main entry point for the tf-gate CLI.
    
    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    print("tf-gate - Terraform Gatekeeper")
    print("A multi-layered defense system for terraform apply")
    print()
    print("Phase 0: Project Infrastructure - Complete")
    print("- Project structure initialized")
    print("- Dependencies configured")
    print("- CI/CD pipeline configured")
    print("- OPA integration ready")
    print()
    print("Next: Implement Phase 1 - CLI Framework & Core Interface")
    return 0


if __name__ == "__main__":
    sys.exit(main())
