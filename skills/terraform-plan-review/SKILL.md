---
name: terraform-plan-review
description: Use this skill whenever reviewing a Terraform plan; identify destructive changes, privilege expansion, cost exposure, and unsafe assumptions before approval.
---

# Terraform plan review

1. Run formatting and validation, then generate a fresh plan for the intended workspace and variables.
2. Review every add, change, and destroy; reject unexpected replacements or deletes until their impact is understood.
3. Check IAM, networking, encryption, logging, backup, and public-access changes against least-privilege and security requirements.
4. Identify cost-impacting resources, data-loss risks, dependencies, and changes that need a maintenance window.
5. Record the reviewed plan inputs, required approvals, deployment order, and rollback or recovery steps.
