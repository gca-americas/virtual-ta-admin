terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# 1. Enable Cloud SQL API
resource "google_project_service" "sql_api" {
  project = var.project_id
  service = "sqladmin.googleapis.com"
  
  disable_on_destroy = false
}

# 2. Enable Cloud Run API
resource "google_project_service" "cloudrun_api" {
  project = var.project_id
  service = "run.googleapis.com"
  
  disable_on_destroy = false
}

# 2.4 Enable Cloud Build API
resource "google_project_service" "cloudbuild_api" {
  project = var.project_id
  service = "cloudbuild.googleapis.com"
  disable_on_destroy = false
}

# 2.5 Enable Artifact Registry API
resource "google_project_service" "artifactregistry_api" {
  project = var.project_id
  service = "artifactregistry.googleapis.com"
  disable_on_destroy = false
}

# 2.6 Enable Secret Manager API
resource "google_project_service" "secretmanager_api" {
  project = var.project_id
  service = "secretmanager.googleapis.com"
  disable_on_destroy = false
}

# 2.7 Enable Observability APIs (Workload Manager, Monitoring, Asset, Logging)
resource "google_project_service" "workloadmanager_api" {
  project = var.project_id
  service = "workloadmanager.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "monitoring_api" {
  project = var.project_id
  service = "monitoring.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "cloudasset_api" {
  project = var.project_id
  service = "cloudasset.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "logging_api" {
  project = var.project_id
  service = "logging.googleapis.com"
  disable_on_destroy = false
}

# Fetch the active GCP Project logic (grants access to Project Number)
data "google_project" "project" {
  project_id = var.project_id
}

# 2.8 Grant Workload Manager Service Agent Identity Access
resource "google_project_iam_member" "workload_manager_service_agent" {
  project = var.project_id
  role    = "roles/workloadmanager.serviceAgent"
  member  = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-workloadmanager.iam.gserviceaccount.com"
}

resource "google_project_iam_member" "workload_manager_admin" {
  project = var.project_id
  role    = "roles/workloadmanager.admin"
  member  = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-workloadmanager.iam.gserviceaccount.com"
}

resource "google_project_iam_member" "workload_manager_viewer" {
  project = var.project_id
  role    = "roles/workloadmanager.viewer"
  member  = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-workloadmanager.iam.gserviceaccount.com"
}

# 2.7 Create Secret Manager Payload natively
resource "google_secret_manager_secret" "db_credentials" {
  project   = var.project_id
  secret_id = "events-db-credentials"

  replication {
    auto {}
  }
  
  depends_on = [google_project_service.secretmanager_api]
}

resource "google_secret_manager_secret_version" "db_credentials_version" {
  secret      = google_secret_manager_secret.db_credentials.id
  secret_data = <<EOF
export CLOUD_SQL_CONNECTION_NAME="${var.project_id}:${var.region}:${var.instance_name}"
export DB_USER="admin"
export DB_PASS="${var.db_password}"
export DB_NAME="${var.database_id}"
EOF
}

# 2.6 Pipeline Builders Artifact Repository
resource "google_artifact_registry_repository" "virtual_ta_pipeline" {
  location      = var.region
  repository_id = "virtual-ta-pipeline"
  description   = "Docker repository holding pre-built Cloud Build custom executor images."
  format        = "DOCKER"
  project       = var.project_id
  depends_on    = [google_project_service.artifactregistry_api]
}

# 2.7 Enable Firestore API
resource "google_project_service" "firestore_api" {
  project = var.project_id
  service = "firestore.googleapis.com"
  disable_on_destroy = false
}

# 2.8 Create Firestore Database
resource "google_firestore_database" "interactions_db" {
  project     = var.project_id
  name        = var.firestore_database_id
  location_id = var.region
  type        = "FIRESTORE_NATIVE"
  
  depends_on = [google_project_service.firestore_api]
}

# 3. Create Cloud SQL Instance (PostgreSQL)
resource "google_sql_database_instance" "events_db" {
  name             = var.instance_name
  database_version = "POSTGRES_18"
  region           = var.region

  settings {
    tier = "db-g1-small"
  }
  
  deletion_protection = false
  depends_on = [google_project_service.sql_api]
}

resource "google_sql_database" "database" {
  name     = var.database_id
  instance = google_sql_database_instance.events_db.name
}

resource "google_sql_user" "admin_user" {
  name     = var.db_user
  instance = google_sql_database_instance.events_db.name
  password = var.db_password
}

# 4. Service Account for Application Execution (Dashboard & Student UI)
resource "google_service_account" "app_sa" {
  account_id   = "virtual-ta-app-sa"
  display_name = "Virtual TA Application Service Account"
  project      = var.project_id
}

resource "google_project_iam_member" "app_sa_sql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.app_sa.email}"
}

resource "google_project_iam_member" "app_sa_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.app_sa.email}"
}

resource "google_project_iam_member" "app_sa_datastore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.app_sa.email}"
}

resource "google_project_iam_member" "app_sa_aiplatform_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.app_sa.email}"
}

resource "google_project_iam_member" "app_sa_cloudtrace_agent" {
  project = var.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${google_service_account.app_sa.email}"
}

resource "google_project_iam_member" "app_sa_logging_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.app_sa.email}"
}

# (Optional Deployment) 5. Cloud Run Service 
resource "google_cloud_run_v2_service" "backend" {
  name     = var.service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"
  
  template {
    service_account = google_service_account.app_sa.email

    containers {
      image = "us-central1-docker.pkg.dev/${var.project_id}/virtual-ta-pipeline/${var.service_name}:latest"
      
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "DB_NAME"
        value = google_sql_database.database.name
      }
      env {
        name  = "GOOGLE_CLIENT_ID"
        value = var.google_client_id
      }
      env {
        name  = "FIRESTORE_DATABASE_ID"
        value = google_firestore_database.interactions_db.name
      }
      env {
        name  = "ROOT_ADMIN_EMAILS"
        value = var.root_admin_emails
      }
    }
  }

  depends_on = [google_project_service.cloudrun_api]
  
  lifecycle {
    ignore_changes = [
      template[0].containers[0].image
    ]
  }
}

# Allow Unauthenticated access to Cloud Run
resource "google_cloud_run_v2_service_iam_member" "public_access" {
  name     = google_cloud_run_v2_service.backend.name
  location = google_cloud_run_v2_service.backend.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

output "cloud_sql_connection_name" {
  value = google_sql_database_instance.events_db.connection_name
}

output "cloud_run_url" {
  value = google_cloud_run_v2_service.backend.uri
}
