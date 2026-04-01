const API_BASE = "/api";

let adminIdToken = null;
let allLogs = [];
let currentOffset = 0;
const EVENTS_LIMIT = 50;
let hasMoreEvents = false;

const authContainer = document.getElementById("admin-auth-container");
const actionBar = document.getElementById("admin-action-bar");
const logsView = document.getElementById("logs-view");

const searchEventId = document.getElementById("log-search-event-id");
const searchEventName = document.getElementById("log-search-event-name");
const statusSelect = document.getElementById("log-status-select");
const sortSelect = document.getElementById("log-sort-select");

const dateTypeSelect = document.getElementById("log-date-type");
const dateMinInput = document.getElementById("log-date-min");
const dateMaxInput = document.getElementById("log-date-max");
const executeSearchBtn = document.getElementById("execute-search-btn");
const loadMoreBtn = document.getElementById("load-more-btn");
const downloadLogsBtn = document.getElementById("download-logs-btn");

executeSearchBtn?.addEventListener("click", () => {
    currentOffset = 0;
    allLogs = [];
    document.getElementById("logs-list").innerHTML = "<p style='color: #aaa; font-size: 0.9rem;'>Searching logs...</p>";
    loadLogs();
});

loadMoreBtn?.addEventListener("click", () => {
    currentOffset += EVENTS_LIMIT;
    if(loadMoreBtn) loadMoreBtn.textContent = "Loading...";
    loadLogs(true);
});

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
        
        if (!authRes.ok || (authData.role !== 'superadmin' && authData.role !== 'admin')) {
            sessionStorage.removeItem("adminIdToken");
            window.google.accounts.id.renderButton(
                document.getElementById("google-btn"),
                { theme: "outline", size: "large" }
            );
            document.getElementById("admin-auth-msg").innerHTML = `<strong style='color:#ff4a4a'>Valid Admin clearance required.</strong>`;
            return;
        }
        
        authContainer.classList.add("hidden");
        
        try {
            const payload = JSON.parse(atob(adminIdToken.split('.')[1]));
            document.getElementById("logged-in-user").innerHTML = `Logged in as <strong style="color: #58a6ff;">${payload.email}</strong>`;
        } catch(e) { console.error("JWT Decode failed", e); }

        actionBar.classList.remove("hidden");
        logsView.classList.remove("hidden");
        
        // Initial Fetch
        loadLogs();
        
    } catch(e) {
        document.getElementById("admin-auth-msg").innerHTML = `<strong style='color:#ff4a4a'>Network connection failed.</strong>`;
    }
}

async function loadLogs(append = false) {
    if (!adminIdToken) return;
    
    try {
        const urlParams = new URLSearchParams();
        urlParams.append("limit", EVENTS_LIMIT);
        urlParams.append("offset", currentOffset);

        if (searchEventId.value.trim()) urlParams.append("event_id", searchEventId.value.trim());
        if (searchEventName.value.trim()) urlParams.append("event_name", searchEventName.value.trim());
        
        if (statusSelect.value) urlParams.append("status", statusSelect.value);
        if (sortSelect.value) urlParams.append("sort_by", sortSelect.value);
        
        if (dateTypeSelect.value) urlParams.append("date_filter_type", dateTypeSelect.value);
        if (dateMinInput.value && dateMaxInput.value) {
            urlParams.append("date_min", dateMinInput.value);
            urlParams.append("date_max", dateMaxInput.value);
        }
        
        const res = await fetch(`${API_BASE}/admin/logs?${urlParams.toString()}`, {
            headers: { "Authorization": `Bearer ${adminIdToken}` },
            cache: "no-store"
        });
        
        if (!res.ok) throw new Error("Fetch failed");
        
        const data = await res.json();
        
        if (!append) allLogs = [];
        allLogs = allLogs.concat(data);
        hasMoreEvents = data.length === EVENTS_LIMIT;

        const loadMoreContainer = document.getElementById("load-more-container");
        if (loadMoreBtn) loadMoreBtn.textContent = "Load More";
        
        if (hasMoreEvents) {
            if (loadMoreContainer) loadMoreContainer.classList.remove("hidden");
        } else {
            if (loadMoreContainer) loadMoreContainer.classList.add("hidden");
        }

        renderLogs();
    } catch(e) {
        document.getElementById("logs-list").innerHTML = "<p style='color: #ff4a4a;'>Failed to load running logs natively.</p>";
    }
}

