/* =====================================================
   PARKEASE ADMIN CONTROL DASHBOARD LOGIC
===================================================== */

const API_BASE = (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")
    ? `${window.location.protocol}//${window.location.hostname}:5000`
    : "https://parkease-backend.onrender.com";

// Admin state
const state = {
    token: localStorage.getItem("parkease_admin_token") || null,
    currentView: "overview",
    autoRefresh: true,
    refreshInterval: null,
    dashboardData: null,
    bookingsData: [],
    vehiclesData: [],
    statsData: null,
    iotData: null,
};

/* =====================================================
   API HELPER
===================================================== */
async function adminApi(endpoint, options = {}) {
    const headers = {
        "Content-Type": "application/json",
        ...options.headers,
    };

    if (state.token) {
        headers["Authorization"] = `Bearer ${state.token}`;
    }

    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            ...options,
            headers,
        });

        const data = await response.json();

        if (!response.ok) {
            if (response.status === 401 || response.status === 403) {
                // Auth failure -> prompt login
                showAdminLogin();
            }
            throw new Error(data.message || `HTTP ${response.status} error`);
        }

        return data;
    } catch (error) {
        console.error(`Admin API Error (${endpoint}):`, error);
        throw error;
    }
}

/* =====================================================
   AUTHENTICATION & INITIALIZATION
===================================================== */
const loginOverlay = document.getElementById("adminLoginOverlay");
const adminApp = document.getElementById("adminApp");
const loginForm = document.getElementById("adminLoginForm");

function showAdminLogin() {
    state.token = null;
    localStorage.removeItem("parkease_admin_token");
    loginOverlay.classList.remove("hidden");
    adminApp.classList.add("hidden");
    stopAutoRefresh();
}

function showAdminApp() {
    loginOverlay.classList.add("hidden");
    adminApp.classList.remove("hidden");
    startAutoRefresh();
    refreshCurrentView();
}

// Login Submit
if (loginForm) {
    loginForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const email = document.getElementById("adminEmail").value;
        const password = document.getElementById("adminPassword").value;
        const btn = document.getElementById("adminLoginBtn");

        btn.disabled = true;
        btn.textContent = "Authenticating...";

        try {
            const res = await adminApi("/api/admin/login", {
                method: "POST",
                body: JSON.stringify({ email, password }),
            });

            if (res.success && res.token) {
                state.token = res.token;
                localStorage.setItem("parkease_admin_token", res.token);
                showToast("Welcome to ParkEase Admin Portal");
                showAdminApp();
            } else {
                showToast(res.message || "Invalid admin credentials");
            }
        } catch (error) {
            showToast(error.message || "Admin login failed.");
        } finally {
            btn.disabled = false;
            btn.textContent = "Authenticate & Access Dashboard";
        }
    });
}

// Logout
const logoutBtn = document.getElementById("adminLogoutBtn");
if (logoutBtn) {
    logoutBtn.addEventListener("click", () => {
        showAdminLogin();
        showToast("Logged out of Admin Portal.");
    });
}

/* =====================================================
   VIEW NAVIGATION & SIDEBAR
===================================================== */
const navItems = document.querySelectorAll(".nav-item");
const views = document.querySelectorAll(".admin-view");
const pageTitle = document.getElementById("pageTitle");

navItems.forEach((item) => {
    item.addEventListener("click", () => {
        const viewTarget = item.getAttribute("data-view");
        switchView(viewTarget);
    });
});

function switchView(viewName) {
    state.currentView = viewName;

    // Update active nav button
    navItems.forEach((btn) => {
        if (btn.getAttribute("data-view") === viewName) {
            btn.classList.add("active");
            pageTitle.textContent = btn.querySelector("span:last-child").textContent;
        } else {
            btn.classList.remove("active");
        }
    });

    // Toggle view elements
    views.forEach((v) => {
        if (v.id === `view${capitalize(viewName)}`) {
            v.classList.remove("hidden");
            v.classList.add("active");
        } else {
            v.classList.add("hidden");
            v.classList.remove("active");
        }
    });

    // Close mobile sidebar if open
    document.getElementById("adminSidebar").classList.remove("open");

    refreshCurrentView();
}

function capitalize(str) {
    return str.charAt(0).toUpperCase() + str.slice(1).replace(/-([a-z])/g, (g) => g[1].toUpperCase());
}



