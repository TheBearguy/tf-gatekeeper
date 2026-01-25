# Terraform Gatekeeper

> **"Terraform enforces desired state; tf-gatekeeper judges whether enforcing it is safe."**

`tf-gatekeeper` is a comprehensive security analysis tool designed to sit between `terraform plan` and `terraform apply`. It bridges the gap between **syntactic correctness** (Is the code valid?) and **operational safety** (Is it safe to run this right now?).

## The Problem
Infrastructure-as-Code (IaC) is a blind executor. Standard CI/CD pipelines will happily execute a `terraform apply` that:
1.  **Destroys production databases** due to a simple resource rename.
2.  **Reverts a manual emergency hotfix** (Drift) made by an on-call engineer.
3.  **Opens Security Groups** to `0.0.0.0/0` accidentally.
4.  **Deploys high-risk changes** during a "Friday Afternoon" or a Code Freeze.

## The Solution
`tf-gatekeeper` analyzes the machine-readable JSON output of a Terraform plan and uses a combination of **Heuristics (Regex/Logic)** and **AI (LLMs)** to provide a human-readable risk assessment.

## Key Features
* **Drift Detection:** Ingests `refresh-only` plans to detect if Terraform is about to overwrite a manual cloud change.
* **Blast Radius Analysis:** Scrutinizes "Crown Jewel" services (RDS, S3, Route53, IAM) for destructive actions.
* **The "When" Logic:** Blocks or warns on deployments during sensitive time windows (e.g., Friday Deploys).
* **AI Insights:** Uses LLMs to explain *why* a plan is risky, catching "Hidden Deletes" (Force-New replacements) that standard linters miss.
* **CI/CD Native:** Returns non-zero exit codes to automatically fail builds in GitHub Actions, GitLab, or Jenkins.

## Technical Architecture
1.  **Parser:** Ingests `terraform show -json` output.
2.  **Filter:** Strips noise (tag-only updates) and isolates high-impact changes (Deletes/Replaces).
3.  **Context Engine:** Injects external context (Current time, PagerDuty status, resource sensitivity).
4.  **Analyzer:**
    * **Level 1 (Regex):** Flags known bad patterns (e.g., `0.0.0.0/0`).
    * **Level 2 (Semantic):** LLM analyzes the mismatch between Git Commit intent and the resulting Terraform Plan.
5.  **Output:** Generates a Risk Report and a GO/NO-GO decision.

---

## Getting Started

### Prerequisites
- Python 3.9+
- Terraform 1.0+

### Quick Start
1. **Generate the plan JSON:**
   ```bash
   terraform plan -out=tfplan
   terraform show -json tfplan > plan.json
   ```

2. **Run tf-gatekeeper:**
   ```bash
   python gatekeeper.py --plan plan.json
   ```

3. **Check the results:**
   ```bash
   # If critical risks are found, the script exits with code 1
   # If no critical risks, it exits with code 0
   ```

## Phase-by-Phase Implementation

### Phase 1: Foundation (JSON Ingestion)
- ✅ **Mock Environment**: Created dummy Terraform project with S3 bucket and RDS instance
- ✅ **Data Extraction**: Automated shell script for JSON plan generation
- ✅ **Basic Parser**: Python script that loads plan.json and iterates through resource_changes
- ✅ **Change Filter**: Filters resources with delete/update actions

### Phase 2: Heuristic Guardrails
- ✅ **Protected Resources**: Configurable protection for critical infrastructure
- ✅ **Destruction Logic**: Flags protected resource deletions as CRITICAL
- ✅ **Security Logic**: Detects unrestricted security group configurations
- ✅ **Exit Codes**: Proper pipeline integration with non-zero exits

### Phase 3: Context Engine
- ✅ **Time-Based Rules**: Upgrades warnings to CRITICAL on weekends/Friday afternoons
- ✅ **Drift Comparison**: Detects conflicts between manual AWS changes and Terraform plans

