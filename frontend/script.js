/* =====================================================
   PARKEASE - SMART PARKING
   COMPLETE FRONTEND JAVASCRIPT

   Frontend
       ↓
   Flask API
       ↓
   MySQL

   ESP32
       ↓
   Flask API
       ↓
   Entry IR status
       ↓
   Frontend
===================================================== */


/* =====================================================
   API CONFIGURATION
===================================================== */

// Auto-detect backend URL: use localhost for local dev, Render URL for production
const API_BASE_URL = (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")
    ? "http://127.0.0.1:5000"
    : "https://parkease-backend-cer9.onrender.com";


/* =====================================================
   API REQUEST HELPER
===================================================== */

async function requestApi(endpoint, options = {}) {
    const token = localStorage.getItem("parkease_token");
    const headers = {
        "Content-Type": "application/json",
        ...(options.headers || {})
    };

    if (token) {
        headers["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(
        `${API_BASE_URL}${endpoint}`,
        {
            ...options,
            headers
        }
    );

    let data = {};

    try {
        data = await response.json();
    } catch (error) {
        data = {};
    }

    if (!response.ok) {
        throw new Error(
            data.message || `Request failed (${response.status})`
        );
    }

    return data;
}



/* =====================================================
   DARK MODE
===================================================== */

const themeToggle =
    document.getElementById("themeToggle");


const savedTheme =
    localStorage.getItem("parkingTheme");


if (savedTheme === "dark") {

    document.body.classList.add("dark");

    if (themeToggle) {

        themeToggle.textContent = "☀️";

    }

}


if (themeToggle) {

    themeToggle.addEventListener(
        "click",
        function () {

            document.body.classList.toggle(
                "dark"
            );


            const darkMode =
                document.body.classList.contains(
                    "dark"
                );


            if (darkMode) {

                themeToggle.textContent =
                    "☀️";


                localStorage.setItem(
                    "parkingTheme",
                    "dark"
                );

            }

            else {

                themeToggle.textContent =
                    "🌙";


                localStorage.setItem(
                    "parkingTheme",
                    "light"
                );

            }

        }
    );

}


/* =====================================================
   DEFAULT APPLICATION STATE
===================================================== */

const defaultState = {

    slots: {

        1: {
            status: "available"
        },

        2: {
            status: "available"
        },

        3: {
            status: "available"
        }

    },


    booking: null,


    /*
       TRUE when Entry IR detects a vehicle.
    */

    vehicleWaiting: false,


    /*
       TRUE after backend authorizes entry.
    */

    entryAuthorized: false

};


/* =====================================================
   LOCAL STORAGE
===================================================== */

const STORAGE_KEY =
    "smartParkingDemo";


/* =====================================================
   LOAD SAVED STATE
===================================================== */

function loadState() {

    try {

        const saved =
            localStorage.getItem(
                STORAGE_KEY
            );


        if (saved) {

            const parsed =
                JSON.parse(saved);


            return {

                ...defaultState,

                ...parsed

            };

        }

    }

    catch (error) {

        console.error(
            "Unable to load saved state:",
            error
        );

    }


    return JSON.parse(
        JSON.stringify(
            defaultState
        )
    );
}


let state =
    loadState();


/* =====================================================
   SAVE STATE
===================================================== */

function saveState() {

    try {

        localStorage.setItem(
            STORAGE_KEY,
            JSON.stringify(state)
        );

    }

    catch (error) {

        console.error(
            "Unable to save state:",
            error
        );

    }

}


/* =====================================================
   STATUS LABEL
===================================================== */

function statusLabel(status) {

    switch (status) {

        case "available":
            return "AVAILABLE";

        case "reserved":
            return "RESERVED";

        case "occupied":
            return "OCCUPIED";

        case "exiting":
            return "EXITING";

        default:
            return "UNKNOWN";

    }

}


/* =====================================================
   STATUS DESCRIPTION
===================================================== */

function statusDescription(status) {

    switch (status) {

        case "available":
            return "Ready to reserve";

        case "reserved":
            return "Reserved by user";

        case "occupied":
            return "Vehicle detected";

        case "exiting":
            return "Vehicle exiting";

        default:
            return "";

    }

}


/* =====================================================
   RENDER COMPLETE UI
===================================================== */

function render() {

    const slots =
        Object.values(
            state.slots
        );


    /* -------------------------------------------------
       COUNTS
    ------------------------------------------------- */

    const available =
        slots.filter(
            slot =>
                slot.status ===
                "available"
        ).length;


    const reserved =
        slots.filter(
            slot =>
                slot.status ===
                "reserved"
        ).length;


    const occupied =
        slots.filter(
            slot =>
                slot.status ===
                "occupied"
        ).length;


    /* -------------------------------------------------
       STATISTICS
    ------------------------------------------------- */

    const availableCount =
        document.getElementById(
            "availableCount"
        );


    const reservedCount =
        document.getElementById(
            "reservedCount"
        );


    const occupiedCount =
        document.getElementById(
            "occupiedCount"
        );


    if (availableCount) {

        availableCount.textContent =
            available;

    }


    if (reservedCount) {

        reservedCount.textContent =
            reserved;

    }


    if (occupiedCount) {

        occupiedCount.textContent =
            occupied;

    }


    /* -------------------------------------------------
       SIDE AVAILABILITY
    ------------------------------------------------- */

    const sideAvailability =
        document.getElementById(
            "sideAvailability"
        );


    if (sideAvailability) {

        sideAvailability.textContent =
            `${available} / ${slots.length}`;

    }


    /* -------------------------------------------------
       HERO AVAILABLE COUNT
    ------------------------------------------------- */

    const heroAvailable =
        document.getElementById(
            "heroAvailable"
        );


    if (heroAvailable) {

        heroAvailable.textContent =
            available;

    }


    /* -------------------------------------------------
       HERO PROGRESS
    ------------------------------------------------- */

    const heroProgress =
        document.getElementById(
            "heroProgress"
        );


    if (heroProgress) {

        const total =
            slots.length || 1;


        const percentage =
            (available / total) * 100;


        heroProgress.style.width =
            `${percentage}%`;

    }


    /* -------------------------------------------------
       PARKING SLOT GRID
    ------------------------------------------------- */

    const slotGrid =
        document.getElementById(
            "slotGrid"
        );


    if (slotGrid) {

        slotGrid.innerHTML = "";


        Object.keys(state.slots)
            .sort(
                (a, b) =>
                    Number(a) -
                    Number(b)
            )
            .forEach(
                function (slotNumber) {

                    const slot =
                        state.slots[
                            slotNumber
                        ];


                    const card =
                        document.createElement(
                            "div"
                        );


                    card.className = `slot-card ${slot.status}`;

                    const vehicleTag = slot.vehicle_number ? slot.vehicle_number : (slot.status === 'available' ? 'Open Space' : 'In Use');
                    const badgeClass = `badge ${slot.status}`;

                    card.innerHTML = `
                        <div class="slot-top">
                            <span class="slot-name">Slot S${slotNumber}</span>
                            <span class="${badgeClass}">
                                <span class="badge-dot"></span>
                                ${statusLabel(slot.status)}
                            </span>
                        </div>

                        <div class="car-area">
                            <div class="bay-floor-marking">S${slotNumber}</div>
                            <div class="car ${slot.status}">
                                <div class="car-windshield"></div>
                                <div class="car-headlight left"></div>
                                <div class="car-headlight right"></div>
                                <div class="car-roof"></div>
                            </div>
                        </div>

                        <div class="slot-bottom">
                            <div class="slot-meta-info">
                                <span class="slot-description">${statusDescription(slot.status)}</span>
                                <small class="slot-vehicle-tag">${vehicleTag}</small>
                            </div>
                            ${slot.status === "available" ? `<button class="book-button" type="button">Reserve <span class="btn-arrow">→</span></button>` : `<span class="not-available">${statusLabel(slot.status)}</span>`}
                        </div>
                    `;

                    if (slot.status === "available") {
                        card.style.cursor = "pointer";
                        card.addEventListener("click", function () {
                            openBookingModal(slotNumber);
                        });
                    }

                    slotGrid.appendChild(card);
                }
            );

    }


    /* -------------------------------------------------
       BOOKING
    ------------------------------------------------- */

    updateBooking();


    /* -------------------------------------------------
       ENTRY PANEL
    ------------------------------------------------- */

    updateEntryPanel();

}


/* =====================================================
   REFRESH LIVE PARKING SLOTS
===================================================== */

async function refreshSlotsFromApi() {

    try {

        const data =
            await requestApi(
                "/api/slots"
            );


        if (
            !data ||
            !Array.isArray(
                data.slots
            )
        ) {

            console.error(
                "Invalid /api/slots response:",
                data
            );


            return;
        }


        const newSlots = {};


        /*
           IMPORTANT:

           Backend returns:

           {
               "slot": "S1",
               "status": "available"
           }

           NOT:

           {
               "slot_number": "S1"
           }
        */

        data.slots.forEach(
            function (slot) {

                const slotName =
                    String(
                        slot.slot
                    );


                /*
                   S1 → 1
                   S2 → 2
                   S3 → 3
                */

                const slotNumber =
                    Number(
                        slotName.replace(
                            /^S/i,
                            ""
                        )
                    );


                if (
                    Number.isInteger(
                        slotNumber
                    ) &&
                    slotNumber > 0
                ) {

                    newSlots[
                        slotNumber
                    ] = {

                        status:
                            String(
                                slot.status
                            ).toLowerCase()

                    };

                }

            }
        );


        /*
           Only update state when
           valid slot data was received.
        */

        if (
            Object.keys(
                newSlots
            ).length > 0
        ) {

            state.slots =
                newSlots;


            saveState();


            render();

        }

    }

    catch (error) {

        console.error(
            "Unable to refresh parking slots:",
            error
        );

    }

}


/* =====================================================
   READ REAL ENTRY IR STATUS
===================================================== */

async function refreshEntryStatus() {

    try {

        const data =
            await requestApi(
                "/api/entry-status"
            );


        if (
            data &&
            data.success
        ) {

            state.vehicleWaiting =
                Boolean(
                    data.vehicle_waiting
                );


            updateEntryPanel();

        }

    }

    catch (error) {

        console.error(
            "Unable to read Entry IR status:",
            error
        );


        /*
           If frontend cannot contact
           backend, don't pretend that
           a vehicle is waiting.
        */

        state.vehicleWaiting =
            false;


        updateEntryPanel();

    }

}


/* =====================================================
   ENTRY IR POLLING
===================================================== */

function startEntrySensorPolling() {

    /*
       Check immediately.
    */

    refreshEntryStatus();


    /*
       Then check every 1 second.
    */

    setInterval(
        refreshEntryStatus,
        1000
    );

}


/* =====================================================
   SLOT REFRESH POLLING
===================================================== */

function startSlotPolling() {

    setInterval(
        refreshSlotsFromApi,
        3000
    );

}


/* =====================================================
   VERIFY BOOKING WITH BACKEND

   If the stored booking has been completed or
   cancelled on the backend, clear localStorage
   so the user sees the correct state.
===================================================== */

async function verifyBookingWithBackend() {

    if (!state.booking) {
        return;
    }

    const bookingId =
        state.booking.id ||
        state.booking.booking_id;

    if (!bookingId) {
        return;
    }

    try {

        const data =
            await requestApi(
                `/api/booking-status?booking_id=${encodeURIComponent(bookingId)}`
            );

        if (!data || !data.success) {
            return;
        }

        /*
           Booking not found or no longer active.
        */

        if (
            !data.found ||
            data.status === "completed" ||
            data.status === "cancelled"
        ) {

            console.log(
                "Backend booking status:",
                data.status,
                "— clearing local state."
            );

            state.booking = null;
            state.entryAuthorized = false;

            saveState();
            render();
        }

    }

    catch (error) {

        console.error(
            "Unable to verify booking status:",
            error
        );

    }

}


function startBookingVerification() {

    verifyBookingWithBackend();

    setInterval(
        verifyBookingWithBackend,
        5000
    );

}


/* =====================================================
   UPDATE ENTRY PANEL
===================================================== */

function updateEntryPanel() {

    const entryPanel =
        document.getElementById(
            "entryPanel"
        );


    const enterParking =
        document.getElementById(
            "enterParking"
        );


    const statusTitle =
        document.getElementById(
            "entryStatusTitle"
        );


    const statusText =
        document.getElementById(
            "entryStatusText"
        );


    const statusDot =
        document.getElementById(
            "entryStatusDot"
        );


    if (!entryPanel) {

        return;

    }


    /* -------------------------------------------------
       NO BOOKING
    ------------------------------------------------- */

    if (!state.booking) {

        entryPanel.classList.add(
            "hidden"
        );


        if (enterParking) {

            enterParking.disabled =
                true;

        }


        return;

    }


    /* -------------------------------------------------
       BOOKING EXISTS
    ------------------------------------------------- */

    entryPanel.classList.remove(
        "hidden"
    );


    /* -------------------------------------------------
       ALREADY AUTHORIZED
    ------------------------------------------------- */

    if (state.entryAuthorized) {

        if (statusTitle) {

            statusTitle.textContent =
                "Entry authorized";

        }


        if (statusText) {

            statusText.textContent =
                "Your booking has been verified. Please proceed through the gate.";

        }


        if (statusDot) {

            statusDot.classList.add(
                "active"
            );

        }


        if (enterParking) {

            enterParking.disabled =
                true;

        }


        return;

    }


    /* -------------------------------------------------
       VEHICLE DETECTED
    ------------------------------------------------- */

    if (state.vehicleWaiting) {

        if (statusTitle) {

            statusTitle.textContent =
                "Vehicle detected";

        }


        if (statusText) {

            statusText.textContent =
                "Your vehicle is waiting at the entrance. Tap Enter Parking to verify.";

        }


        if (statusDot) {

            statusDot.classList.add(
                "active"
            );

        }


        if (enterParking) {

            enterParking.disabled =
                false;

        }


        return;

    }


    /* -------------------------------------------------
       NO VEHICLE
    ------------------------------------------------- */

    if (statusTitle) {

        statusTitle.textContent =
            "Ready for entry";

    }


    if (statusText) {

        statusText.textContent =
            "Reach the entry sensor, then tap Enter Parking.";

    }


    if (statusDot) {

        statusDot.classList.remove(
            "active"
        );

    }


    if (enterParking) {

        enterParking.disabled =
            true;

    }

}


/* =====================================================
   OPEN BOOKING MODAL
===================================================== */

function openBookingModal(
    slotNumber
) {

    const modal =
        document.getElementById(
            "modal"
        );


    const modalSlot =
        document.getElementById(
            "modalSlot"
        );


    const selectedSlot =
        document.getElementById(
            "selectedSlot"
        );


    if (!modal) {

        return;

    }


    if (modalSlot) {

        modalSlot.textContent =
            `S${slotNumber}`;

    }


    if (selectedSlot) {

        selectedSlot.value =
            slotNumber;

    }


    modal.classList.remove(
        "hidden"
    );

}


/* =====================================================
   CLOSE BOOKING MODAL
===================================================== */

function closeModal() {

    const modal =
        document.getElementById(
            "modal"
        );


    if (modal) {

        modal.classList.add(
            "hidden"
        );

    }

}


/* =====================================================
   CLOSE MODAL BUTTON
===================================================== */

const closeModalButton =
    document.getElementById(
        "closeModal"
    );


if (closeModalButton) {

    closeModalButton.addEventListener(
        "click",
        closeModal
    );

}


/* =====================================================
   BOOKING FORM
===================================================== */

const bookingForm =
    document.getElementById(
        "bookingForm"
    );


if (bookingForm) {

    bookingForm.addEventListener(
        "submit",
        async function (event) {

            event.preventDefault();


            /* -----------------------------------------
               FORM ELEMENTS
            ----------------------------------------- */

            const selectedSlot =
                document.getElementById(
                    "selectedSlot"
                );


            const userName =
                document.getElementById(
                    "userName"
                );


            const userPhone =
                document.getElementById(
                    "userPhone"
                );


            const vehicleNumberInput =
                document.getElementById(
                    "vehicleNumber"
                );


            const slot =
                selectedSlot
                    ? selectedSlot.value
                    : "";


            const name =
                userName
                    ? userName.value.trim()
                    : "";


            const phone =
                userPhone
                    ? userPhone.value.trim()
                    : "";


            const vehicleNumber =
                vehicleNumberInput
                    ? vehicleNumberInput.value
                        .trim()
                        .toUpperCase()
                    : "";


            /* -----------------------------------------
               VALIDATE NAME
            ----------------------------------------- */

            if (
                name.length < 2
            ) {

                showToast(
                    "Please enter your full name."
                );


                return;

            }


            /* -----------------------------------------
               VALIDATE PHONE
            ----------------------------------------- */

            if (
                !/^[0-9]{10}$/.test(
                    phone
                )
            ) {

                showToast(
                    "Enter a valid 10-digit mobile number."
                );


                return;

            }


            /* -----------------------------------------
               VALIDATE VEHICLE
            ----------------------------------------- */

            if (
                !/^[A-Z0-9 -]{5,12}$/.test(
                    vehicleNumber
                )
            ) {

                showToast(
                    "Enter a valid vehicle number."
                );


                return;

            }


            /* -----------------------------------------
               CHECK EXISTING BOOKING
            ----------------------------------------- */

            if (state.booking) {

                showToast(
                    "You already have an active booking."
                );


                closeModal();


                return;

            }


            /* -----------------------------------------
               CHECK LOCAL SLOT STATE
            ----------------------------------------- */

            if (
                !state.slots[slot] ||
                state.slots[slot].status !==
                    "available"
            ) {

                showToast(
                    "This parking slot is no longer available."
                );


                closeModal();


                await refreshSlotsFromApi();


                return;

            }


            try {

                /* -------------------------------------
                   SEND BOOKING TO FLASK
                ------------------------------------- */

                const data =
                    await requestApi(
                        "/api/book",
                        {

                            method: "POST",

                            body:
                                JSON.stringify({

                                    slot:
                                        `S${slot}`,

                                    name:
                                        name,

                                    phone:
                                        phone,

                                    vehicle_number:
                                        vehicleNumber

                                })

                        }
                    );


                /* -------------------------------------
                   CHECK RESPONSE
                ------------------------------------- */

                if (
                    !data ||
                    !data.booking
                ) {

                    throw new Error(
                        "Invalid booking response."
                    );

                }


                const booking =
                    data.booking;


                /* -------------------------------------
                   STORE BOOKING
                ------------------------------------- */

                state.booking = {

                    id:
                        booking.booking_id ||
                        booking.id,

                    booking_id:
                        booking.booking_id ||
                        booking.id,

                    slot:
                        slot,

                    name:
                        name,

                    phone:
                        phone,

                    vehicle_number:
                        booking.vehicle_number ||
                        vehicleNumber

                };


                /*
                   New booking means
                   entry has not been authorized.
                */

                state.entryAuthorized =
                    false;


                saveState();


                closeModal();


                /*
                   Get latest slot status
                   from backend.
                */

                await refreshSlotsFromApi();


                render();


                showToast(
                    `Slot S${slot} booked successfully.`
                );


                /* -------------------------------------
                   SCROLL TO BOOKING
                ------------------------------------- */

                const bookingSection =
                    document.getElementById(
                        "booking"
                    );


                if (bookingSection) {

                    setTimeout(
                        function () {

                            bookingSection.scrollIntoView(
                                {
                                    behavior:
                                        "smooth"
                                }
                            );

                        },
                        300
                    );

                }

            }

            catch (error) {

                console.error(
                    "Booking failed:",
                    error
                );


                showToast(
                    error.message ||
                    "Unable to create booking."
                );


                /*
                   Refresh because another
                   user may have booked the slot.
                */

                await refreshSlotsFromApi();

            }

        }
    );

}


/* =====================================================
   UPDATE MY BOOKING
===================================================== */

function updateBooking() {

    const heading =
        document.getElementById(
            "bookingHeading"
        );


    const text =
        document.getElementById(
            "bookingText"
        );


    const cancel =
        document.getElementById(
            "cancelBooking"
        );


    const bookingDetails =
        document.getElementById(
            "bookingDetails"
        );


    const bookingIdValue =
        document.getElementById(
            "bookingIdValue"
        );


    const bookingVehicleValue =
        document.getElementById(
            "bookingVehicleValue"
        );


    const bookingSlotValue =
        document.getElementById(
            "bookingSlotValue"
        );


    if (
        !heading ||
        !text ||
        !cancel
    ) {

        return;

    }


    /* -------------------------------------------------
       NO BOOKING
    ------------------------------------------------- */

    if (!state.booking) {

        heading.textContent =
            "No active reservation";


        text.textContent =
            "Choose an available slot to create your reservation.";


        cancel.classList.add(
            "hidden"
        );


        if (bookingDetails) {

            bookingDetails.classList.add(
                "hidden"
            );

        }


        return;

    }


    /* -------------------------------------------------
       ACTIVE BOOKING
    ------------------------------------------------- */

    heading.textContent =
        `Slot S${state.booking.slot} reserved`;


    if (state.entryAuthorized) {

        text.textContent =
            "Entry authorized. Please proceed through the gate.";

    }

    else {

        text.textContent =
            "Your reservation is active. Bring your vehicle to the entry sensor.";

    }


    cancel.classList.remove(
        "hidden"
    );


    if (bookingDetails) {

        bookingDetails.classList.remove(
            "hidden"
        );

    }


    if (bookingIdValue) {

        bookingIdValue.textContent =
            state.booking.id ||
            "—";

    }


    if (bookingVehicleValue) {

        bookingVehicleValue.textContent =
            state.booking.vehicle_number ||
            "—";

    }


    if (bookingSlotValue) {

        bookingSlotValue.textContent =
            `S${state.booking.slot}`;

    }

}


/* =====================================================
   CANCEL BOOKING
===================================================== */

const cancelBooking =
    document.getElementById(
        "cancelBooking"
    );


if (cancelBooking) {

    cancelBooking.addEventListener(
        "click",
        async function () {

            if (!state.booking) {

                return;

            }


            try {

                await requestApi(
                    "/api/cancel",
                    {

                        method: "POST",

                        body:
                            JSON.stringify({

                                booking_id:
                                    state.booking.id

                            })

                    }
                );


                state.booking =
                    null;


                state.vehicleWaiting =
                    false;


                state.entryAuthorized =
                    false;


                saveState();


                await refreshSlotsFromApi();


                render();


                showToast(
                    "Booking cancelled successfully."
                );

            }

            catch (error) {

                console.error(
                    "Cancellation failed:",
                    error
                );


                showToast(
                    error.message ||
                    "Unable to cancel booking."
                );

            }

        }
    );

}


/* =====================================================
   ENTER PARKING
===================================================== */

const enterParking =
    document.getElementById(
        "enterParking"
    );


if (enterParking) {

    enterParking.addEventListener(
        "click",
        async function () {

            /* -----------------------------------------
               BOOKING CHECK
            ----------------------------------------- */

            if (!state.booking) {

                showToast(
                    "Please make a booking first."
                );


                return;

            }


            /* -----------------------------------------
               VEHICLE CHECK
            ----------------------------------------- */

            if (!state.vehicleWaiting) {

                showToast(
                    "Please bring your vehicle to the entry gate."
                );


                return;

            }


            /* -----------------------------------------
               ALREADY AUTHORIZED
            ----------------------------------------- */

            if (state.entryAuthorized) {

                return;

            }


            /* -----------------------------------------
               DISABLE BUTTON
            ----------------------------------------- */

            enterParking.disabled =
                true;


            /* -----------------------------------------
               SHOW VERIFYING
            ----------------------------------------- */

            const statusTitle =
                document.getElementById(
                    "entryStatusTitle"
                );


            const statusText =
                document.getElementById(
                    "entryStatusText"
                );


            if (statusTitle) {

                statusTitle.textContent =
                    "Verifying...";

            }


            if (statusText) {

                statusText.textContent =
                    "Checking your booking and vehicle details.";

            }


            try {

                /* -------------------------------------
                   BACKEND AUTHORIZATION
                ------------------------------------- */

                const data =
                    await requestApi(
                        "/api/enter-parking",
                        {

                            method: "POST",

                            body:
                                JSON.stringify({

                                    booking_id:
                                        state.booking.id

                                })

                        }
                    );


                /* -------------------------------------
                   SUCCESS
                ------------------------------------- */

                if (
                    data &&
                    data.authorized
                ) {

                    state.entryAuthorized =
                        true;


                    saveState();


                    updateBooking();


                    updateEntryPanel();


                    showToast(
                        "Entry authorized. Please proceed through the gate."
                    );

                }

                else {

                    /*
                       Backend did not authorize.
                    */

                    state.entryAuthorized =
                        false;


                    showToast(
                        data.message ||
                        "Entry denied."
                    );


                    updateEntryPanel();

                }

            }

            catch (error) {

                console.error(
                    "Entry authorization failed:",
                    error
                );


                state.entryAuthorized =
                    false;


                showToast(
                    error.message ||
                    "Unable to authorize parking entry."
                );


                updateEntryPanel();

            }

        }
    );

}


/* =====================================================
   TOAST MESSAGE
===================================================== */

function showToast(message) {

    const toast =
        document.getElementById(
            "toast"
        );


    if (!toast) {

        console.log(
            message
        );


        return;

    }


    toast.textContent =
        message;


    toast.classList.remove(
        "hidden"
    );


    toast.classList.add(
        "show"
    );


    setTimeout(
        function () {

            toast.classList.remove(
                "show"
            );


            toast.classList.add(
                "hidden"
            );

        },
        3000
    );

}


/* =====================================================
   INITIALIZE PARKEASE
===================================================== */

/* =====================================================
   USER AUTHENTICATION LOGIC
===================================================== */

const userAuth = {
    token: localStorage.getItem("parkease_token") || null,
    user: null,
};

const navLoginBtn = document.getElementById("navLoginBtn");
const navRegisterBtn = document.getElementById("navRegisterBtn");
const navAccountBtn = document.getElementById("navAccountBtn");
const navLogoutBtn = document.getElementById("navLogoutBtn");

const forgotPasswordModal = document.getElementById("forgotPasswordModal");
const resetPasswordModal = document.getElementById("resetPasswordModal");

const openForgotPassword = document.getElementById("openForgotPassword");
const closeForgotPasswordModal = document.getElementById("closeForgotPasswordModal");
const closeResetPasswordModal = document.getElementById("closeResetPasswordModal");

const forgotSwitchToLogin = document.getElementById("forgotSwitchToLogin");
const resetSwitchToLogin = document.getElementById("resetSwitchToLogin");

const forgotPasswordForm = document.getElementById("forgotPasswordForm");
const resetPasswordForm = document.getElementById("resetPasswordForm");

const welcomeLanding = document.getElementById("welcomeLanding");
const dashboardContent = document.getElementById("dashboardContent");
const welcomeLoginBtn = document.getElementById("welcomeLoginBtn");
const welcomeRegisterBtn = document.getElementById("welcomeRegisterBtn");
const navAdminLink = document.querySelector(".nav-admin-link");

function updateAuthUI() {
    if (userAuth.user) {
        if (welcomeLanding) welcomeLanding.classList.add("hidden");
        if (dashboardContent) dashboardContent.classList.remove("hidden");

        if (navLoginBtn) navLoginBtn.classList.add("hidden");
        if (navRegisterBtn) navRegisterBtn.classList.add("hidden");
        if (navAccountBtn) {
            navAccountBtn.classList.remove("hidden");
            navAccountBtn.textContent = `👤 ${userAuth.user.name.split(" ")[0]}`;
        }
        if (navLogoutBtn) navLogoutBtn.classList.remove("hidden");

        // NO ADMIN LOGIN BUTTON inside authenticated user dashboard
        if (navAdminLink) {
            navAdminLink.classList.add("hidden");
            navAdminLink.style.display = "none";
        }

        const accName = document.getElementById("accName");
        const accEmail = document.getElementById("accEmail");
        const accPhone = document.getElementById("accPhone");
        const accRole = document.getElementById("accRole");

        if (accName) accName.textContent = userAuth.user.name;
        if (accEmail) accEmail.textContent = userAuth.user.email || "Not set";
        if (accPhone) accPhone.textContent = userAuth.user.phone;
        if (accRole) accRole.textContent = userAuth.user.role || "USER";

        const userName = document.getElementById("userName");
        const userPhone = document.getElementById("userPhone");

        if (userName) userName.value = userAuth.user.name;
        if (userPhone) userPhone.value = userAuth.user.phone;
    } else {
        if (welcomeLanding) welcomeLanding.classList.remove("hidden");
        if (dashboardContent) dashboardContent.classList.add("hidden");

        if (navLoginBtn) navLoginBtn.classList.remove("hidden");
        if (navRegisterBtn) navRegisterBtn.classList.remove("hidden");
        if (navAccountBtn) navAccountBtn.classList.add("hidden");
        if (navLogoutBtn) navLogoutBtn.classList.add("hidden");

        // Admin login accessible on unauthenticated welcome screen
        if (navAdminLink) {
            navAdminLink.classList.remove("hidden");
            navAdminLink.style.display = "inline-flex";
        }
    }
}

if (welcomeLoginBtn) welcomeLoginBtn.addEventListener("click", () => loginModal.classList.remove("hidden"));
if (welcomeRegisterBtn) welcomeRegisterBtn.addEventListener("click", () => registerModal.classList.remove("hidden"));


async function fetchUserProfile() {
    if (!userAuth.token) {
        updateAuthUI();
        return;
    }

    try {
        const data = await requestApi("/api/auth/me");
        if (data.success && data.user) {
            userAuth.user = data.user;
            if (data.active_booking) {
                state.booking = {
                    id: data.active_booking.booking_id,
                    booking_id: data.active_booking.booking_id,
                    slot: data.active_booking.slot.replace("S", ""),
                    name: data.active_booking.user_name,
                    phone: data.active_booking.user_phone,
                    vehicle_number: data.active_booking.vehicle_number
                };
                saveState();
                render();
            }
            updateAuthUI();
        } else {
            handleUserLogout();
        }
    } catch (error) {
        handleUserLogout();
    }
}

function handleUserLogout() {
    userAuth.token = null;
    userAuth.user = null;
    localStorage.removeItem("parkease_token");
    updateAuthUI();
    showToast("Logged out successfully.");
}

if (navLoginBtn) navLoginBtn.addEventListener("click", () => loginModal.classList.remove("hidden"));
if (navRegisterBtn) navRegisterBtn.addEventListener("click", () => registerModal.classList.remove("hidden"));
if (navAccountBtn) navAccountBtn.addEventListener("click", () => accountModal.classList.remove("hidden"));
if (navLogoutBtn) navLogoutBtn.addEventListener("click", handleUserLogout);
if (modalLogoutBtn) modalLogoutBtn.addEventListener("click", () => {
    accountModal.classList.add("hidden");
    handleUserLogout();
});

if (closeLoginModal) closeLoginModal.addEventListener("click", () => loginModal.classList.add("hidden"));
if (closeRegisterModal) closeRegisterModal.addEventListener("click", () => registerModal.classList.add("hidden"));
if (closeAccountModal) closeAccountModal.addEventListener("click", () => accountModal.classList.add("hidden"));
if (closeForgotPasswordModal) closeForgotPasswordModal.addEventListener("click", () => forgotPasswordModal.classList.add("hidden"));
if (closeResetPasswordModal) closeResetPasswordModal.addEventListener("click", () => resetPasswordModal.classList.add("hidden"));

if (switchToRegister) switchToRegister.addEventListener("click", (e) => {
    e.preventDefault();
    loginModal.classList.add("hidden");
    registerModal.classList.remove("hidden");
});

const mobileMenuBtn = document.getElementById("mobileMenu");
const navLinksContainer = document.querySelector(".nav-links");

if (mobileMenuBtn && navLinksContainer) {
    mobileMenuBtn.addEventListener("click", () => {
        navLinksContainer.classList.toggle("active");
    });
}

if (switchToLogin) switchToLogin.addEventListener("click", (e) => {
    e.preventDefault();
    registerModal.classList.add("hidden");
    loginModal.classList.remove("hidden");
});

if (openForgotPassword) openForgotPassword.addEventListener("click", (e) => {
    e.preventDefault();
    loginModal.classList.add("hidden");
    forgotPasswordModal.classList.remove("hidden");
});

if (forgotSwitchToLogin) forgotSwitchToLogin.addEventListener("click", (e) => {
    e.preventDefault();
    forgotPasswordModal.classList.add("hidden");
    loginModal.classList.remove("hidden");
});

if (resetSwitchToLogin) resetSwitchToLogin.addEventListener("click", (e) => {
    e.preventDefault();
    resetPasswordModal.classList.add("hidden");
    loginModal.classList.remove("hidden");
});

if (userLoginForm) {
    userLoginForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const email = document.getElementById("loginEmail").value;
        const password = document.getElementById("loginPassword").value;
        const btn = document.getElementById("btnLoginSubmit");

        btn.disabled = true;
        btn.textContent = "Signing in...";

        try {
            const data = await requestApi("/api/auth/login", {
                method: "POST",
                body: JSON.stringify({ email, password })
            });

            if (data.success && data.token) {
                userAuth.token = data.token;
                userAuth.user = data.user;
                localStorage.setItem("parkease_token", data.token);
                loginModal.classList.add("hidden");
                updateAuthUI();
                await fetchUserProfile();
                showToast(`Welcome back, ${data.user.name}!`);
            }
        } catch (error) {
            showToast(error.message || "Login failed.");
        } finally {
            btn.disabled = false;
            btn.textContent = "Sign In";
        }
    });
}

