# Workshop Technical Assistant Setup

The Virtual TA platform is split into two applications:
1. **`workshop-ta`**: The student-facing LLM chat interface.
2. **`workshop-ta-admin`**: The organizer-facing dashboard to create events and isolate courses.

This guide provides the step-by-step commands to configure the Google Cloud resources required by both services.

---

## 🗄️ 1. Cloud SQL Setup (events) & Firestore (interactions)

**A. Firestore (Chat Logs for `workshop-ta`)**
```bash
gcloud services enable firestore.googleapis.com
gcloud firestore databases create --database=virtual-ta-test --location=us-central1 --type=firestore-native
```

**B. Cloud SQL (Event Configuration for `workshop-ta-admin`)**
```bash
# Enable API
gcloud services enable sqladmin.googleapis.com

# Create PostgreSQL instance (Takes ~5 minutes)
gcloud sql instances create events-db-instance \
    --database-version=POSTGRES_15 \
    --region=us-central1 \
    --tier=db-f1-micro

# Create the events database
gcloud sql databases create events_db --instance=events-db-instance

# Create the admin user (replace with a secure password)
gcloud sql users create admin --instance=events-db-instance --password=1234qwer
```

**C. Initialize SQL Schema**
To initialize the schema natively, run the provided `schema.sql` via `gcloud sql connect`:
```bash
gcloud sql connect events-db-instance --user=admin --quiet < backend/schema.sql
```
*(Alternatively, you can skip the manual creation and just run `terraform apply` inside the `terraform/` directory!)*

---

## 🔐 2. Google OAuth 2.0 Setup (Client ID)

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

---

## 🚀 3. Environment Configuration

You must configure the `.env` variables for **both** backend services.

**In `workshop-ta/backend/.env`:**
```text
GOOGLE_CLOUD_PROJECT=your-google-project-id
FIRESTORE_DATABASE_ID=virtual-ta-interaction
```

**In `workshop-ta-admin/backend/.env`:**
```text
GOOGLE_CLOUD_PROJECT=your-google-project-id
FIRESTORE_DATABASE_ID=virtual-ta-interaction
GOOGLE_CLIENT_ID=your_client_id_from_step_2_here.apps.googleusercontent.com
ROOT_ADMIN_EMAILS=your.email@example.com,another.admin@example.com
```
*(The `ROOT_ADMIN_EMAILS` variable allows specified users to see all events created by anyone in the admin dashboard).*


```
gcloud artifacts repositories create virtual-ta-pipeline \
    --repository-format=docker \
    --location=us-central1 \
    --description="Docker repository holding pre-built Cloud Build custom executor images." || true

```
---

## 💻 4. Local Testing & Starting the Services

**B. Start the Admin App**
In a new terminal, navigate to `workshop-ta-admin` and run:
```bash
export GOOGLE_CLOUD_PROJECT=""
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8081
```



Open `http://localhost:8081` to sign in, create a new event, and pick courses.

---


