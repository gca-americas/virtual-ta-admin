const API_BASE = "/api";

let adminIdToken = null;
let allCourses = [];

const authContainer = document.getElementById("admin-auth-container");
const actionBar = document.getElementById("admin-action-bar");
const coursesView = document.getElementById("courses-view");
const courseFormContainer = document.getElementById("course-form-container");
const showCreateFormBtn = document.getElementById("show-create-form-btn");
const cancelCourseBtn = document.getElementById("cancel-course-btn");
const saveCourseBtn = document.getElementById("save-course-btn");
const formTitle = document.getElementById("form-title");

const courseSearchInput = document.getElementById("course-search-input");
const courseSearchBtn = document.getElementById("course-search-btn");

courseSearchBtn?.addEventListener("click", () => {
    const q = courseSearchInput.value.trim();
    loadCourses(q);
});

courseSearchInput?.addEventListener("keypress", (e) => {
    if (e.key === "Enter") courseSearchBtn.click();
});

// Inputs
const inputMode = document.getElementById("course-mode");
const inputId = document.getElementById("course-id");
const inputName = document.getElementById("course-name");
const inputRepo = document.getElementById("course-repo-url");
const inputDir = document.getElementById("course-directory-root");
const inputPub = document.getElementById("course-published");

async function initAdminAuth() {
    try {
        const res = await fetch(`${API_BASE}/config`);
        const config = await res.json();
        
        if (!config.google_client_id) {
            document.getElementById("admin-auth-msg").innerHTML = "<strong style='color:#ff4a4a'>Google Client ID is missing.</strong>";
            return;
        }

        window.google.accounts.id.initialize({
            client_id: config.google_client_id,
            cancel_on_tap_outside: false,
            callback: (response) => {
                sessionStorage.setItem("adminIdToken", response.credential);
                processAdminIdToken(response.credential);
            }
        });
        
        const cachedToken = sessionStorage.getItem("adminIdToken");
        if (cachedToken) {
            processAdminIdToken(cachedToken);
        } else {
            window.google.accounts.id.renderButton(
                document.getElementById("google-btn"),
                { theme: "outline", size: "large" }
            );
        }
    } catch (e) {
        console.error("Failed to load auth config", e);
    }
}

async function processAdminIdToken(token) {
    adminIdToken = token;
    try {
        const authRes = await fetch(`${API_BASE}/admin/verify`, {
            headers: { "Authorization": `Bearer ${adminIdToken}` },
            cache: "no-store"
        });
        
        const authData = await authRes.json();
        
        if (!authRes.ok || authData.role !== 'superadmin') {
            sessionStorage.removeItem("adminIdToken");
            window.google.accounts.id.renderButton(
                document.getElementById("google-btn"),
                { theme: "outline", size: "large" }
            );
            document.getElementById("admin-auth-msg").innerHTML = `<strong style='color:#ff4a4a'>SuperAdmin clearance perfectly required.</strong>`;
            return;
        }
        
        authContainer.classList.add("hidden");
        
        try {
            const payload = JSON.parse(atob(adminIdToken.split('.')[1]));
            document.getElementById("logged-in-user").innerHTML = `Logged in as <strong style="color: #58a6ff;">${payload.email}</strong> <span style="font-size: 0.8rem; color: #f85149; background: rgba(255,255,255,0.1); padding: 2px 6px; border-radius: 4px; margin-left: 5px; vertical-align: middle;">SuperAdmin</span>`;
        } catch(e) { console.error("JWT Decode failed", e); }

        actionBar.classList.remove("hidden");
        coursesView.classList.remove("hidden");
    } catch(e) {
        document.getElementById("admin-auth-msg").innerHTML = `<strong style='color:#ff4a4a'>Network connection failed.</strong>`;
    }
}

async function loadCourses(queryStr = "") {
    if (!adminIdToken) return;
    try {
        const urlParams = new URLSearchParams();
        if (queryStr) urlParams.append("q", queryStr);
        
        const res = await fetch(`${API_BASE}/admin/courses?${urlParams.toString()}`, {
            headers: { "Authorization": `Bearer ${adminIdToken}` },
            cache: "no-store"
        });
        if (!res.ok) throw new Error("Fetch failed");
        
        allCourses = await res.json();
        renderCourses();
    } catch(e) {
        document.getElementById("courses-list").innerHTML = "<p style='color: #ff4a4a;'>Failed to load courses natively.</p>";
    }
}

