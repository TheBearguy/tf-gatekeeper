# Terraform Gatekeeper (tf-gate) - Implementation TODO

> Complete build-out of the multi-layered defense system for terraform apply

## Phase 0: Project Setup & Infrastructure

### Core Setup
- [x] Create project structure with proper directory layout
- [x] Initialize Python 3.9+ project with virtual environment
- [x] Set up package configuration (pyproject.toml or setup.py)
- [x] Define project dependencies in requirements.txt
- [ ] Create CI/CD pipeline (GitHub Actions) for testing
- [ ] Set up linting (ruff/black) and type checking (mypy)
- [ ] Create development environment setup documentation

### Tooling & Dependencies
- [ ] Install and configure core dependencies:
  - [ ] Click or Typer for CLI interface
  - [ ] ijson for streaming JSON parsing
  - [ ] opa-python or python-opa for OPA integration
  - [ ] requests for HTTP API calls
  - [ ] pyyaml for configuration parsing
  - [ ] python-dateutil for temporal calculations
- [ ] Set up OPA binary integration (auto-download or system path)
- [ ] Configure test framework (pytest) with fixtures

---

## Phase 1: CLI Framework & Core Interface

### CLI Implementation
- [ ] Implement `tf-gate` main CLI entry point
- [ ] Create command structure:
  - [ ] `tf-gate init` - Initialize policies directory
  - [ ] `tf-gate plan` - Wrapper around terraform plan
  - [ ] `tf-gate apply` - Main validation + apply command
  - [ ] `tf-gate validate` - Standalone validation without apply
- [ ] Add global flags:
  - [ ] `--config` / `-c` for custom config file path
  - [ ] `--verbose` / `-v` for debug output
  - [ ] `--json` for machine-readable output
- [ ] Implement help text and usage documentation

### Terraform Integration
- [ ] Build terraform wrapper that captures:
  - [ ] Plan output to JSON
  - [ ] Exit codes from terraform commands
  - [ ] Error handling and passthrough
- [ ] Create terraform detection (verify terraform is installed)
- [ ] Handle terraform version compatibility checks
- [ ] Implement terraform plan file handling (.tfplan → .json conversion)

### Configuration System
- [ ] Create config file loader (YAML)
- [ ] Define default configuration schema
- [ ] Implement environment variable substitution in config
- [ ] Add config validation with helpful error messages
- [ ] Create default policies directory structure on init

---

## Phase 2: Phase 1 - Ingestion & Blast Radius (CRITICAL)

### Streaming JSON Parser
- [ ] Implement ijson-based streaming parser for plan.json
- [ ] Handle 50MB+ plan files without memory issues
- [ ] Extract key data structures:
  - [ ] resource_changes array
  - [ ] output_changes
  - [ ] terraform_version
  - [ ] configuration data
  - [ ] prior_state information
- [ ] Create data models/classes for parsed plan
- [ ] Add error handling for malformed JSON

### Resource Analysis
- [ ] Build resource change classifier:
  - [ ] Detect create actions
  - [ ] Detect update actions
  - [ ] Detect delete actions
  - [ ] Detect replace actions (destroy + create)
- [ ] Categorize resources by type:
  - [ ] Identify stateful resources (RDS, S3, KMS, etc.)
  - [ ] Identify network resources (VPC, SG, etc.)
  - [ ] Identify compute resources (EC2, Lambda, etc.)
  - [ ] Identify IAM resources (roles, policies)

### Blast Radius Calculation
- [ ] Implement blast radius scoring algorithm:
  - [ ] Count total resources affected
  - [ ] Weight by resource criticality
  - [ ] Factor in action severity (delete > replace > update > create)