/* =====================================================
   AUTO-REFRESH CONTROLS
===================================================== */
const autoRefreshToggle = document.getElementById("autoRefreshToggle");
const refreshBtn = document.getElementById("refreshBtn");
const btnRefreshFull = document.getElementById("btnRefreshFull");
const btnViewHardware = document.getElementById("btnViewHardware");

if (autoRefreshToggle) {
    autoRefreshToggle.addEventListener("change", (e) => {
        state.autoRefresh = e.target.checked;
        if (state.autoRefresh) {
            startAutoRefresh();
            showToast("Auto-refresh enabled (2s)");
        } else {
            stopAutoRefresh();
            showToast("Auto-refresh paused");
        }
    });
}

if (refreshBtn) {
    refreshBtn.addEventListener("click", () => {
        refreshCurrentView();
        showToast("Data refreshed.");
    });
}

if (btnRefreshFull) {
    btnRefreshFull.addEventListener("click", () => {
        refreshCurrentView();
        showToast("Full system sync triggered.");
    });
}

if (btnViewHardware) {
    btnViewHardware.addEventListener("click", () => {
        switchView("iot-status");
    });
}

const btnToggleEntrySensor = document.getElementById("btnToggleEntrySensor");
const btnClearEntrySensor = document.getElementById("btnClearEntrySensor");

if (btnToggleEntrySensor) {
    btnToggleEntrySensor.addEventListener("click", async () => {
        const waiting = btnToggleEntrySensor.dataset.waiting === "true";
        await simulateSensor(!waiting);
    });
}

if (btnClearEntrySensor) {
    btnClearEntrySensor.addEventListener("click", async () => {
        await simulateSensor(false);
    });
}

async function simulateSensor(vehicleWaiting) {
    try {
        const res = await adminApi("/api/admin/simulate-sensor", {
            method: "POST",
            body: JSON.stringify({ vehicle_waiting: vehicleWaiting })
        });
        if (res.success) {
            showToast(res.message);
            refreshCurrentView(true);
        }
    } catch (err) {
        showToast("Failed to simulate sensor trigger.");
    }
}


function startAutoRefresh() {
    stopAutoRefresh();
    if (state.autoRefresh) {
        state.refreshInterval = setInterval(() => {
            refreshCurrentView(true);
        }, 2000);
    }
}

function stopAutoRefresh() {
    if (state.refreshInterval) {
        clearInterval(state.refreshInterval);
        state.refreshInterval = null;
    }
}

/* =====================================================
   DATA FETCHING & RENDERING
===================================================== */
async function refreshCurrentView(silent = false) {
    if (!state.token) return;

    try {
        // Always refresh dashboard overview stats
        await fetchDashboardData();

        // View specific refresh
        if (state.currentView === "all-bookings") {
            await fetchBookingsData();
        } else if (state.currentView === "active-vehicles") {
            await fetchVehiclesData();
        } else if (state.currentView === "statistics") {
            await fetchStatisticsData();
        } else if (state.currentView === "iot-status") {
            await fetchIotStatusData();
        }

        const liveText = document.getElementById("liveStatusText");
        if (liveText) liveText.textContent = "Live Synced";

    } catch (error) {
        const liveText = document.getElementById("liveStatusText");
        if (liveText) liveText.textContent = "Sync Offline";
    }
}

