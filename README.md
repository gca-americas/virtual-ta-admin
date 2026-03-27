# Virtual TA Central Control Architecture

Welcome to the **Virtual Technical Assistant** ecosystem! This repository (`workshop-ta-admin`) serves as the central system for managing highly-scalable, ephemeral AI assistants deployed securely for individual workshops and learning labs. 

Because managing dynamic Cloud infrastructure securely requires cleanly separated responsibilities, this entire ecosystem is strictly decoupled into a **Three-Project Architecture**.

---

## 🏗️ The Three Projects

### 1. 🛡️ Virtual TA Admin portal (`virtual-ta-admin`)
*(You are here!)*
- **Purpose**: The centralized control panel and infrastructure anchor.
- **Functionality**: Admins log in securely (via Google OAuth), provision new upcoming workshops natively, assign learning courses, and manage active system configurations. 
- **State**: It securely manages the core **Cloud SQL PostgreSQL database** mapping the entire global workshop topology (Active Events, Courses, Superadmins, Running Logs).

### 2. ⚙️ Virtual TA Jobs (`virtual-ta-job`)
- **Purpose**: The background Infrastructure-as-Code pipeline orchestrator.
- **Functionality**: It contains the Google Cloud Scheduler hooks, Pub/Sub triggers (`deploy-queue` / `demolish-queue`), and Cloud Build executors.
- **Role**: It actively scans the Admin database for pending workshops. When an event is scheduled to start, this pipeline automatically physically builds and deploys the infrastructure dynamically over GCP without human intervention. When the event ends, it destroys the resources to save costs!

### 3. 🎓 Virtual TA (`virtual-ta`)
- **Purpose**: The actual student-facing generative AI learning environment.
- **Functionality**: This is the literal codebase that gets deployed dynamically as an isolated container instance for every individual event. 
- **Role**: When attendees arrive at a workshop, they open their dedicated URL deployed by the Job Orchestrator, log in with their `Event Code`, and securely chat directly with exactly the customized AI parameters mapped to their specific class.

---

## 🔄 The Complete Event Lifecycle Workflow

Here is exactly how these three independent systems interlock seamlessly to deploy learning instances:

1. **Schedule Event**: An instructor accesses the **Virtual TA Admin portal** and natively registers a new workshop (e.g., *DevOps 101*), setting a strict Start and End date natively. The Admin portal locks this securely into the `events_db` Cloud SQL instance.
2. **Hourly Polling**: The **Virtual TA Jobs** completely isolated `hourly-job` cron trigger sweeps the database. It sees *DevOps 101* is scheduled to start today!
3. **Infrastructure Pub/Sub Trigger**: The Job Orchestrator directly fires a message payload natively onto the Google Cloud `deploy_queue`. 
4. **Build Pipeline Natively Executes**: Cloud Build intercepts the trigger, literally clones the source code directly from the **Virtual TA** student repository, builds an isolated Docker container exactly mapping the courses for *DevOps 101*, and hosts it identically onto a brand new Cloud Run Service URL.
5. **Student Access**: The container spins up. Students go to that generated URL, input the Event Code, and actively converse with the AI natively during their lab hours safely. All conversational interactions map securely into an isolated Firestore DB.
6. **Automated Demolition**: 48 hours later, the workshop finishes. The **Virtual TA Jobs** `hourly-job` detects the expired status. It dynamically launches a `demolish_queue` message natively into Cloud Build, which aggressively deletes the Cloud Run Server instance off the cloud, eliminating all active hosting costs!

## 🛠️ Platform Management

### Managing Administrator Access
The Virtual TA Admin portal utilizes a strict Role-Based Access Control (RBAC) model anchored by Google OAuth:
1. **Super Admins**: When the infrastructure is first deployed, foundational "Super Admins" are bootstrapped into the system via the `ROOT_ADMIN_EMAILS` environmental variable. These accounts have immutable access.
2. **Adding New Admins**: Any existing authenticated administrator can easily grant access to additional colleagues natively! Simply open the **Virtual TA Admin portal**, click on the **Admins** tab, and enter their Google-registered email address. They will be instantly vaulted into the system and can immediately authenticate.

### Expanding the Course Catalog
Courses dictate exactly which source repositories, documentation, and specific syllabus files the AI Assistant will study when an event launches. 

1. **Prerequisite - Public GitHub Repository**: Before any course can be registered in the system, instructors must first physically commit their learning materials, documentation, and specific AI "skills" into a **Public GitHub Repository**. Because the Google Cloud Build pipelines dynamically clone these source files during the event provisioning phase, the repository cannot be private.
2. **SuperAdmin Dashboard**: Once the repository is public, instructors can ask the superadmin to dynamically register brand new courses via the portal. Navigate to the **Courses** tab, define a human-readable title, strictly map the target Git Repository URL, and provide the exact directory tree the AI should index! Any newly added courses intuitively appear in the Dropdown Menu during your next Event Creation!


## 📂 Architecture of this Repository

The `virtual-ta-admin` portal is purposefully designed as a lightweight, highly-performant monolith optimized for secure Google Cloud deployment.

### Tech Stack
- **Backend**: **FastAPI** (Python 3.11+) powering high-speed async REST endpoints.
- **Frontend**: **Vanilla HTML/CSS/JS** directly served by the backend to eliminate complex node setups.
- **Database**: **Google Cloud SQL (PostgreSQL)** managed securely via `pg8000` connectors.
- **Infrastructure**: **Terraform** managing all authoritative state and Secret Manager bounds natively.

### Codebase Structure
```text
workshop-ta-admin/
├── backend/
│   ├── main.py          # Core FastAPI server and REST endpoint routing
│   ├── database.py      # Cloud SQL connection logic & Secret Manager extraction
│   └── schema.sql       # Static PostgreSQL schema payload (events, courses, admins)
├── frontend/
│   ├── index.html       # Single-page application logic and dashboard UI
│   ├── style.css        # Premium dark-mode UI designs natively styled
│   └── js/              # Client-side API fetch flows
├── terraform/           
│   ├── main.tf          # Core infrastructure mapping for Cloud SQL & Cloud Run
│   └── variables.tf     # Terraform input variables
├── Dockerfile           # Web server containerization packaging
├── cloudbuild.yaml      # CI/CD pipeline triggers natively building Cloud Run instances
└── seed.py              # Local setup utility pushing schema to cloud databases
```

---

## 🚀 Deployment Instructions

If you are a system administrator looking to deploy this entire architecture from absolute scratch onto a brand new GCP project logically, please follow the infrastructure documentation meticulously:

1. Follow the exact deployment guide inside `workshop-ta-admin/production.md` to establish the Cloud SQL mapping, IAM identity boundaries, and the Admin web container.
2. Next, deploy the background Pipeline Triggers cleanly by following `workshop-ta-job/production-deploy.md`.

*All core networking, authentication pipelines, routing domains, and background orchestrators strictly synthesize via pure Terraform configurations.*
