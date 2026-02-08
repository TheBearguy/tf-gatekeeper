# Running tf-gate Locally with LMStudio

This guide will walk you through running the Terraform Gatekeeper (tf-gate) project locally with LMStudio as your LLM provider for intent validation.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [LMStudio Setup](#lmstudio-setup)
4. [Configuration](#configuration)
5. [Running tf-gate](#running-tf-gate)
6. [Example Workflow](#example-workflow)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before starting, ensure you have the following installed:

### 1. Python 3.9+
```bash
python3 --version
# Should show 3.9 or higher
```

### 2. Terraform
```bash
terraform --version
# Should show 1.0 or higher
```

### 3. OPA (Open Policy Agent)
```bash
# Download from https://www.openpolicyagent.org/docs/latest/#running-opa
# Or use Homebrew on macOS:
brew install opa

# Verify installation
opa version
```

### 4. LMStudio
- Download from: https://lmstudio.ai/
- Install and launch LMStudio

---

## Installation

### Step 1: Clone/Navigate to the Project
```bash
cd /home/thebearguy/batcave/tf-gatekeeper
```

### Step 2: Create Virtual Environment
```bash
# Create virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate  # On Linux/Mac
# OR
.venv\Scripts\activate  # On Windows
```

### Step 3: Install Dependencies
```bash
# Install main dependencies
pip install -r requirements.txt

# Install development dependencies (optional, for testing)
pip install -r requirements-dev.txt

# Install in editable mode
pip install -e .
```

### Step 4: Verify Installation
```bash
# Check if tf-gate command is available
tf-gate --help

# Check OPA integration
tf-gate version
```

---

## LMStudio Setup

### Step 1: Download the Model
1. Open LMStudio
2. Go to the "Discover" tab
3. Search for: `qwen2.5-coder-7b-instruct`
4. Download the model (approximately 4.5GB)

### Step 2: Configure LMStudio
1. Go to "Local Server" tab in LMStudio
2. Select the model: `qwen2.5-coder-7b-instruct`
3. Set these parameters:
   - **Port**: `1234`
   - **Temperature**: `0.7`
   - **Max Tokens**: `-1` (unlimited)
   - **Context Length**: `4096` or higher

4. Click "Start Server"
5. Verify it's running: `http://localhost:1234` should be accessible

### Step 3: Test LMStudio API
```bash
# Test the API endpoint
curl http://localhost:1234/v1/models

# You should see your model listed
```

---

## Configuration

### Step 1: Initialize tf-gate
```bash
# In your project directory (or tf-gate directory)
tf-gate init
```

This creates:
- `tf-gate.yaml` - Configuration file
- `policies/` - Directory with Rego policy files

### Step 2: Configure tf-gate for LMStudio

Edit the generated `tf-gate.yaml` file:

```yaml
# tf-gate Configuration
opa:
  policy_dir: "./policies"
  strict_mode: true

phases:
  phase_3_time_gating:
    friday_cutoff_hour: 15
    weekend_blocking: true

  phase_4_intent:
    provider: "lmstudio"  # Using LMStudio for intent validation
    model: "qwen2.5-coder-7b-instruct"
    enabled: true  # Enable intent validation

blast_radius:
  thresholds:
    green: 5
    yellow: 20
    red: 50

notifications:
  slack_webhook: null
  pagerduty_key: null
```

### Step 3: Verify Policies
```bash
# Check that all policies compile correctly
tf-gate check-policies

# Should output: ✅ All policies compiled successfully
```

---

## Running tf-gate

### Method 1: Using tf-gate plan and validate (Recommended)

```bash
# Step 1: Navigate to your Terraform project
cd /path/to/your/terraform/project

# Step 2: Initialize tf-gate in your project directory
tf-gate init

# Step 3: Edit tf-gate.yaml to enable LMStudio (as shown above)

# Step 4: Create Terraform plan with JSON output
tf-gate plan

# This will create:
# - tfplan (binary plan file)
# - tfplan.json (JSON version for validation)

# Step 5: Run validation
# Make sure LMStudio server is running first!
tf-gate validate

# Step 6: If validation passes, apply
tf-gate apply
```

### Method 2: Using existing Terraform plan

```bash
# If you already have a Terraform plan
terraform plan -out=tfplan
terraform show -json tfplan > tfplan.json

# Then validate
tf-gate validate tfplan.json
```

### Method 3: Direct validation without apply

```bash
# Just run validation without applying
tf-gate validate

# With custom policy directory
tf-gate validate --policy-dir ./custom-policies

# With verbose output
tf-gate validate --verbose
```

---

## Example Workflow

Here's a complete example workflow:

```bash
# 1. Navigate to project
cd ~/my-terraform-project

# 2. Initialize tf-gate (first time only)
tf-gate init

# 3. Configure for LMStudio
# Edit tf-gate.yaml and set:
#   phases.phase_4_intent.provider: "lmstudio"
#   phases.phase_4_intent.enabled: true

# 4. Start LMStudio server
# Open LMStudio app, load qwen2.5-coder-7b-instruct model
# Click "Start Server" on Local Server tab

# 5. Create your Terraform changes
git add .
git commit -m "Update RDS instance type and add tags"

# 6. Generate plan
tf-gate plan

# 7. Validate (4-phase pipeline)
tf-gate validate

# Output will show:
# Phase 1: Blast radius calculation
# Phase 2: Policy validation (OPA)
# Phase 3: Context analysis (time-based risks, drift detection)
# Phase 4: Intent validation (LLM analysis of commit message vs changes)

# 8. If validation passes, apply
tf-gate apply
```

---

## Understanding the Output

### Phase 1: Ingestion & Blast Radius
```
🟡 Blast Radius Level: YELLOW
   Total Resources: 12
   Create: 2, Update: 8, Delete: 0, Replace: 2
   ⚠️  Critical resources affected:
      - aws_db_instance.main
```

### Phase 2: Policy Validation
```
❌ 1 policy violations (deny)
   - CRITICAL: Protected resource aws_db_instance.main scheduled for replacement
⚠️  2 warnings
   - WARNING: Large blast radius detected
```

### Phase 3: Context Analysis
```
🟢 Temporal Risk: LOW
✅ No drift detected
```

### Phase 4: Intent Validation (LLM via LMStudio)
```
✅ Intent aligned with changes
# OR
⚠️  Intent mismatch detected
   The commit mentions only updating tags, but the plan shows
   replacing the RDS instance. Please verify this is intentional.
```

---

## Special Modes

### Break Glass Mode (Emergency Bypass)
```bash
# When production is on fire and you need to bypass validation
tf-gate apply --break-glass="INCIDENT-2024-001"

# Returns exit code 42 for audit purposes
```

### Shadow Mode (Testing)
```bash
# Run validation without blocking - useful for testing
# Will show what WOULD block but allows apply anyway
tf-gate validate --shadow-mode
```

---

## Troubleshooting

### Issue: "OPA binary not found"
**Solution:**
```bash
# Install OPA
# macOS:
brew install opa

# Linux:
curl -L -o opa https://openpolicyagent.org/downloads/v0.60.0/opa_linux_amd64
chmod +x opa
sudo mv opa /usr/local/bin/

# Verify
opa version
```

### Issue: "LLM provider 'lmstudio' not implemented"
**Solution:**
- Make sure you're using the latest code with LMStudio support
- Check that `tf-gate.yaml` has correct provider name: `lmstudio`

### Issue: "Cannot connect to LMStudio"
**Solution:**
```bash
# Check if LMStudio is running
curl http://localhost:1234/v1/models

# If no response:
# 1. Open LMStudio application
# 2. Go to "Local Server" tab
# 3. Select qwen2.5-coder-7b-instruct model
# 4. Click "Start Server"
# 5. Verify port is 1234
```

### Issue: "ollama package not installed" (when using LMStudio)
**Solution:**
```bash
# Install OpenAI package (LMStudio uses OpenAI-compatible API)
pip install openai
```

### Issue: "Policy compilation failed"
**Solution:**
```bash
# Check syntax of your .rego files
tf-gate check-policies

# Or check individual files
opa fmt policies/*.rego
opa test policies/*.rego
```

### Issue: "Phase 4: No git commit message found"
**Solution:**
```bash
# Make sure you're in a git repository
git status

# And have at least one commit
git log --oneline -1
```

### Issue: Validation takes too long with LLM
**Solution:**
- The first call to LMStudio may take 10-30 seconds as the model loads
- Subsequent calls are faster
- Consider disabling intent validation for quick iterations:
  ```yaml
  phase_4_intent:
    enabled: false
  ```

---

## Exit Codes

- `0` - Success / Validation passed
- `1` - Validation failed (policy violations or critical issues)
- `2` - Drift conflict detected
- `3` - Intent mismatch detected
- `42` - Break glass used (emergency bypass)

---

## Configuration Reference

### tf-gate.yaml Full Example

```yaml
# tf-gate Configuration
opa:
  policy_dir: "./policies"
  strict_mode: true

phases:
  phase_3_time_gating:
    friday_cutoff_hour: 15
    weekend_blocking: true

  phase_4_intent:
    provider: "lmstudio"
    model: "qwen2.5-coder-7b-instruct"
    enabled: true

blast_radius:
  thresholds:
    green: 5
    yellow: 20
    red: 50

notifications:
  slack_webhook: null
  pagerduty_key: null
```

---

## Quick Reference Commands

```bash
# Initialize
tf-gate init

# Plan and generate JSON
tf-gate plan

# Validate only
tf-gate validate

# Validate with custom config
tf-gate validate --config ./custom-config.yaml

# Validate with custom policy dir
tf-gate validate --policy-dir ./policies

# Apply (runs validation first)
tf-gate apply

# Apply with auto-approve
tf-gate apply --auto-approve

# Check policies compile
tf-gate check-policies

# Show version
tf-gate version

# Help
tf-gate --help
tf-gate validate --help
```

---

## Next Steps

1. ✅ Verify all prerequisites are installed
2. ✅ Set up LMStudio with qwen2.5-coder-7b-instruct model
3. ✅ Initialize tf-gate in your project
4. ✅ Configure tf-gate.yaml for LMStudio
5. ✅ Start LMStudio server
6. ✅ Run `tf-gate plan` then `tf-gate validate`
7. ✅ Review the 4-phase validation output
8. ✅ Apply changes with `tf-gate apply`

For issues or questions, check the main README.md or DEVELOPMENT.md files in the project root.