function renderLogs() {
    const container = document.getElementById("logs-list");
    if (allLogs.length === 0) {
        container.innerHTML = "<p style='color: #aaa; font-size: 0.9rem;'>No running logs found matching filters.</p>";
        return;
    }

    container.innerHTML = allLogs.map(log => {
        const statusClass = `status-${log.status || 'PENDING'}`;
        
        return `
        <div class="log-card">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
                <h3 style="color: #4a90e2; margin: 0;">${log.event_name} <span style="font-size:0.75rem; color:#8b949e; font-weight:normal;">(${log.event_id})</span></h3>
                <span class="status-badge ${statusClass}">${log.status}</span>
            </div>
            
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 10px;">
                <div>
                    <p style="margin: 0 0 5px 0; font-size: 0.85rem; color: #8b949e;"><strong>Service:</strong> <code style="color: #c9d1d9;">${log.cloud_run_service_name}</code></p>
                    <p style="margin: 0 0 5px 0; font-size: 0.85rem; color: #8b949e;"><strong>URL:</strong> ${log.cloud_run_url && log.cloud_run_url !== 'PENDING' ? `<a href="${log.cloud_run_url}" target="_blank" style="color: #58a6ff;">${log.cloud_run_url}</a>` : '<span style="color: #6e7681;">Not Deployed</span>'}</p>
                </div>
                <div>
                    <p style="margin: 0 0 5px 0; font-size: 0.85rem; color: #8b949e;"><strong>Scheduled:</strong> ${log.scheduled_start_date} to ${log.scheduled_end_date}</p>
                    <p style="margin: 0 0 5px 0; font-size: 0.85rem; color: #8b949e;"><strong>Actual:</strong> ${log.actual_datetime_started ? log.actual_datetime_started.replace('T', ' ').substring(0, 16) : '--'} to ${log.actual_datetime_ended ? log.actual_datetime_ended.replace('T', ' ').substring(0, 16) : '--'}</p>
                </div>
            </div>
        </div>
        `;
    }).join('') + (!hasMoreEvents && allLogs.length > 0 ? `<p style="text-align: center; color: #aaa; font-size: 0.8rem; margin-top: 10px;">Loaded ${allLogs.length} running logs physically</p>` : '');
}

downloadLogsBtn?.addEventListener("click", () => {
    let qsParams = new URLSearchParams();
    
    if (searchEventId.value.trim()) qsParams.append("event_id", searchEventId.value.trim());
    if (searchEventName.value.trim()) qsParams.append("event_name", searchEventName.value.trim());
    
    if (statusSelect.value) qsParams.append("status", statusSelect.value);
    if (sortSelect.value) qsParams.append("sort_by", sortSelect.value);
    
    if (dateTypeSelect.value) qsParams.append("date_filter_type", dateTypeSelect.value);
    if (dateMinInput.value && dateMaxInput.value) {
        qsParams.append("date_min", dateMinInput.value);
        qsParams.append("date_max", dateMaxInput.value);
    }
    
    let qs = qsParams.toString();
    if (qs.length > 0 && !qs.startsWith("&")) qs = "?" + qs;

    downloadLogsBtn.textContent = "Compiling CSV Database Dump...";
    downloadLogsBtn.disabled = true;

    fetch(`${API_BASE}/admin/logs/export${qs}`, {
        headers: { "Authorization": `Bearer ${adminIdToken}` },
        cache: "no-store"
    })
    .then(r => {
        if (!r.ok) throw new Error("Download API Rejected");
        return r.json();
    })
    .then(targetLogs => {
        if (targetLogs.length === 0) return alert("No logs found to export!");

        const headers = ["Event ID", "Event Name", "Cloud Run Service", "Cloud Run URL", "Scheduled Start", "Scheduled End", "Actual Start", "Actual End", "Status"];
        const csvRows = [headers.join(",")];
        
        for (const log of targetLogs) {
            const row = [
                `"${log.event_id}"`,
                `"${log.event_name}"`,
                `"${log.cloud_run_service_name}"`,
                `"${log.cloud_run_url}"`,
                `"${log.scheduled_start_date}"`,
                `"${log.scheduled_end_date}"`,
                `"${log.actual_datetime_started}"`,
                `"${log.actual_datetime_ended}"`,
                `"${log.status}"`
            ];
            csvRows.push(row.join(","));
        }

        const csvString = csvRows.join("\\n");
        const blob = new Blob([csvString], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.setAttribute('hidden', '');
        a.setAttribute('href', url);
        a.setAttribute('download', 'running_logs_export.csv');
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    })
    .catch(e => {
        console.error(e);
        alert("Failed to export logging streams.");
    })
    .finally(() => {
        downloadLogsBtn.textContent = "Download CSV (Full Export)";
        downloadLogsBtn.disabled = false;
    });
});
