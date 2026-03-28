const API_BASE = "/api";

const setupEventName = document.getElementById("setup-event-name");
const setupStartDate = document.getElementById("setup-start-date");
const setupEndDate = document.getElementById("setup-end-date");
const setupLanguage = document.getElementById("setup-language");
const setupCountry = document.getElementById("setup-country");
const setupCoursesList = document.getElementById("setup-courses-list");
const createEventBtn = document.getElementById("create-event-btn");

const showCreateFormBtn = document.getElementById("show-create-form-btn");
const cancelCreateBtn = document.getElementById("cancel-create-btn");
const downloadEventsBtn = document.getElementById("download-events-btn");
const adminConfigContainer = document.getElementById("admin-config-container");
const adminActionBar = document.getElementById("admin-action-bar");

const dashboardView = document.getElementById("dashboard-view");
const usersView = document.getElementById("users-view");
const navDashboardBtn = document.getElementById("nav-dashboard-btn");
const navUsersBtn = document.getElementById("nav-users-btn");

const addAdminBtn = document.getElementById("add-admin-btn");

let adminIdToken = null;
let allLoadedEvents = [];
let isSuperAdmin = false;
let selectedEventCourses = new Set();

// Toggles for SPA routing
const countries = [
    "United States", "Canada", "Mexico", "Brazil",
    "Antigua and Barbuda", "Argentina", "Bahamas", "Barbados", "Belize", "Bolivia", 
    "Chile", "Colombia", "Costa Rica", "Cuba", "Dominica", "Dominican Republic", 
    "Ecuador", "El Salvador", "Grenada", "Guatemala", "Guyana", "Haiti", 
    "Honduras", "Jamaica", "Nicaragua", "Panama", "Paraguay", "Peru", 
    "Saint Kitts and Nevis", "Saint Lucia", "Saint Vincent and the Grenadines", 
    "Suriname", "Trinidad and Tobago", "Uruguay", "Venezuela"
];
const countryDropdown = document.getElementById("country-combobox-dropdown");

function renderCountryDropdown(filter = "") {
    if (!countryDropdown) return;
    countryDropdown.innerHTML = "";
    const filtered = countries.filter(c => c.toLowerCase().includes(filter.toLowerCase()));
    
    if (filtered.length === 0) {
        countryDropdown.style.display = "none";
        return;
    }

    filtered.forEach(c => {
        const div = document.createElement("div");
        div.textContent = c;
        div.style.padding = "10px 15px";
        div.style.cursor = "pointer";
        div.style.color = "#c9d1d9";
        div.style.borderBottom = "1px solid rgba(255,255,255,0.05)";
        
        div.onmouseover = () => { div.style.background = "rgba(88, 166, 255, 0.2)"; div.style.color = "white"; };
        div.onmouseout = () => { div.style.background = "transparent"; div.style.color = "#c9d1d9"; };
        
        div.onclick = () => {
            setupCountry.value = c;
            countryDropdown.style.display = "none";
        };
        countryDropdown.appendChild(div);
    });
}

if (setupCountry && countryDropdown) {
    setupCountry.addEventListener("focus", () => {
        countryDropdown.style.display = "block";
        renderCountryDropdown(setupCountry.value);
    });

    setupCountry.addEventListener("input", () => {
        countryDropdown.style.display = "block";
        renderCountryDropdown(setupCountry.value);
    });

    document.addEventListener("click", (e) => {
        if (e.target !== setupCountry && e.target !== countryDropdown && !countryDropdown.contains(e.target)) {
            countryDropdown.style.display = "none";
        }
    });
}

navDashboardBtn?.addEventListener("click", () => {
    dashboardView.classList.remove("hidden");
    usersView.classList.add("hidden");
    navDashboardBtn.style.background = "#0969da";
    navUsersBtn.style.background = "#21262d";
});

