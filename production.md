# Production Deployment Guide (workshop-ta-admin)

## 🔐 Google OAuth 2.0 Setup (Client ID)

To protect the `workshop-ta-admin` dashboard, you must generate a Google Client ID. This allows organizers to sign in securely.

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Navigate to **APIs & Services > OAuth consent screen**. https://console.cloud.google.com/auth/clients/create
   - Select **Internal** (if restricted to your Google Workspace) or **External**, then click **Create**.
   - Fill in the required App Information (App name: "Workshop TA Admin", User support email).
   - Click **Save and Continue** through the Scopes and Test Users screens.
3. Navigate to **APIs & Services > Credentials**.
4. Click **+ CREATE CREDENTIALS** > **OAuth client ID**.
5. Select **Web application** as the Application type.
6. Name it (e.g., "Virtual TA Admin UI").
7. Under **Authorized JavaScript origins**, click **+ ADD URI**.
   - Add your local testing URI: `http://localhost:8080` (or whichever port you use).
   - Add your production Cloud Run URI once deployed: `https://workshop-ta-admin-xyz.run.app`
8. Click **Create**.
9. A popup will reveal your **Client ID** (e.g., `123456789-abcxyz.apps.googleusercontent.com`). Copy this!


This guide documents the formalized pipeline to deploy the Virtual TA Admin architecture completely via Terraform leveraging securely bound Service Accounts and Artifact Registries.

---

## 🔐 0. Set Configuration Variables

To avoid retyping your long IDs constantly, generate them locally in your bash window first! 

```bash
export PROJECT_ID="gca-america-virtual-ta"
export CLIENT_ID="your-client-id"
export DB_PASSWORD="your-postgres-password"
export ROOT_ADMIN_EMAILS="your_google_email@gmail.com"



gcloud config set project $PROJECT_ID
gcloud auth login
```

---

## 🏗️ 1. Bootstrapping initial Artifact Registry 

Terraform manages the Artifact Registry dynamically, but deploying the Cloud Run instance inherently requires the baseline Docker Container to already exist! To break this chicken-and-egg dependency, we will provision *just* the Artifact Repository first natively using Terraform explicitly:

1. Initialize the terraform state:
```bash
cd terraform
terraform init
```

4. Target exactly the Artifact Registry via Terraform avoiding Cloud Run errors:
```bash
terraform apply -target="google_project_service.cloudbuild_api" \
  -target="google_project_service.secretmanager_api" \
  -target="google_artifact_registry_repository.virtual_ta_pipeline" \
  -var="project_id=$PROJECT_ID" \
  -var="google_client_id=$CLIENT_ID" \
  -var="db_password=$DB_PASSWORD"
```

5. With the repository globally created natively, push the Initial Docker Image using Cloud Build:
```bash
cd ..
gcloud services enable cloudbuild.googleapis.com artifactregistry.googleapis.com
gcloud builds submit --tag us-central1-docker.pkg.dev/$PROJECT_ID/virtual-ta-pipeline/virtual-ta-admin:latest .
```

---

## Phase 2: Deploying the Core Architecture

We heavily recommend deploying the core infrastructure logic completely seamlessly through **Terraform**. Once the image exists cleanly inside the Artifact registry, terraform will correctly lock onto it natively while initializing your Cloud SQL `db-g1-small` / `POSTGRES_18` instance.

```bash
cd terraform
terraform plan -var="project_id=$PROJECT_ID" -var="google_client_id=$CLIENT_ID" -var="db_password=$DB_PASSWORD"
terraform apply \
    -var="project_id=$PROJECT_ID" \
    -var="google_client_id=$CLIENT_ID" \
    -var="db_password=$DB_PASSWORD" \
    -var="root_admin_emails=$ROOT_ADMIN_EMAILS"
```

### What Terraform Solves For You Natively:
- ✅ Enables `sqladmin.googleapis.com` & `run.googleapis.com`
- ✅ Provisions your strictly spec'd `POSTGRES_18` Cloud SQL loop natively
- ✅ Generates an active database user dynamically.
- ✅ Creates the `virtual-ta-admin-sa` Service Account granting rigorous IAM permissions.
- ✅ Maps all the internal Network connection wrappers globally, bypassing messy `.env` injections.

---

## Phase 3: Database Seeding Sequence

Setup the Cloud SQL:

Because macOS local `gcloud` environments notoriously fail to locate the internal `cloud-sql-proxy` TCP binding binaries dynamically, use the Python injection script wrapping the verified Admin Dashboard architecture natively!

```bash
cd ..
# Create the local environment file for the FastAPI backend natively
cat << EOF > backend/.env
GOOGLE_CLOUD_PROJECT=$PROJECT_ID
GOOGLE_CLIENT_ID=$CLIENT_ID
ROOT_ADMIN_EMAILS=$ROOT_ADMIN_EMAILS
EOF

python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python seed.py
```

The system is now fully deployed exactly identically to standard corporate production infrastructure guidelines natively mapped strictly out of raw Terraform config structures.

---

## Phase 4: Future Application Updates (CI/CD)

Deploy to Cloud Run after infra already setup. 

```bash

export PROJECT_ID=""
export CLIENT_ID=""
export DB_PASSWORD=""
export ROOT_ADMIN_EMAILS=""

# Push your local code natively passing strictly the Cloud Run substitution logic
gcloud builds submit --config cloudbuild.yaml \
    --substitutions=^:^_DB_NAME="event_db":_GOOGLE_CLIENT_ID="$CLIENT_ID":_FIRESTORE_DATABASE_ID="virtual-ta-interaction":_ROOT_ADMIN_EMAILS="$ROOT_ADMIN_EMAILS" \
    .
```

This officially finalizes the Admin Dashboard production release cycle!
