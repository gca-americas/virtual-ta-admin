variable "project_id" {
  description = "The Google Cloud Project ID"
  type        = string
}

variable "region" {
  description = "The region to deploy resources (e.g., us-central1)"
  type        = string
  default     = "us-central1"
}

variable "database_id" {
  description = "The name of the PostgreSQL Database"
  type        = string
  default     = "event_db"
}

variable "instance_name" {
  description = "The physically deployed name of the Cloud SQL Instance"
  type        = string
  default     = "events-db-instance"
}

variable "service_name" {
  description = "The name of the Cloud Run admin service"
  type        = string
  default     = "virtual-ta-admin"
}

variable "google_client_id" {
  description = "The OAuth 2.0 Client ID for securely locking out non-admins from the dashboard."
  type        = string
}

variable "root_admin_emails" {
  description = "Comma-separated list of superadmin emails bootstrapped actively on initial deployment."
  type        = string
}

variable "db_password" {
  description = "The secure password for the admin PostgreSQL Cloud SQL user."
  type        = string
  sensitive   = true
}

variable "db_user" {
  description = "The database user logic wrapping the Cloud SQL backend (e.g. admin)"
  type        = string
  default     = "admin"
}

variable "firestore_database_id" {
  description = "The unique string identifier locating the Firestore native Database holding interactions natively."
  type        = string
  default     = "virtual-ta-interaction"
}
