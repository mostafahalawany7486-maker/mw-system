# Phase 1 — Azure Deployment Guide

This covers deploying Phase 1 to Azure using **Azure Container Apps**
(recommended: scales to zero, simple container-native scaling) for the
backend and frontend, **Azure Database for PostgreSQL – Flexible Server**
for the database, and **Azure Blob Storage** for file attachments.
Terraform config is provided in `/infra` for repeatable provisioning.

## 1. Prerequisites
- An Azure subscription and the `az` CLI installed and logged in (`az login`)
- Docker installed locally (to build and push images)
- Terraform installed (optional but recommended — see `/infra`)

## 2. Provision infrastructure

### Option A: Terraform (recommended)
```bash
cd infra
terraform init
terraform plan -var="admin_password=<choose-a-strong-db-password>"
terraform apply -var="admin_password=<choose-a-strong-db-password>"
```
This provisions: a resource group, Azure Database for PostgreSQL Flexible
Server, an Azure Container Registry, a Container Apps Environment, two
Container Apps (backend, frontend), and a Storage Account with a blob
container for attachments.

### Option B: Manual (az CLI)
```bash
az group create -n pms-rg -l eastus

az postgres flexible-server create \
  --resource-group pms-rg --name pms-db-server \
  --admin-user pms_admin --admin-password "<strong-password>" \
  --sku-name Standard_B1ms --tier Burstable --version 16 \
  --storage-size 32 --public-access 0.0.0.0

az postgres flexible-server db create \
  --resource-group pms-rg --server-name pms-db-server --database-name pms_db

az acr create --resource-group pms-rg --name pmsregistry --sku Basic

az storage account create --resource-group pms-rg --name pmsstorageacct --sku Standard_LRS
az storage container create --account-name pmsstorageacct --name pms-attachments

az containerapp env create --resource-group pms-rg --name pms-env --location eastus
```

## 3. Build & push images
```bash
az acr login --name pmsregistry

docker build -t pmsregistry.azurecr.io/pms-backend:latest ./backend
docker push pmsregistry.azurecr.io/pms-backend:latest

docker build -t pmsregistry.azurecr.io/pms-frontend:latest --target production ./frontend
docker push pmsregistry.azurecr.io/pms-frontend:latest
```

## 4. Deploy the backend Container App
```bash
az containerapp create \
  --resource-group pms-rg --name pms-backend --environment pms-env \
  --image pmsregistry.azurecr.io/pms-backend:latest \
  --target-port 8000 --ingress external \
  --min-replicas 1 --max-replicas 5 \
  --env-vars \
    APP_ENV=production \
    DATABASE_URL="postgresql+psycopg2://pms_admin:<password>@pms-db-server.postgres.database.azure.com:5432/pms_db?sslmode=require" \
    SECRET_KEY="<generate-a-long-random-value>" \
    STORAGE_BACKEND=azure_blob \
    AZURE_STORAGE_CONNECTION_STRING="<from Storage Account Access Keys>" \
    AZURE_STORAGE_CONTAINER=pms-attachments \
    BACKEND_CORS_ORIGINS="https://<your-frontend-domain>"
```

Run migrations + seed once, against the production DB (from a one-off job
or locally with `DATABASE_URL` pointed at Azure):
```bash
alembic upgrade head
python seed.py
```
**Change the seeded admin password immediately after first login.**

## 5. Deploy the frontend Container App
```bash
az containerapp create \
  --resource-group pms-rg --name pms-frontend --environment pms-env \
  --image pmsregistry.azurecr.io/pms-frontend:latest \
  --target-port 80 --ingress external \
  --min-replicas 1 --max-replicas 3
```
Rebuild the frontend image with `VITE_API_BASE_URL` pointed at the deployed
backend's public URL before pushing (Vite bakes env vars in at build time):
```bash
docker build -t pmsregistry.azurecr.io/pms-frontend:latest \
  --build-arg VITE_API_BASE_URL=https://pms-backend.<region>.azurecontainerapps.io/api/v1 \
  --target production ./frontend
```
(Add a corresponding `ARG`/`ENV` line to the frontend Dockerfile's build
stage if you go this route, or set the value directly in `frontend/.env`
before building.)

## 6. Custom domain & TLS
Add a custom domain to the frontend Container App via **Custom domains** in
the Azure Portal, or front both apps with **Azure Front Door** for a single
managed TLS certificate, WAF, and CDN caching for static assets.

## 7. High availability, scaling, backups, disaster recovery
- **Horizontal scaling:** both Container Apps are stateless (JWT auth, file
  storage abstracted to Blob) — `--min-replicas`/`--max-replicas` and
  Container Apps' built-in HTTP-based autoscaling handle this out of the box.
- **Load balancing:** handled automatically by Container Apps ingress.
- **High availability (DB):** enable **Zone-redundant HA** on the PostgreSQL
  Flexible Server (`--high-availability ZoneRedundant`) for automatic failover.
- **Automatic backups:** PostgreSQL Flexible Server has automated backups
  enabled by default (7–35 day retention, configurable); Blob Storage should
  have soft-delete and versioning enabled for attachments.
- **Disaster recovery:** configure geo-redundant backup storage
  (`--geo-redundant-backup Enabled`) on the PostgreSQL server, and
  geo-redundant storage (`Standard_GRS`) on the Storage Account.

## 8. CI/CD
See `.github/workflows/ci.yml` for the pipeline that runs backend tests and
frontend type-checking on every push. Extend it with a deploy job that runs
`az acr build` + `az containerapp update` on merges to `main` once you're
ready to automate deployment.
