# Terraform Gatekeeper (tf-gate)

> A multi-layered defense system that gates `terraform apply` behind contextual safety checks, semantic validation, and policy-as-code guardrails.

**Status:** POC (Proof of Concept)  
**Interface:** CLI-only  
**License:** MIT

---

## What We Are Building

`tf-gate` is a CLI tool that intercepts `terraform apply` and forces it through a 4-phase validation pipeline before execution. It transforms Terraform from a "shoot yourself in the foot" tool into a "measure twice, cut once" workflow.

Unlike simple policy checkers (Checkov, tfsec), tf-gate understands **context** (time, blast radius, drift) and **intent** (commit message vs. actual changes).

---

## Why This Exists

Terraform's `apply` command is binary: it either succeeds or fails catastrophically. There is no middle ground for:
- Accidental deletions of stateful resources (RDS, S3, KMS)
- Friday-night deployments that conflict with manual console changes
- Semantic mismatches ("I said I was updating tags, but I'm actually deleting the database")
- Cost explosions ($10 → $10,000/month due to instance type typos)

**The cost of a mistake is asymmetric.** One wrong apply can destroy production data. tf-gate introduces **asymmetric friction**—making dangerous operations harder than safe ones.

---

## How It Works (The Architecture)

tf-gate operates as a **wrapper** around your existing Terraform workflow:

```bash
# Instead of:
terraform apply

# You run:
tf-gate apply  # Intercepts, validates, then delegates to terraform
```

The system uses a **4-Phase Defense Pipeline**:

### Phase 1: Ingestion & Blast Radius Calculation
- **Streaming Parser**: Uses `ijson` to handle 50MB+ plan files without memory crashes
- **Resource Extraction**: Captures `resource_changes`, `output_changes`, `terraform_version`
- **Blast Radius Calculation**: 
  - 🟢 **Green**: 0-5 resources, cosmetic changes only
  - 🟡 **Yellow**: 5-20 resources, compute/network changes
  - 🔴 **Red**: 20+ resources, deletions, IAM, or state migrations

*Enhancement*: Dynamically adjusts strictness based on blast radius (Red = mandatory AI review).

### Phase 2: Policy Validation (OPA Integration)
**No YAML. No Regex.** Policies are written in **Rego** (Open Policy Agent).

```rego
# policies/protected_resources.rego
package terraform.analysis

import future.keywords.if
import future.keywords.in

deny[msg] if {
    resource := input.resource_changes[_]
    resource.type in ["aws_db_instance", "aws_kms_key", "aws_s3_bucket"]
    resource.change.actions[_] in ["delete", "replace"]
    not input.emergency_override
    
    msg := sprintf("CRITICAL: Protected resource %s scheduled for deletion", [resource.address])
}

deny[msg] if {
    resource := input.resource_changes[_]
    resource.type == "aws_security_group_rule"
    resource.change.after.from_port == 0
    resource.change.after.cidr_blocks[_] == "0.0.0.0/0"
    
    msg := sprintf("SECURITY: Resource %s opens 0.0.0.0/0:0 (all ports)", [resource.address])
}
```

**OPA Execution**: tf-gate bundles OPA as a library (via `opa-python`) or calls the binary:
```python
# Simplified core logic
def phase_2_validate(plan_json, blast_radius):
    # Compile Rego policies
    policy = opa.compile("./policies/")
    
    # Input includes plan + metadata
    input_data = {
        "resource_changes": plan_json["resource_changes"],
        "blast_radius": blast_radius,
        "timestamp": datetime.now().isoformat(),
        "git_commit": get_git_head()
    }
    
    result = policy.eval(input_data)
    return result.deny  # List of violations
```

*Key Advantage*: Security teams write Rego. You don't maintain a Python policy engine.

### Phase 3: Context Engine
**Temporal Safety**:
```python
def get_risk_level(base_risk):
    now = datetime.now()
    if now.weekday() >= 5 or (now.weekday() == 4 and now.hour >= 15):
        # Friday after 3 PM or weekend
        return min(base_risk + 1, 3)  # Escalate to CRITICAL
    return base_risk
```

**Drift Detection**:
1. Runs `terraform plan -refresh-only -out=drift.tfplan`
2. Parses drift.json vs plan.json
3. **Conflict Detection**: If a resource was manually modified in AWS (drift) AND your plan modifies it → **DRIFT CONFLICT**

**Provider Version Check**:
```rego
# policies/version_lock.rego
warn[msg] if {
    input.terraform_version != input.last_applied_version
    msg := sprintf("Version drift: Plan uses %s, state was last touched by %s", 
                   [input.terraform_version, input.last_applied_version])
}
```

### Phase 4: Intent Validation (The "Semantic Layer")
**The Problem**: Commit message says "Update RDS tags", but plan shows RDS deletion.

