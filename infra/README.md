# Infrastructure as Code — Azure

Provisions the core Azure resources for Phase 1:
- Resource Group
- Azure Database for PostgreSQL Flexible Server (+ database, firewall rule, geo-redundant backups)
- Azure Container Registry
- Storage Account + Blob container for attachments (soft-delete enabled)
- Log Analytics Workspace + Container Apps Environment

Container Apps for the backend/frontend themselves are created via the `az
containerapp create` commands in `docs/deployment-azure.md` (kept outside
Terraform in Phase 1 since their image tags change on every deploy — a
natural fit for a CD pipeline rather than a Terraform apply). They can be
migrated into Terraform (`azurerm_container_app`) once deploys stabilize.

## Usage
```bash
terraform init
terraform plan -var="admin_password=<strong-password>"
terraform apply -var="admin_password=<strong-password>"
```

## Variables
| Name | Description | Default |
|---|---|---|
| `location` | Azure region | `eastus` |
| `prefix` | Resource name prefix | `pms` |
| `admin_password` | PostgreSQL admin password (required, sensitive) | — |