navUsersBtn?.addEventListener("click", () => {
    dashboardView.classList.add("hidden");
    usersView.classList.remove("hidden");
    navDashboardBtn.style.background = "#21262d";
    navUsersBtn.style.background = "#0969da";
});

const navCoursesBtn = document.getElementById("nav-courses-btn");
navCoursesBtn?.addEventListener("click", () => {
    window.location.href = "courses.html";
});

async function initAdminAuth() {
    try {
        const res = await fetch(`${API_BASE}/config`);
        const config = await res.json();
        
        if (!config.google_client_id) {
            document.getElementById("admin-auth-msg").innerHTML = "<strong style='color:#ff4a4a'>Google Client ID is missing.</strong> Please add GOOGLE_CLIENT_ID to your backend .env file.";
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
        
        if (!authRes.ok) {
            sessionStorage.removeItem("adminIdToken");
            window.google.accounts.id.renderButton(
                document.getElementById("google-btn"),
                { theme: "outline", size: "large" }
            );
            return;
        }
        
        document.getElementById("admin-auth-container").classList.add("hidden");
        
        try {
            const payload = JSON.parse(atob(adminIdToken.split('.')[1]));
            document.getElementById("logged-in-user").innerHTML = `Logged in as <strong style="color: #58a6ff;">${payload.email}</strong>`;
        } catch(e) { console.error("JWT Decode failed", e); }

        adminActionBar.classList.remove("hidden");
        dashboardView.classList.remove("hidden");
        navDashboardBtn.style.background = "#0969da";
        
        loadPastEvents();
        loadAdminsIfAuthorized();
    } catch(e) {
        document.getElementById("admin-auth-msg").innerHTML = `<strong style='color:#ff4a4a'>Network connection failed.</strong>`;
    }
}

showCreateFormBtn.addEventListener("click", () => {
    adminConfigContainer.classList.remove("hidden");
});

cancelCreateBtn.addEventListener("click", () => {
    adminConfigContainer.classList.add("hidden");
});

const eventCourseSearchInput = document.getElementById("event-course-search-input");
const eventCourseSearchBtn = document.getElementById("event-course-search-btn");

eventCourseSearchBtn?.addEventListener("click", () => {
    const q = eventCourseSearchInput.value.trim();
    loadAdminWorkshops(q);
});

eventCourseSearchInput?.addEventListener("keypress", (e) => {
    if (e.key === "Enter") eventCourseSearchBtn.click();
});

window.toggleCourseSelection = function(courseId, isChecked) {
    if (isChecked) {
        selectedEventCourses.add(courseId);
    } else {
        selectedEventCourses.delete(courseId);
    }
};

async function loadAdminWorkshops(queryStr = "") {
    try {
        const urlParams = new URLSearchParams();
        if (queryStr) urlParams.append("q", queryStr);
        
        const response = await fetch(`${API_BASE}/workshops?${urlParams.toString()}`, {
            headers: { "Authorization": `Bearer ${adminIdToken}` }
        });
        if (!response.ok) return;
        
        const allAvailableWorkshops = await response.json();
        
        if (allAvailableWorkshops.length === 0) {
            setupCoursesList.innerHTML = "<p style='color: #aaa; font-size: 0.9rem; margin: 0;'>No matching published courses found.</p>";
            return;
        }

        setupCoursesList.innerHTML = allAvailableWorkshops.map(w => {
            const isChecked = selectedEventCourses.has(w.id) ? "checked" : "";
            return `<label style="display: block; margin-bottom: 8px; color: white;">
                <input type="checkbox" name="admin-course" value="${w.id}" ${isChecked} onchange="toggleCourseSelection('${w.id}', this.checked)"> 
                ${w.name} <span style="font-size: 0.75rem; color: #8b949e;">(${w.id})</span>
            </label>`;
        }).join('');
    } catch (error) {
        console.error("Failed to load workshops:", error);
    }
}

async function loadAdminsIfAuthorized() {
    if (!adminIdToken) return;
    try {
        const res = await fetch(`${API_BASE}/admin/users`, {
            headers: { "Authorization": `Bearer ${adminIdToken}` },
            cache: "no-store"
        });
        if (res.status === 403) return; // Silent return for standard admins
        
        isSuperAdmin = true;
        const users = await res.json();
        
        // Append SuperAdmin Badge
        const userLabel = document.getElementById("logged-in-user");
        if (userLabel && !userLabel.innerHTML.includes("SuperAdmin")) {
            userLabel.innerHTML += ` <span style="font-size: 0.8rem; color: #f85149; background: rgba(255,255,255,0.1); padding: 2px 6px; border-radius: 4px; margin-left: 5px; vertical-align: middle;">SuperAdmin</span>`;
        }

        // Show superadmin features
        document.getElementById("nav-users-btn")?.classList.remove("hidden");
        document.getElementById("nav-courses-btn")?.classList.remove("hidden");
        document.getElementById("superadmin-event-filters")?.classList.remove("hidden");
        
        // Refresh event rendering to strip top 5 limit implicitly since they are now superadmin
        if (allLoadedEvents.length > 0) {
            renderPastEvents();
        }

        const container = document.getElementById("admins-list");
        container.innerHTML = users.map(u => `
            <div style="display: flex; justify-content: space-between; align-items: center; background: rgba(0,0,0,0.3); padding: 10px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.05);">
                <div>
                    <strong style="color: #e6edf3;">${u.email}</strong>
                    <span style="font-size: 0.8rem; color: ${u.role === 'superadmin' ? '#f85149' : '#58a6ff'}; margin-left: 8px; padding: 2px 6px; background: rgba(255,255,255,0.1); border-radius: 4px;">${u.role}</span>
                </div>
                <button onclick="removeAdmin('${u.email}')" class="text-btn" style="color: #ff4a4a; font-size: 0.9rem;">Remove</button>
            </div>
        `).join('');
    } catch(e) {
        console.error(e);
    }
}

window.removeAdmin = async function(email) {
    if (!confirm(`Revoke access for ${email}?`)) return;
    try {
        const res = await fetch(`${API_BASE}/admin/users/${email}`, {
            method: "DELETE",
            headers: { "Authorization": `Bearer ${adminIdToken}` }
        });
        const data = await res.json();
        if (res.ok) {
            loadAdminsIfAuthorized();
        } else {
            alert(data.detail);
        }
    } catch(e) {
        alert("Network error.");
    }
};

addAdminBtn?.addEventListener("click", async () => {
    const email = document.getElementById("new-admin-email").value.trim();
    const role = document.getElementById("new-admin-role").value;
    if (!email) return alert("Enter an email address.");
    
    try {
        addAdminBtn.textContent = "...";
        addAdminBtn.disabled = true;
        const res = await fetch(`${API_BASE}/admin/users`, {
            method: "POST",
            headers: { 
                "Authorization": `Bearer ${adminIdToken}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ email, role })
        });
        const data = await res.json();
        if (res.ok) {
            document.getElementById("new-admin-email").value = "";
            loadAdminsIfAuthorized();
        } else {
            alert(data.detail);
        }
    } catch(e) {
        alert("Network error.");
    } finally {
        addAdminBtn.textContent = "Invite";
        addAdminBtn.disabled = false;
    }
});

window.deleteEvent = async function(eventId) {
    if (!confirm(`Are you sure you want to permanently delete "${eventId}"? This cannot be undone.`)) return;
    try {
        const res = await fetch(`${API_BASE}/admin/events/${eventId}`, {
            method: "DELETE",
            headers: { "Authorization": `Bearer ${adminIdToken}` }
        });
        const data = await res.json();
        if (res.ok) {
            loadPastEvents();
        } else {
            alert(data.detail);
        }
    } catch(e) {
        alert("Network error.");
    }
};

document.getElementById("apply-filters-btn")?.addEventListener("click", () => renderPastEvents());

document.getElementById("clear-filters-btn")?.addEventListener("click", () => {
    document.getElementById("filter-start-date").value = "";
    document.getElementById("filter-end-date").value = "";
    document.getElementById("filter-creator").value = "";
    renderPastEvents();
});

function renderPastEvents() {
    const container = document.getElementById("past-events-list");
    let filteredEvents = allLoadedEvents;

    if (isSuperAdmin) {
        const startDateStr = document.getElementById("filter-start-date").value;
        const endDateStr = document.getElementById("filter-end-date").value;
        const creatorEmail = document.getElementById("filter-creator").value.trim().toLowerCase();

        if (startDateStr) {
            const startD = new Date(startDateStr);
            filteredEvents = filteredEvents.filter(e => new Date(e.start_date) >= startD);
        }
        if (endDateStr) {
            const endD = new Date(endDateStr);
            filteredEvents = filteredEvents.filter(e => new Date(e.end_date) <= endD);
        }
        if (creatorEmail) {
            filteredEvents = filteredEvents.filter(e => e.createdBy && e.createdBy.toLowerCase().includes(creatorEmail));
        }
    } else {
        filteredEvents = filteredEvents.slice(0, 5);
    }
    
    if (filteredEvents.length === 0) {
        container.innerHTML = "<p style='color: #aaa; font-size: 0.9rem;'>No matching events found.</p>";
        return;
    }

    container.innerHTML = filteredEvents.map(e => `
        <div style="background: rgba(13, 17, 23, 0.5); padding: 12px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.1); text-align: left; position: relative;">
            <button onclick="deleteEvent('${e.id}')" style="position: absolute; top: 12px; right: 12px; background: none; border: none; color: #ff4a4a; cursor: pointer; font-size: 1.2rem;" title="Delete Event">🗑️</button>
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 5px;">
                <h3 style="color: #4a90e2; margin: 0; padding-right: 30px;">${e.event_name} <span style="font-size:0.75rem; color:#8b949e; font-weight:normal;">(${e.id})</span></h3>
                <span class="status-badge status-${e.status || 'SCHEDULED'}" style="margin-right: 35px;">${e.status || 'SCHEDULED'}</span>
            </div>
            <p style="margin: 0 0 2px 0; font-size: 0.85rem; color: #e6edf3;"><strong>Created By:</strong> ${e.createdBy || 'Unknown'}</p>
            <p style="margin: 0 0 2px 0; font-size: 0.85rem; color: #e6edf3;"><strong>Dates:</strong> ${e.start_date} to ${e.end_date}</p>
            <p style="margin: 0 0 2px 0; font-size: 0.85rem; color: #e6edf3;"><strong>Courses:</strong> ${e.courses.join(", ")}</p>
            <p style="margin: 0 0 2px 0; font-size: 0.85rem; color: #e6edf3;"><strong>Location:</strong> ${e.language}-${e.country}</p>
            <p style="margin: 0; font-size: 0.85rem; color: #e6edf3;"><strong>URL:</strong> <a href="https://vta-${e.id}.gca-americas.dev" target="_blank" style="color: #58a6ff;">https://vta-${e.id}.gca-americas.dev</a></p>
        </div>
    `).join('') + ((!isSuperAdmin && allLoadedEvents.length > 5) ? `<p style="text-align: center; color: #aaa; font-size: 0.8rem; margin-top: 10px; grid-column: 1 / -1;">Showing 5 of ${allLoadedEvents.length} total events</p>` : '');
}

async function loadPastEvents() {
    if (!adminIdToken) return;

    try {
        const response = await fetch(`${API_BASE}/admin/events`, {
            headers: { "Authorization": `Bearer ${adminIdToken}` },
            cache: "no-store"
        });
        const data = await response.json();
        const container = document.getElementById("past-events-list");

        if (!response.ok) {
            container.innerHTML = `<p style='color: #ff4a4a; font-size: 0.9rem;'>DB Error: ${data.detail || 'Failed to connect'}</p>`;
            return;
        }

        allLoadedEvents = data;
        renderPastEvents();
        
    } catch (e) {
        console.error(e);
        document.getElementById("past-events-list").innerHTML = "<p style='color: #ff4a4a; font-size: 0.9rem;'>Connection Timeout. Are you sure you whitelisted your Wi-Fi IP in Google Cloud SQL?</p>";
    }
}

downloadEventsBtn?.addEventListener("click", () => {
    let targetEvents = allLoadedEvents;
    
    if (!isSuperAdmin) {
        const sixMonthsAgo = new Date();
        sixMonthsAgo.setMonth(sixMonthsAgo.getMonth() - 6);
        targetEvents = allLoadedEvents.filter(e => {
            const eventDate = new Date(e.start_date);
            return eventDate >= sixMonthsAgo;
        });
    }

    if (targetEvents.length === 0) return alert("No events to download!");

    const headers = ["Event ID", "Event Name", "Start Date", "End Date", "Language", "Country", "Created By", "Courses"];
    const csvRows = [headers.join(",")];
    
    for (const e of targetEvents) {
        const row = [
            `"${e.id}"`,
            `"${e.event_name}"`,
            `"${e.start_date}"`,
            `"${e.end_date}"`,
            `"${e.language}"`,
            `"${e.country}"`,
            `"${e.createdBy}"`,
            `"${e.courses.join("; ")}"`
        ];
        csvRows.push(row.join(","));
    }

    const csvString = csvRows.join("\n");
    const blob = new Blob([csvString], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.setAttribute('hidden', '');
    a.setAttribute('href', url);
    a.setAttribute('download', isSuperAdmin ? 'all_events_export.csv' : 'events_last_6_months.csv');
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
});

createEventBtn.addEventListener("click", async () => {
    const eventName = setupEventName.value.trim();
    const startDate = setupStartDate.value;
    const endDate = setupEndDate.value;
    const language = setupLanguage.value.trim() || "en";
    const country = setupCountry.value.trim() || "US";

    const courses = Array.from(selectedEventCourses);

    if (!eventName || !startDate || !endDate) return alert("Please fill in the Event Name and Dates.");
    if (courses.length === 0) return alert("Please select at least 1 course.");
    if (courses.length > 5) return alert("Please select a maximum of 5 courses.");

    createEventBtn.disabled = true;
    createEventBtn.textContent = "Saving...";

    const headers = { "Content-Type": "application/json" };
    if (adminIdToken) {
        headers["Authorization"] = `Bearer ${adminIdToken}`;
    }

    try {
        const response = await fetch(`${API_BASE}/admin/events`, {
            method: "POST",
            headers: headers,
            body: JSON.stringify({
                event_name: eventName,
                start_date: startDate,
                end_date: endDate,
                language: language,
                country: country,
                courses: courses
            })
        });

        const data = await response.json();
        if (response.ok) {
            setupEventName.value = "";
            setupStartDate.value = "";
            setupEndDate.value = "";
            setupLanguage.value = "";
            setupCountry.value = "";
            selectedEventCourses.clear();
            setupCoursesList.innerHTML = "<p style='color: #aaa; font-size: 0.9rem; margin: 0;'>Perform a search to load available courses.</p>";
            
            const targetUrl = `https://vta-${data.event_id}.gca-americas.dev`;
            alert(`✅ Event Created Successfully!\n\nThe automated Cloud Build pipeline is now provisioning your ephemeral architecture.\n\nYour service will become available at:\n${targetUrl}`);
            
            adminConfigContainer.classList.add("hidden");
            showCreateFormBtn.classList.remove("hidden");
            
            loadPastEvents();
        } else {
            alert(`Error: ${data.detail || 'Internal Server Error'}`);
        }
    } catch (e) {
        alert("Server error configuring the event.");
    } finally {
        createEventBtn.disabled = false;
        createEventBtn.textContent = "Schedule Event";
    }
});

initAdminAuth();