function renderCourses() {
    const container = document.getElementById("courses-list");
    if (allCourses.length === 0) {
        container.innerHTML = "<p style='color: #aaa; font-size: 0.9rem;'>No courses configured.</p>";
        return;
    }

    container.innerHTML = allCourses.map(c => `
        <div class="course-card">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
                <h3 style="color: #4a90e2; margin: 0;">${c.name} <span style="font-size:0.75rem; color:#8b949e; font-weight:normal;">(${c.id})</span></h3>
                <span style="font-size: 0.75rem; padding: 2px 6px; border-radius: 4px; background: ${c.is_published ? 'rgba(46, 160, 67, 0.2)' : 'rgba(248, 81, 73, 0.2)'}; color: ${c.is_published ? '#3fb950' : '#ff7b72'};">
                    ${c.is_published ? 'Published' : 'Draft'}
                </span>
            </div>
            <p style="margin: 0 0 5px 0; font-size: 0.85rem; color: #8b949e; word-break: break-all;"><strong>Repo:</strong> <a href="${c.repo_url}" target="_blank" style="color: #58a6ff;">${c.repo_url}</a></p>
            <p style="margin: 0 0 5px 0; font-size: 0.85rem; color: #8b949e;"><strong>Path:</strong> <code>${c.directory_root}</code></p>
            <div style="display: flex; gap: 15px; margin: 0 0 10px 0; font-size: 0.8rem; color: #8b949e; background: rgba(0,0,0,0.2); padding: 8px; border-radius: 4px; border: 1px solid rgba(255,255,255,0.05);">
                <div><strong>Eval Score:</strong> <span style="color: ${c.eval_score === '100%' || c.eval_score === '100' ? '#3fb950' : (c.eval_score === '0%' ? '#aaa' : '#d29922')};">${c.eval_score || '0%'}</span></div>
                <div><strong>Last Eval:</strong> <span>${c.last_eval_date || 'N/A'}</span></div>
            </div>
            <p style="margin: 0 0 15px 0; font-size: 0.75rem; color: #6e7681; font-style: italic;">Last Updated: ${c.last_update_date || 'Just now'}</p>
            
            <div style="display: flex; gap: 8px;">
                <button onclick="editCourse('${c.id}')" class="glow-btn" style="padding: 4px 10px; font-size: 0.8rem; width: auto; min-height: 0;">Edit</button>
                <button onclick="deleteCourse('${c.id}')" class="glow-btn" style="padding: 4px 10px; font-size: 0.8rem; width: auto; min-height: 0; background: #21262d; border: 1px solid rgba(255,255,255,0.1); color: #ff4a4a; box-shadow: none;">Delete</button>
            </div>
        </div>
    `).join('');
}

showCreateFormBtn.addEventListener("click", () => {
    inputMode.value = "create";
    formTitle.textContent = "Create New Course";
    inputId.value = "";
    inputId.disabled = false;
    inputName.value = "";
    inputRepo.value = "";
    inputDir.value = "/";
    inputPub.value = "true";
    
    courseFormContainer.classList.remove("hidden");
    showCreateFormBtn.classList.add("hidden");
});

cancelCourseBtn.addEventListener("click", () => {
    courseFormContainer.classList.add("hidden");
    showCreateFormBtn.classList.remove("hidden");
});

window.editCourse = function(courseId) {
    const course = allCourses.find(c => c.id === courseId);
    if (!course) return;

    inputMode.value = "edit";
    formTitle.textContent = `Edit Course: ${courseId}`;
    
    // Lock Primary Key modifications structurally
    inputId.value = course.id;
    inputId.disabled = true; 
    
    inputName.value = course.name;
    inputRepo.value = course.repo_url;
    inputDir.value = course.directory_root;
    inputPub.value = course.is_published ? "true" : "false";
    
    courseFormContainer.classList.remove("hidden");
    showCreateFormBtn.classList.add("hidden");
    window.scrollTo({ top: 0, behavior: 'smooth' });
};

window.deleteCourse = async function(courseId) {
    if (!confirm(`Are you absolutely sure you want to permanently delete "${courseId}"? If this is attached to active events, it may fail natively.`)) return;
    
    try {
        const res = await fetch(`${API_BASE}/admin/courses/${courseId}`, {
            method: "DELETE",
            headers: { "Authorization": `Bearer ${adminIdToken}` }
        });
        const data = await res.json();
        if (res.ok) {
            loadCourses();
        } else {
            alert(data.detail || "Deletion failed recursively.");
        }
    } catch(e) {
        alert("Network error.");
    }
};

saveCourseBtn.addEventListener("click", async () => {
    const id = inputId.value.trim();
    const name = inputName.value.trim();
    const repo_url = inputRepo.value.trim();
    const directory_root = inputDir.value.trim() || "/";
    const is_published = inputPub.value === "true";

    if (!id || !name || !repo_url) return alert("ID, Name, and Repository URL are required mappings.");

    saveCourseBtn.disabled = true;
    saveCourseBtn.textContent = "Saving...";

    const mode = inputMode.value;
    const url = mode === "create" ? `${API_BASE}/admin/courses` : `${API_BASE}/admin/courses/${id}`;
    const method = mode === "create" ? "POST" : "PUT";

    try {
        const res = await fetch(url, {
            method: method,
            headers: { 
                "Authorization": `Bearer ${adminIdToken}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                id, name, repo_url, directory_root, is_published
            })
        });

        const data = await res.json();
        if (res.ok) {
            courseFormContainer.classList.add("hidden");
            showCreateFormBtn.classList.remove("hidden");
            if (courseSearchInput.value.trim()) {
                loadCourses(courseSearchInput.value.trim());
            }
        } else {
            alert(`Error: ${data.detail || 'Internal Server Error'}`);
        }
    } catch (e) {
        alert("Server error deploying the course logic.");
    } finally {
        saveCourseBtn.disabled = false;
        saveCourseBtn.textContent = "Save Course";
    }
});

// Boot securely
initAdminAuth();