### Phase 4: AI Integration
- ✅ **Intent Detection**: Compares Git commit messages with actual changes
- ✅ **Mismatch Detection**: Identifies intent vs reality discrepancies
- ✅ **Smart Summaries**: AI-generated risk summaries and recommendations

## Configuration

Create a `config.yaml` file:

```yaml
protected_resources:
  aws_db_instance: true
  aws_kms_key: true
  aws_s3_bucket: true
  aws_security_group: true
  aws_vpc: true

ai_integration:
  enabled: true
  provider:
    type: openai
    model: gpt-4
    api_key: "${OPENAI_API_KEY}"

time_based_rules:
  upgrade_friday_afternoon: true
  upgrade_weekends: true

drift_detection:
  enabled: true
  tolerance_level: "strict"
```

## Usage Examples

### Basic Analysis
```bash
# Generate and analyze plan
make plan
python gatekeeper.py --plan plan.json
```

### With Commit Message (AI Analysis)
```bash
python gatekeeper.py --plan plan.json --commit-message "Update database tags"
```

### Drift Detection
```bash
# Generate drift comparison
terraform plan -refresh-only -out=drift.tfplan
terraform show -json drift.tfplan > drift.json

# Analyze with drift comparison
python gatekeeper.py --plan plan.json --drift drift.json
```

### Automated Workflow
```bash
# Extract and analyze in one command
./extract_plan.sh

# Using Makefile
make analyze
```

## Risk Levels

- **🔴 CRITICAL**: Protected resource deletion, critical security violations
- **🟡 SECURITY RISK**: Unrestricted access, dangerous configurations  
- **🔵 WARNING**: Best practice violations, non-critical issues

## CI/CD Integration

### GitHub Actions
```yaml
- name: Terraform Plan
  run: |
    terraform plan -out=tfplan
    terraform show -json tfplan > plan.json

- name: Security Analysis
  run: |
    python gatekeeper.py --plan plan.json --commit-message "${{ github.event.head_commit.message }}"
```

### GitLab CI
```yaml
terraform_plan:
  script:
    - terraform plan -out=tfplan
    - terraform show -json tfplan > plan.json
    - python gatekeeper.py --plan plan.json --commit-message "$CI_COMMIT_MESSAGE"
```

## AI Integration Setup

### OpenAI Configuration
```bash
export OPENAI_API_KEY="your-api-key-here"
```

### Mock AI Provider
The tool includes a mock AI provider that works without API keys for testing:

```bash
# Works without API key for testing
python gatekeeper.py --plan plan.json --commit-message "Test changes"
```

## File Structure

```
tf-gatekeeper/
├── main.tf              # Mock Terraform environment
├── config.yaml          # Configuration file  
├── gatekeeper.py        # Main analysis script
├── ai_analyzer.py       # AI integration module
├── extract_plan.sh      # Automated extraction script
├── Makefile            # Build automation
├── README.md           # This file
└── modules/
    └── vpc/            # VPC module for testing
```

## Testing

```bash
# Clean environment
make clean

# Generate test plan
make plan

# Run analysis
make analyze

# Test with mock AI
python gatekeeper.py --plan plan.json --commit-message "Test AI analysis"
```

## Examples

### Protected Resource Detection
```
🔴 [CRITICAL] aws_db_instance.prod-db: Protected resource deletion detected
```

### Security Risk Detection  
```
🟡 [SECURITY RISK] aws_security_group.unrestricted-sg: Security group allows unrestricted access (0.0.0.0/0, all ports)
```

### Intent Mismatch Detection
```
🤖 Intent Analysis: MISMATCH: Intent suggests updates but plan shows deletions
   ⚠️  WARNING: Intent mismatch detected! Review changes carefully.
```

### AI Summary
```
🤖 AI Analysis: Critical security risks detected: 2 critical issues requiring immediate attention.
💡 AI Recommendations:
   1. Review and restrict security group rules to prevent unauthorized access
   2. Address critical security issues before proceeding with deployment
```

## Contributing

1. Fork the repository
2. Create a feature branch  
3. Test your changes with `make test`
4. Submit a pull request

## License

MIT License - see LICENSE file for details.