if (userRegisterForm) {
    userRegisterForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const name = document.getElementById("regName").value;
        const email = document.getElementById("regEmail").value;
        const phone = document.getElementById("regPhone").value;
        const password = document.getElementById("regPassword").value;
        const confirm_password = document.getElementById("regConfirmPassword").value;
        const btn = document.getElementById("btnRegisterSubmit");

        btn.disabled = true;
        btn.textContent = "Creating Account...";

        try {
            const data = await requestApi("/api/auth/register", {
                method: "POST",
                body: JSON.stringify({ name, email, phone, password, confirm_password })
            });

            if (data.success) {
                // REGISTRATION DOES NOT AUTOMATICALLY LOG IN THE USER
                registerModal.classList.add("hidden");
                showToast(data.message || "Registration successful. Please login to continue.");
                
                const loginEmail = document.getElementById("loginEmail");
                if (loginEmail) loginEmail.value = email;

                loginModal.classList.remove("hidden");
            }
        } catch (error) {
            showToast(error.message || "Registration failed.");
        } finally {
            btn.disabled = false;
            btn.textContent = "Register Account";
        }
    });
}

if (forgotPasswordForm) {
    forgotPasswordForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const email = document.getElementById("forgotEmail").value;
        const btn = document.getElementById("btnForgotSubmit");

        btn.disabled = true;
        btn.textContent = "Sending...";

        try {
            const data = await requestApi("/api/auth/forgot-password", {
                method: "POST",
                body: JSON.stringify({ email })
            });

            forgotPasswordModal.classList.add("hidden");
            showToast(data.message || "If an account exists for this email, password reset instructions have been sent.");

            if (data.reset_token) {
                const resetTokenInput = document.getElementById("resetToken");
                if (resetTokenInput) resetTokenInput.value = data.reset_token;
            }
            resetPasswordModal.classList.remove("hidden");
        } catch (error) {
            showToast(error.message || "Request failed.");
        } finally {
            btn.disabled = false;
            btn.textContent = "Send Reset Link";
        }
    });
}

