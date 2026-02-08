# Test Plans for tf-gate

This directory contains test Terraform plan files to validate the tf-gate 4-phase pipeline.

## Test Files

### 🟢 tfplan_green.json - Low Risk
**Scenario**: Creating 3 new web servers in staging environment  
**Expected Blast Radius**: GREEN  
**Expected Behavior**: ✅ Should pass all validations

**Resources**:
- 1 security group (create)
- 2 EC2 instances (create)

**Expected Results**:
- Phase 1: 🟢 Green blast radius (3 resources, 0 destructive)
- Phase 2: No policy violations
- Phase 3: Context analysis (depends on current time)
- Phase 4: Intent aligned (creating web servers matches commit)

### 🟡 tfplan_yellow.json - Medium Risk
**Scenario**: Scaling up worker pool and replacing load balancer  
**Expected Blast Radius**: YELLOW  
**Expected Behavior**: ⚠️ May have warnings but likely allowed

**Resources**:
- 1 security group (create)
- 7 EC2 instances (create)
- 1 load balancer (replace)

**Expected Results**:
- Phase 1: 🟡 Yellow blast radius (9 resources, 1 replacement)
- Phase 2: Possible warnings
- Phase 3: Context analysis
- Phase 4: Intent check (replacing LB vs "scale up" message)

### 🔴 tfplan_red.json - High Risk
**Scenario**: Major infrastructure overhaul with deletions and security issues  
**Expected Blast Radius**: RED  
**Expected Behavior**: 🚫 Should be blocked

**Resources**:
- 1 production database (delete)
- 1 KMS key (delete)
- 1 S3 bucket (replace)
- 1 DynamoDB table (delete)
- 1 RDS cluster (replace)
- 12 EC2 instances (delete)
- 2 new EC2 instances (create)
- 1 dangerous security rule (0.0.0.0/0:0-65535)
- 3 NAT gateways (create)

**Expected Results**:
- Phase 1: 🔴 Red blast radius (23 resources, critical deletions)
- Phase 2: Multiple deny violations:
  - Protected resource deletions (DB, KMS, S3, DynamoDB)
  - Security violation (open all ports to world)
  - Cost warnings (3 NAT gateways)
- Phase 3: Context analysis
- Phase 4: Intent mismatch (commit says "update" but plan deletes everything)

## Running the Tests

### Test Individual Plans

```bash
# From the project root
cd /home/thebearguy/batcave/tf-gatekeeper
source .venv/bin/activate

# Test GREEN plan
tf-gate validate test_plans/tfplan_green.json

# Test YELLOW plan
tf-gate validate test_plans/tfplan_yellow.json

# Test RED plan
tf-gate validate test_plans/tfplan_red.json
```

### Run Automated Test Suite

```bash
# Run the test script
cd test_plans
python test_runner.py
```

This will run all three plans through all 4 phases and generate a detailed report.

### Test with LMStudio (Intent Validation)

1. Start LMStudio with qwen2.5-coder-7b-instruct model
2. Update tf-gate.yaml to enable LMStudio
3. Run validation:

```bash
tf-gate validate test_plans/tfplan_red.json
```

## Expected Exit Codes

- **GREEN plan**: Exit code 0 (success)
- **YELLOW plan**: Exit code 0 (success with warnings)
- **RED plan**: Exit code 1 (blocked due to violations)

## Plan JSON Structure

Each tfplan.json file contains:

```json
{
  "format_version": "1.2",
  "terraform_version": "1.7.0",
  "timestamp": "2024-02-08T10:00:00Z",
  "resource_changes": [
    {
      "address": "aws_instance.example",
      "type": "aws_instance",
      "change": {
        "actions": ["create"],
        "before": null,
        "after": { ... }
      }
    }
  ]
}
```

**Action Types**:
- `["create"]` - New resource
- `["delete"]` - Remove resource
- `["update"]` - Modify existing resource
- `["create", "delete"]` - Replace resource

## Customizing Tests

You can modify these plans to test specific scenarios:

### Add a Security Violation
```json
{
  "address": "aws_security_group_rule.ssh_open",
  "type": "aws_security_group_rule",
  "change": {
    "actions": ["create"],
    "after": {
      "cidr_blocks": ["0.0.0.0/0"],
      "from_port": 22,
      "to_port": 22
    }
  }
}
```

### Add an Expensive Instance
```json
{
  "address": "aws_instance.gpu",
  "type": "aws_instance",
  "change": {
    "actions": ["create"],
    "after": {
      "instance_type": "p3.16xlarge"
    }
  }
}
```

### Add a Protected Resource Deletion
```json
{
  "address": "aws_db_instance.production",
  "type": "aws_db_instance",
  "change": {
    "actions": ["delete"],
    "before": { ... },
    "after": null
  }
}
```

## Troubleshooting

### "No such file or directory"
Make sure you're running from the correct directory:
```bash
cd /home/thebearguy/batcave/tf-gatekeeper
```

### "OPA binary not found"
sure OPA is installed:
```bash
which opa
# If not found, install it
```

### Policies don't compile
```bash
tf-gate check-policies
# Fix any policy syntax errors first
```

## Test Results

After running `test_runner.py`, check `test_results.json` for detailed JSON output of all test results.

Example output:
```json
{
  "plan_file": "tfplan_green.json",
  "description": "GREEN: Low risk - 3 new web servers",
  "status": "completed",
  "should_block": false,
  "phases": {
    "phase1": {
      "blast_radius": {
        "level": "green",
        "total_resources": 3,
        ...
      }
    },
    ...
  }
}
```
