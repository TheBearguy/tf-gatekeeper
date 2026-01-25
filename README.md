# tf-gatekeeper

> **"Terraform enforces desired state; tf-gatekeeper judges whether enforcing it is safe."**

`tf-gatekeeper` is an AI-assisted risk analysis tool designed to sit between `terraform plan` and `terraform apply`. It bridges the gap between **syntactic correctness** (Is the code valid?) and **operational safety** (Is it safe to run this right now?).

---

## The Problem
Infrastructure-as-Code (IaC) is a blind executor. Standard CI/CD pipelines will happily execute a `terraform apply` that:
1.  **Destroys production databases** due to a simple resource rename.
2.  **Reverts a manual emergency hotfix** (Drift) made by an on-call engineer.
3.  **Opens Security Groups** to `0.0.0.0/0` accidentally.
4.  **Deploys high-risk changes** during a "Friday Afternoon" or a Code Freeze.

##  The Solution
`tf-gatekeeper` analyzes the machine-readable JSON output of a Terraform plan and uses a combination of **Heuristics (Regex/Logic)** and **AI (LLMs)** to provide a human-readable risk assessment.



## ️ Key Features
* **Drift Detection:** Ingests `refresh-only` plans to detect if Terraform is about to overwrite a manual cloud change.
* **Blast Radius Analysis:** Scrutinizes "Crown Jewel" services (RDS, S3, Route53, IAM) for destructive actions.
* **The "When" Logic:** Blocks or warns on deployments during sensitive time windows (e.g., Friday Deploys).
* **AI Insights:** Uses LLMs to explain *why* a plan is risky, catching "Hidden Deletes" (Force-New replacements) that standard linters miss.
* **CI/CD Native:** Returns non-zero exit codes to automatically fail builds in GitHub Actions, GitLab, or Jenkins.

---

##  Technical Architecture
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