**Implementation**:
```python
def phase_4_intent_check(commit_msg, plan_summary):
    prompt = f"""
    Git Commit Message: "{commit_msg}"
    Terraform Changes: {plan_summary}
    
    Analyze: Does the commit message semantically match the infrastructure changes?
    If they mismatch, explain the risk in 2 sentences.
    If they match, respond with "ALIGNMENT_CONFIRMED".
    """
    
    # Uses local LLM (Ollama/Llama3) for privacy, or OpenAI if configured
    response = llm.generate(prompt)
    
    if "ALIGNMENT_CONFIRMED" not in response:
        return {
            "status": "MISMATCH",
            "explanation": response,
            "action_required": "Human confirmation needed"
        }
```

*Alternative for POC*: Simple keyword matching (you can swap in LLM later):
```python
# Fallback if LLM unavailable
def simple_intent_check(commit, changes):
    if "tag" in commit.lower() and any("delete" in c for c in changes):
        return False  # Likely mismatch
```

---

## The "Shadow Mode" & Break Glass

### Shadow Mode (Testing)
Run validation without blocking:
```bash
tf-gate apply --shadow-mode
# Logs: "Would have blocked: aws_db_instance.primary deletion"
# But applies anyway (for tuning thresholds)
```

### Break Glass Protocol
When production is on fire:
```bash
tf-gate apply --break-glass="INCIDENT-2024-001"
```
- ✅ Proceeds immediately
- 🚨 Pages on-call engineer (PagerDuty integration hook)
- 📹 Records terminal session (asciinema)
- 🎫 Creates mandatory post-mortem ticket (GitHub/Jira API)

---

## Installation & Usage

### Prerequisites
- Python 3.9+
- Terraform >= 1.0
- OPA (Open Policy Agent) binary in `$PATH`
- (Optional) Infracost for cost estimation

### Install
```bash
pip install tf-gate
# Or from source
git clone https://github.com/yourorg/tf-gate
cd tf-gate && pip install -e .
```

### Quick Start

**1. Initialize policies:**
```bash
tf-gate init
# Creates ./policies/ directory with default Rego rules
```

**2. Replace `terraform apply`:**
```bash
# In your CI/CD or locally
tf-gate plan -out=tfplan  # Wrapper around terraform plan
tf-gate apply tfplan      # Runs 4-phase validation before actual apply
```

**3. Configuration (tf-gate.yaml):**
```yaml
opa:
  policy_dir: "./policies"
  strict_mode: true  # Fail on any deny rule

phases:
  phase_3_time_gating:
    friday_cutoff_hour: 15
    weekend_blocking: true
  
  phase_4_intent:
    provider: "ollama"  # or "openai"
    model: "llama3"
    enabled: true

blast_radius:
  thresholds:
    green: 5
    yellow: 20
    red: 50
  
notifications:
  slack_webhook: ${SLACK_WEBHOOK_URL}  # Posts critical blocks
```

---

## Development Architecture (POC Scope)

```
tf-gate/
├── cli.py                 # Click/Typer CLI interface
├── phases/
│   ├── __init__.py
│   ├── phase1_ingest.py   # ijson streaming parser
│   ├── phase2_opa.py      # OPA integration
│   ├── phase3_context.py  # Time drift, refresh-only comparison
│   └── phase4_intent.py   # LLM/semantic validation
├── policies/              # Rego files (default + examples)
│   ├── protected.rego
│   ├── security.rego
│   └── cost.rego
└── utils/
    ├── blast_radius.py    # Impact calculation logic
    └── git.py             # Commit message extraction
```

### Key Technical Decisions

1. **Streaming JSON**: Uses `ijson` to parse `plan.json` iteratively. Prevents CI OOM on large monorepos.
   
2. **OPA-over-YAML**: Policies are data, not code. Changes to rules don't require redeploying tf-gate.

3. **Local LLM Default**: Ships with Ollama integration so your Terraform plans (which contain sensitive resource IDs) never leave your VPC.

4. **Exit Codes**:
   - `0`: Success / No critical issues
   - `1`: Critical violation blocked (OPA deny rule)
   - `2`: Drift conflict detected
   - `3`: Intent mismatch (Phase 4 failure)
   - `42`: Break glass used (auditing purposes)

---

## Roadmap to Production

**Current (POC)**:
- [x] CLI wrapper
- [x] OPA policy engine
- [x] Basic drift detection
- [x] Local LLM intent check

**Next**:
- [ ] Remote state locking awareness
- [ ] Infracost integration for Phase 2
- [ ] GitHub PR comments integration
- [ ] Cosign attestation generation (Phase 7 compliance)

---

## Contributing

This is a POC. We optimize for ** correctness over performance**. If you can break the safety guarantees, that's a bug.

**Development Setup:**
```bash
git clone <repo>
cd tf-gate
python -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
pytest tests/  # Currently unit tests for parser + OPA client
```

---

This README provides the architectural blueprint while keeping it implementable as a CLI POC. The OPA integration is the centerpiece—replacing fragile YAML logic with composable, testable Rego policies that security teams can own independently of the Python codebase.