/* 1. DASHBOARD DATA */
async function fetchDashboardData() {
    const data = await adminApi("/api/admin/dashboard");
    if (!data.success) return;

    state.dashboardData = data;

    // Render Stats
    const totalEl = document.getElementById("statTotalSlots");
    if (totalEl) totalEl.textContent = data.total_slots;

    const availEl = document.getElementById("statAvailableSlots");
    if (availEl) availEl.textContent = data.available_slots;

    const resEl = document.getElementById("statReservedSlots");
    if (resEl) resEl.textContent = data.reserved_slots;

    const occEl = document.getElementById("statOccupiedSlots");
    if (occEl) occEl.textContent = data.occupied_slots;

    const actBEl = document.getElementById("statActiveBookings");
    if (actBEl) actBEl.textContent = data.active_bookings_count;

    const actVEl = document.getElementById("statActiveVehicles");
    if (actVEl) actVEl.textContent = data.active_vehicles_count;

    const todayBEl = document.getElementById("statTodayBookings");
    if (todayBEl) todayBEl.textContent = data.today_bookings_count;

    const todayEEl = document.getElementById("statTodayExits");
    if (todayEEl) todayEEl.textContent = data.today_completed_exits_count;

    // Gate Movement
    const gateMove = document.getElementById("gateMovementState");
    if (gateMove) {
        gateMove.textContent = data.movement_state || "IDLE";
    }

    const entryVeh = document.getElementById("entryVehicleState");
    if (entryVeh) {
        entryVeh.textContent = data.entry_vehicle_waiting ? "WAITING (ACTIVE)" : "CLEAR";
        entryVeh.style.color = data.entry_vehicle_waiting ? "var(--admin-warning)" : "var(--admin-success)";
    }

    const pEntry = document.getElementById("pendingEntryId");
    if (pEntry) pEntry.textContent = data.pending_entry_booking_id || "None";

    const pExit = document.getElementById("pendingExitSlot");
    if (pExit) pExit.textContent = data.pending_exit_slot || "None";

    const lastUpdated = document.getElementById("lastUpdatedText");
    if (lastUpdated) {
        lastUpdated.textContent = `Updated: ${new Date().toLocaleTimeString()}`;
    }

    // Render Slots Grid
    renderSlotsGrid("overviewSlotsGrid", data.slots);
    renderSlotsGrid("slotsDetailGrid", data.slots);
}

function renderSlotsGrid(containerId, slots) {
    const container = document.getElementById(containerId);
    if (!container || !slots) return;

    container.innerHTML = slots.map((s) => {
        const statusClass = `status-${s.status}`;
        const vehicleText = s.vehicle_number ? s.vehicle_number : "—";
        const sensorText = s.sensor_status ? s.sensor_status.toUpperCase() : "EMPTY";

        let labelText = s.status ? s.status.toUpperCase() : "AVAILABLE";
        if (s.status === "reserved") labelText = "RESERVED (Waiting Entry)";
        else if (s.status === "occupied") labelText = "PARKED (Inside)";
        else if (s.status === "exiting") labelText = "EXITING";

        return `
            <div class="slot-card-admin ${statusClass}">
                <div class="slot-header-admin">
                    <span class="slot-number-badge">Slot ${s.slot}</span>
                    <span class="badge-status">${labelText}</span>
                </div>
                <div class="slot-body-admin">
                    <div class="info-row">
                        <span>Current Vehicle</span>
                        <strong>${vehicleText}</strong>
                    </div>
                    <div class="info-row">
                        <span>IR Sensor State</span>
                        <strong>${sensorText}</strong>
                    </div>
                </div>
            </div>
        `;
    }).join("");
}

/* 2. BOOKINGS DATA */
async function fetchBookingsData() {
    const searchVal = document.getElementById("bookingSearchInput")?.value || "";
    const filterVal = document.getElementById("bookingStatusFilter")?.value || "all";

    const data = await adminApi(`/api/admin/bookings?search=${encodeURIComponent(searchVal)}&status=${filterVal}`);
    if (!data.success) return;

    state.bookingsData = data.bookings;
    renderBookingsTable(data.bookings);
}

function formatDateDDMMYYYY(dateInput, includeTime = true) {
    if (!dateInput) return "—";
    const d = new Date(dateInput);
    if (isNaN(d.getTime())) return "—";

    const day = String(d.getDate()).padStart(2, '0');
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const year = d.getFullYear();

    if (!includeTime) {
        return `${day}/${month}/${year}`;
    }

    const timeStr = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true });
    return `${day}/${month}/${year}, ${timeStr}`;
}

