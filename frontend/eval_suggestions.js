const API_BASE = "/api";
let adminIdToken = null;
let currentCourseId = null;

const authContainer = document.getElementById("admin-auth-container");
const actionBar = document.getElementById("admin-action-bar");
const evalsView = document.getElementById("evals-view");
const courseTitleDisplay = document.getElementById("course-title-display");

const suggestionModal = document.getElementById("suggestion-modal");
const suggestionContent = document.getElementById("suggestion-markdown-content");
document.getElementById("close-suggestion").onclick = () => suggestionModal.style.display = "none";

const questionsModal = document.getElementById("questions-modal");
const questionsContent = document.getElementById("questions-list-content");
document.getElementById("close-questions").onclick = () => questionsModal.style.display = "none";

window.onclick = (event) => {
    if (event.target == suggestionModal) suggestionModal.style.display = "none";
    if (event.target == questionsModal) questionsModal.style.display = "none";
};

// Initial setup from URL
const urlParams = new URLSearchParams(window.location.search);
currentCourseId = urlParams.get('course_id');
if(currentCourseId) {
    courseTitleDisplay.textContent = `Course ID: ${currentCourseId}`;
} else {
    courseTitleDisplay.textContent = "Error: No Course ID provided";
}


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
        
        if (!authRes.ok || !['superadmin', 'courseadmin'].includes(authData.role)) {
            sessionStorage.removeItem("adminIdToken");
            window.google.accounts.id.renderButton(
                document.getElementById("google-btn"),
                { theme: "outline", size: "large" }
            );
            document.getElementById("admin-auth-msg").innerHTML = `<strong style='color:#ff4a4a'>SuperAdmin or CourseAdmin clearance strictly required.</strong>`;
            return;
        }
        
        authContainer.classList.add("hidden");
        actionBar.classList.remove("hidden");
        evalsView.classList.remove("hidden");
        
        if(currentCourseId) {
            loadEvalSuggestions();
        }
        
    } catch(e) {
        document.getElementById("admin-auth-msg").innerHTML = `<strong style='color:#ff4a4a'>Network connection failed.</strong>`;
    }
}

async function loadEvalSuggestions() {
    const listContainer = document.getElementById("evals-list");
    listContainer.innerHTML = "<p style='color:#aaa'>Loading past evaluations...</p>";
    try {
        const res = await fetch(`${API_BASE}/admin/eval_suggestions?course_id=${encodeURIComponent(currentCourseId)}`, {
            headers: { "Authorization": `Bearer ${adminIdToken}` },
            cache: "no-store"
        });
        if (!res.ok) throw new Error("Fetch failed");
        const suggestions = await res.json();
        
        if (suggestions.length === 0) {
            listContainer.innerHTML = "<p style='color:#aaa;'>No evaluations naturally stored for this course yet.</p>";
            return;
        }

        listContainer.innerHTML = suggestions.map(s => {
            const shortText = s.suggest_update ? s.suggest_update.substring(0, 150) + (s.suggest_update.length > 150 ? '...' : '') : 'No suggestions strictly provided.';
            // Storing full text cleanly using Base64 so it doesn't break HTML quotes
            const base64Update = btoa(unescape(encodeURIComponent(s.suggest_update || '')));
            
            return `
            <div class="eval-card">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
                    <h3 style="color: #4a90e2; margin: 0; font-size: 1.1rem;">Score: <span style="color: ${s.score === '100' || s.score === '100%' ? '#3fb950' : '#d29922'};">${s.score}</span></h3>
                    <button onclick="viewQuestions('${s.eval_date_time}')" class="glow-btn" style="padding: 4px 12px; font-size: 0.8rem; width: auto; min-height: 0; background: #8957e5; box-shadow: 0 4px 14px rgba(137, 87, 229, 0.4);">See Questions</button>
                </div>
                <p style="margin: 0 0 10px 0; font-size: 0.85rem; color: #8b949e;"><strong>Evaluated At:</strong> ${s.eval_date_time.replace('T', ' ').substring(0,19)}</p>
                <div style="background: rgba(0,0,0,0.3); padding: 10px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.05); cursor: pointer; transition: all 0.2s ease;" onclick="openSuggestionModal('${base64Update}')" onmouseover="this.style.borderColor='rgba(88,166,255,0.5)'" onmouseout="this.style.borderColor='rgba(255,255,255,0.05)'">
                    <p style="margin: 0 0 5px 0; font-size: 0.8rem; color: #58a6ff; font-weight: bold;">Suggested Update Preview (Click to expand)</p>
                    <p style="margin: 0; font-size: 0.85rem; color: #c9d1d9; font-style: italic;">"${shortText}"</p>
                </div>
            </div>
            `;
        }).join('');
    } catch(e) {
        listContainer.innerHTML = "<p style='color: #ff4a4a;'>Failed to strictly fetch suggestions over network.</p>";
    }
}

window.openSuggestionModal = function(base64Text) {
    const decText = decodeURIComponent(escape(atob(base64Text)));
    suggestionContent.innerHTML = marked.parse(decText);
    suggestionModal.style.display = "flex";
}

window.viewQuestions = async function(evalDateTime) {
    questionsContent.innerHTML = "<p style='color:#aaa'>Loading questions natively...</p>";
    questionsModal.style.display = "flex";
    try {
        const res = await fetch(`${API_BASE}/admin/eval_logs?course_id=${encodeURIComponent(currentCourseId)}&eval_date_time=${encodeURIComponent(evalDateTime)}`, {
            headers: { "Authorization": `Bearer ${adminIdToken}` },
            cache: "no-store"
        });
        if(!res.ok) throw new Error("Fetch failed");
        const logs = await res.json();
        
        if (logs.length === 0) {
            questionsContent.innerHTML = "<p style='color:#aaa'>No question logs safely found matching this evaluation.</p>";
            return;
        }
        
        questionsContent.innerHTML = logs.map(l => {
            return `
            <div style="background: rgba(13, 17, 23, 0.5); padding: 15px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.1); margin-bottom: 15px;">
                <h4 style="color: #58a6ff; margin: 0 0 10px 0; border-bottom: 1px solid rgba(88,166,255,0.2); padding-bottom: 5px;">Question ${l.question_number} <span style="font-size: 0.8rem; color: #8b949e; float: right; font-weight: normal;">Level: ${l.level || 'N/A'}</span></h4>
                <div style="margin-bottom: 15px;">
                    <strong style="color: #c9d1d9; font-size: 0.9rem;">Prompt:</strong>
                    <div class="markdown-body" style="margin-top: 5px;">${marked.parse(l.question || '')}</div>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                    <div>
                        <strong style="color: #3fb950; font-size: 0.9rem;">Preferred Answer (Golden Target):</strong>
                        <div class="markdown-body" style="margin-top: 5px; border-color: rgba(63, 185, 80, 0.3); background: rgba(63, 185, 80, 0.05);">${marked.parse(l.prefer_answer || 'N/A')}</div>
                    </div>
                    <div>
                        <strong style="color: #d29922; font-size: 0.9rem;">TA Actual Response:</strong>
                        <div class="markdown-body" style="margin-top: 5px; border-color: rgba(210, 153, 34, 0.3); background: rgba(210, 153, 34, 0.05);">${marked.parse(l.ta_answer || 'N/A')}</div>
                    </div>
                </div>
            </div>
            `;
        }).join('');
    } catch(e) {
        questionsContent.innerHTML = "<p style='color:#ff4a4a'>Failed to query assessment logs database.</p>";
    }
}