- [ ] Create risk levels:
  - [ ] 🟢 Green: 0-5 resources, cosmetic changes only
  - [ 🟡 Yellow: 5-20 resources, compute/network changes
  - [ ] 🔴 Red: 20+ resources, deletions, IAM, or state migrations
- [ ] Add blast radius reporting output
- [ ] Implement dynamic strictness adjustment (Red = mandatory AI review)

---

## Phase 3: Phase 2 - Policy Engine with OPA (CRITICAL)

### OPA Integration
- [ ] Implement OPA client (library or subprocess):
  - [ ] Auto-detect OPA binary or use bundled version
  - [ ] Compile Rego policies from directory
  - [ ] Execute policies against plan data
  - [ ] Parse OPA evaluation results
- [ ] Handle OPA errors gracefully
- [ ] Add OPA version compatibility checks

### Default Policy Suite
- [ ] Create `policies/protected_resources.rego`:
  - [ ] Deny deletion of RDS instances
  - [ ] Deny deletion of KMS keys
  - [ ] Deny deletion of S3 buckets
  - [ ] Allow emergency_override flag
- [ ] Create `policies/security.rego`:
  - [ ] Block 0.0.0.0/0:0 security group rules
  - [ ] Detect overly permissive IAM policies
  - [ ] Flag unencrypted resources
- [ ] Create `policies/cost.rego`:
  - [ ] Flag major cost increases
  - [ ] Detect expensive instance types
  - [ ] Warn on unused resources

### Policy Framework
- [ ] Implement policy loading from directory
- [ ] Support policy categories (deny, warn, info)
- [ ] Create policy context injection:
  - [ ] blast_radius level
  - [ ] timestamp
  - [ ] git_commit hash
  - [ ] terraform_version
- [ ] Add policy testing framework
- [ ] Document policy authoring guide

---

## Phase 4: Phase 3 - Context Engine (CRITICAL)

### Temporal Safety
- [ ] Implement time-based risk escalation:
  - [ ] Detect Friday after 3 PM
  - [ ] Detect weekends
  - [ ] Adjust base_risk score accordingly
- [ ] Add timezone handling (configurable)
- [ ] Implement holiday detection (optional)
- [ ] Create time-based blocking rules

### Drift Detection
- [ ] Implement drift detection workflow:
  - [ ] Run `terraform plan -refresh-only -out=drift.tfplan`
  - [ ] Convert to JSON
  - [ ] Parse drift vs planned changes
- [ ] Build drift conflict analyzer:
  - [ ] Compare resource states
  - [ ] Detect manual console changes
  - [ ] Identify overlapping modifications
- [ ] Implement drift reporting
- [ ] Add drift exit code (2)

### Provider Version Check
- [ ] Track last applied terraform version
- [ ] Compare current vs last version
- [ ] Warn on major version changes
- [ ] Store version history (optional)

### Git Integration
- [ ] Extract current git commit hash
- [ ] Extract commit message for Phase 4
- [ ] Detect branch name
- [ ] Check for uncommitted changes
- [ ] Handle non-git repositories gracefully

---

## Phase 5: Phase 4 - Intent Validation (Semantic Layer)

### LLM Integration
- [ ] Implement LLM provider abstraction:
  - [ ] Local LLM (Ollama) support
  - [ ] OpenAI API support
  - [ ] Configurable provider selection
- [ ] Build prompt template for intent checking
- [ ] Implement semantic analysis:
  - [ ] Compare commit message vs. actual changes
  - [ ] Detect mismatches (e.g., "update tags" vs "delete database")
- [ ] Handle LLM failures gracefully
- [ ] Add cost/performance controls (token limits, caching)

### Fallback Intent Check
- [ ] Implement keyword-based matching (fallback)
  - [ ] Simple string matching for common patterns
  - [ ] Detect dangerous keywords in commit
  - [ ] Compare against change actions
- [ ] Ensure fallback works without LLM

### Intent Reporting
- [ ] Generate human-readable mismatch explanations
- [ ] Provide 2-sentence risk summaries
- [ ] Suggest corrections when intent mismatches
- [ ] Add intent validation exit code (3)

---

## Phase 6: Safety Features & Emergency Protocols

### Shadow Mode
- [ ] Implement `--shadow-mode` flag
- [ ] Run all validations without blocking
- [ ] Log what would have been blocked
- [ ] Generate shadow mode report
- [ ] Allow apply to proceed anyway

### Break Glass Protocol
- [ ] Implement `--break-glass` flag with incident ID
- [ ] Bypass all validation phases
- [ ] Immediate apply execution
- [ ] Trigger audit logging:
  - [ ] Record incident ID
  - [ ] Log timestamp and user
  - [ ] Capture terminal session (asciinema integration)
- [ ] Add pager duty integration hook
- [ ] Create post-mortem ticket (GitHub/Jira API)
- [ ] Break glass exit code (42)

### Audit Logging
- [ ] Implement comprehensive audit trail:
  - [ ] Log all validation phases
  - [ ] Record decisions (pass/fail)
  - [ ] Store policy violations
  - [ ] Capture break-glass usage
- [ ] Add structured logging (JSON)
- [ ] Implement log rotation
- [ ] Create audit report generation

---

## Phase 7: Notifications & Integrations

### Slack Integration
- [ ] Implement Slack webhook notifications
- [ ] Send alerts on critical blocks
- [ ] Include summary of violations
- [ ] Format messages with blast radius info
- [ ] Support custom message templates

### GitHub Integration
- [ ] Post validation results as PR comments
- [ ] Include policy violation details
- [ ] Add blast radius visualization
- [ ] Support GitHub Actions workflow

### Cost Estimation (Infracost)
- [ ] Integrate Infracost for cost estimation
- [ ] Parse cost estimates from plan
- [ ] Add cost-based policies
- [ ] Warn on significant cost increases
- [ ] Block on budget violations

### PagerDuty Integration
- [ ] Add PagerDuty API integration
- [ ] Trigger alerts on break-glass usage
- [ ] Page on-call engineer
- [ ] Include incident context

---

## Phase 8: Testing & Quality Assurance

### Unit Tests
- [ ] Test streaming JSON parser with large files
- [ ] Test blast radius calculation
- [ ] Test OPA policy evaluation
- [ ] Test temporal safety logic
- [ ] Test git integration
- [ ] Test CLI commands

### Integration Tests
- [ ] End-to-end test with real terraform
- [ ] Test against sample terraform projects
- [ ] Test policy violations
- [ ] Test drift detection
- [ ] Test break-glass protocol

### Test Data
- [ ] Create sample plan.json files
- [ ] Build test terraform configurations
- [ ] Generate large plan files for stress testing
- [ ] Create edge case scenarios

### Performance Testing
- [ ] Benchmark 50MB+ plan parsing
- [ ] Test OPA policy compilation speed
- [ ] Measure LLM response times
- [ ] Optimize memory usage

---

## Current Status

**Priority Order:**
1. Phase 0-1: Project setup and CLI (Foundation)
2. Phase 2: Ingestion & Blast Radius (Core functionality)
3. Phase 3: OPA Policy Engine (Security layer)
4. Phase 4: Context Engine (Safety layer)
5. Phase 5: Intent Validation (Semantic layer)
6. Phase 6: Safety features (Emergency protocols)
7. Phase 7-9: Polish, integrations, docs