function renderBookingsTable(bookings) {
    const tbody = document.getElementById("bookingsTableBody");
    if (!tbody) return;

    if (!bookings || bookings.length === 0) {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding: 2rem; color: var(--admin-text-muted);">No booking records found matching search/filter.</td></tr>`;
        return;
    }

    tbody.innerHTML = bookings.map((b) => {
        const createdDate = formatDateDDMMYYYY(b.created_at, true);
        const entryDate = formatDateDDMMYYYY(b.entry_time, true);
        const exitDate = formatDateDDMMYYYY(b.exit_time, true);

        let statusBadgeHTML = `<span class="badge-status status-${b.status}">${b.status}</span>`;
        if (b.status === "ACTIVE") {
            if (!b.entry_time) {
                statusBadgeHTML = `<span class="badge-status status-reserved">RESERVED (Waiting Entry)</span>`;
            } else {
                statusBadgeHTML = `<span class="badge-status status-occupied">PARKED (Inside)</span>`;
            }
        } else if (b.status === "COMPLETED") {
            statusBadgeHTML = `<span class="badge-status status-available">COMPLETED (Exited)</span>`;
        }

        return `
            <tr>
                <td><strong>${b.booking_id}</strong></td>
                <td>${b.user_name || "—"}</td>
                <td>${b.user_phone || "—"}<br><small style="color:var(--admin-text-muted);">${b.user_email || ""}</small></td>
                <td><strong style="font-family:var(--admin-font-mono);">${b.vehicle_number}</strong></td>
                <td>Slot S${b.slot}</td>
                <td>${statusBadgeHTML}</td>
                <td>${entryDate}</td>
                <td>${exitDate}</td>
                <td>${createdDate}</td>
            </tr>
        `;
    }).join("");
}

// Search & Filter event handlers
const searchInput = document.getElementById("bookingSearchInput");
const statusFilter = document.getElementById("bookingStatusFilter");

if (searchInput) searchInput.addEventListener("input", debounce(() => fetchBookingsData(), 300));
if (statusFilter) statusFilter.addEventListener("change", () => fetchBookingsData());

function debounce(func, delay) {
    let timer;
    return function (...args) {
        clearTimeout(timer);
        timer = setTimeout(() => func.apply(this, args), delay);
    };
}

/* 3. ACTIVE VEHICLES DATA */
async function fetchVehiclesData() {
    const data = await adminApi("/api/admin/vehicles");
    if (!data.success) return;

    state.vehiclesData = data.vehicles;
    renderVehiclesTable(data.vehicles);
}

function renderVehiclesTable(vehicles) {
    const tbody = document.getElementById("activeVehiclesTableBody");
    if (!tbody) return;

    if (!vehicles || vehicles.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding: 2rem; color: var(--admin-text-muted);">No vehicles are currently parked or waiting in reserved slots.</td></tr>`;
        return;
    }

    tbody.innerHTML = vehicles.map((v) => {
        const entryStr = v.entry_time ? formatDateDDMMYYYY(v.entry_time, true) : `<span style="color:var(--admin-warning);">Awaiting Gate Entry</span>`;
        const statusBadge = v.entry_time 
            ? `<span class="badge-status status-occupied">PARKED (Inside)</span>`
            : `<span class="badge-status status-reserved">WAITING ENTRY</span>`;

        return `
            <tr>
                <td><strong>${v.booking_id}</strong></td>
                <td><strong style="font-family:var(--admin-font-mono);">${v.vehicle_number}</strong></td>
                <td>${v.user_name || "—"}</td>
                <td>${v.user_phone || "—"}</td>
                <td>Slot S${v.slot}</td>
                <td>${entryStr}</td>
                <td>${statusBadge}</td>
            </tr>
        `;
    }).join("");
}

/* 4. STATISTICS DATA */
async function fetchStatisticsData() {
    const data = await adminApi("/api/admin/statistics");
    if (!data.success) return;

    state.statsData = data;

    // Meter & Totals
    const pct = data.utilization_percentage || 0;
    document.getElementById("utilizationPctText").textContent = `${pct}%`;
    document.getElementById("utilizationProgressBar").style.width = `${pct}%`;

    document.getElementById("statTotalLifetimeBookings").textContent = data.total_bookings_count;
    document.getElementById("statCompletedSessions").textContent = data.completed_sessions_count;

    // Daily Chart Bars
    renderDailyChart(data.daily_bookings);
}

function renderDailyChart(dailyData) {
    const container = document.getElementById("dailyChartContainer");
    if (!container || !dailyData) return;

    const maxCount = Math.max(...dailyData.map((d) => d.count), 5);

    container.innerHTML = dailyData.map((d) => {
        const heightPct = Math.round((d.count / maxCount) * 100);

        return `
            <div class="chart-bar-wrapper">
                <div class="chart-bar" style="height: ${Math.max(heightPct, 5)}%;" title="${d.count} bookings"></div>
                <span class="chart-label">${d.date}</span>
            </div>
        `;
    }).join("");
}