if (resetPasswordForm) {
    resetPasswordForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const token = document.getElementById("resetToken").value;
        const new_password = document.getElementById("resetNewPassword").value;
        const confirm_password = document.getElementById("resetConfirmPassword").value;
        const btn = document.getElementById("btnResetSubmit");

        if (new_password !== confirm_password) {
            showToast("Passwords do not match.");
            return;
        }

        btn.disabled = true;
        btn.textContent = "Resetting Password...";

        try {
            const data = await requestApi("/api/auth/reset-password", {
                method: "POST",
                body: JSON.stringify({ token, new_password, confirm_password })
            });

            if (data.success) {
                resetPasswordModal.classList.add("hidden");
                showToast(data.message || "Password reset successful. Please login with your new password.");
                loginModal.classList.remove("hidden");
            }
        } catch (error) {
            showToast(error.message || "Password reset failed.");
        } finally {
            btn.disabled = false;
            btn.textContent = "Reset Password";
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

/* =====================================================
   INITIALIZE PARKEASE
===================================================== */

async function initializeParkEase() {

    initPasswordToggles();

    render();

    await fetchUserProfile();

    await refreshSlotsFromApi();

    await verifyBookingWithBackend();

    startEntrySensorPolling();

    startSlotPolling();

    startBookingVerification();

    updateBooking();

    updateEntryPanel();

}


/* =====================================================
   START APPLICATION
===================================================== */

initializeParkEase();