/* 5. HARDWARE & IOT DIAGNOSTICS */
async function fetchIotStatusData() {
    const data = await adminApi("/api/admin/iot-status");
    if (!data.success) return;

    state.iotData = data;

    // Sensors
    setSensorBadge("sensorEntryStatus", data.entry_sensor);
    setSensorBadge("sensorExitStatus", data.exit_sensor);

    if (data.slots_sensor_status) {
        setSensorBadge("sensorS1Status", data.slots_sensor_status.S1 || "EMPTY");
        setSensorBadge("sensorS2Status", data.slots_sensor_status.S2 || "EMPTY");
        setSensorBadge("sensorS3Status", data.slots_sensor_status.S3 || "EMPTY");
    }

    // Gate
    const gateText = document.getElementById("gateStateText");
    const gateIcon = document.getElementById("gateVisualIcon");

    if (data.gate_status === "OPEN") {
        if (gateText) gateText.textContent = "OPEN (90°)";
        if (gateIcon) gateIcon.textContent = "⛩️ (OPEN)";
    } else {
        if (gateText) gateText.textContent = "CLOSED (0°)";
        if (gateIcon) gateIcon.textContent = "⛩️";
    }

    const pingText = document.getElementById("iotLastPingText");
    if (pingText) {
        pingText.textContent = data.last_iot_update ? new Date(data.last_iot_update).toLocaleTimeString() : "No recent ping";
    }
}

function setSensorBadge(elementId, statusText) {
    const el = document.getElementById(elementId);
    if (!el) return;

    const text = statusText.toUpperCase();
    el.textContent = text;

    if (text === "OCCUPIED") {
        el.className = "sensor-badge active-occ";
    } else {
        el.className = "sensor-badge active-clr";
    }
}

/* =====================================================
   TOAST NOTIFICATION
===================================================== */
function showToast(msg) {
    const toast = document.getElementById("adminToast");
    if (!toast) return;

    toast.textContent = msg;
    toast.classList.remove("hidden");

    setTimeout(() => {
        toast.classList.add("hidden");
    }, 3000);
}

// Theme Toggle
const themeToggle = document.getElementById("themeToggleAdmin");
if (themeToggle) {
    themeToggle.addEventListener("click", () => {
        const currentTheme = document.body.getAttribute("data-theme");
        if (currentTheme === "light") {
            document.body.removeAttribute("data-theme");
            themeToggle.textContent = "🌙";
        } else {
            document.body.setAttribute("data-theme", "light");
            themeToggle.textContent = "☀️";
        }
    });
}

function initPasswordToggles() {
    document.querySelectorAll(".password-toggle-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            const input = btn.previousElementSibling || btn.parentElement.querySelector("input");
            if (input) {
                const isPassword = input.type === "password";
                input.type = isPassword ? "text" : "password";
                btn.textContent = isPassword ? "🙈" : "👁️";
                btn.setAttribute("aria-label", isPassword ? "Hide password" : "Show password");
            }
        });
    });
}

initPasswordToggles();

/* Mobile Sidebar Toggle & Backdrop */
window.toggleMobileSidebar = function(show) {
    const adminSidebar = document.getElementById("adminSidebar");
    const sidebarBackdrop = document.getElementById("sidebarBackdrop");
    if (!adminSidebar) return;
    
    const isCurrentlyOpen = adminSidebar.classList.contains("open");
    const shouldOpen = show !== undefined ? show : !isCurrentlyOpen;
    
    if (shouldOpen) {
        adminSidebar.classList.add("open");
        if (sidebarBackdrop) sidebarBackdrop.classList.add("active");
    } else {
        adminSidebar.classList.remove("open");
        if (sidebarBackdrop) sidebarBackdrop.classList.remove("active");
    }
};

document.addEventListener("click", (e) => {
    const toggleBtn = e.target.closest("#sidebarToggle");
    const closeBtn = e.target.closest("#closeSidebarBtn");
    const backdrop = e.target.closest("#sidebarBackdrop");
    const navItem = e.target.closest(".sidebar-nav .nav-item");

    if (toggleBtn) {
        e.preventDefault();
        e.stopPropagation();
        window.toggleMobileSidebar();
    } else if (closeBtn || backdrop) {
        window.toggleMobileSidebar(false);
    } else if (navItem && window.innerWidth <= 768) {
        window.toggleMobileSidebar(false);
    }
});

/* Check session on load */
if (state.token) {
    showAdminApp();
} else {
    showAdminLogin();
}
