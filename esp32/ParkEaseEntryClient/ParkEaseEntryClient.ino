#include <ArduinoJson.h>
#include <ESP32Servo.h>
#include <HTTPClient.h>
#include <WiFi.h>
#include "secrets.h"

// ============================================================
// PIN CONFIGURATION
// ============================================================

constexpr int ENTRY_IR_PIN = 18;
constexpr int EXIT_IR_PIN = 19;

constexpr int SLOT_1_IR_PIN = 21;
constexpr int SLOT_2_IR_PIN = 22;
constexpr int SLOT_3_IR_PIN = 23;

constexpr int SERVO_PIN = 25;


// Set to true if your IR sensors output HIGH when obstacle is detected (Active HIGH).
// Set to false if your IR sensors output LOW when obstacle is detected (Active LOW - standard FC-51).
constexpr bool INVERT_SENSOR_LOGIC = false;

constexpr int SENSOR_ACTIVE = INVERT_SENSOR_LOGIC ? HIGH : LOW;
constexpr int SENSOR_CLEAR = INVERT_SENSOR_LOGIC ? LOW : HIGH;


// ============================================================
// GATE CONFIGURATION
// ============================================================

constexpr int GATE_CLOSED_ANGLE = 0;
constexpr int GATE_OPEN_ANGLE = 90;

constexpr unsigned long GATE_MAX_OPEN_MS = 10000;


// ============================================================
// NETWORK / POLLING
// ============================================================

constexpr unsigned long WIFI_RETRY_MS = 5000;

constexpr unsigned long ENTRY_REPORT_MS = 500;
constexpr unsigned long SLOT_REPORT_MS = 500;
constexpr unsigned long AUTH_POLL_MS = 500;


// ============================================================
// GATE OPERATION
// ============================================================

enum GateOperation {
  GATE_NONE,
  GATE_ENTRY,
  GATE_EXIT
};

GateOperation gateOperation = GATE_NONE;


// ============================================================
// GATE STATE
// ============================================================

bool gateOpen = false;

unsigned long gateOpenedAt = 0;


// ============================================================
// EXIT SENSOR STATE
// ============================================================

bool previousExitSensorState = false;


// ============================================================
// SERVO
// ============================================================

Servo gateServo;


// ============================================================
// TIMERS & COOLDOWNS
// ============================================================

unsigned long lastEntryReport = 0;
unsigned long lastSlotReport = 0;

// Lock duration to prevent double-detection on physical sensors
constexpr unsigned long SENSOR_LOCK_MS = 4000;
unsigned long lastExitTriggerTime = 0;
unsigned long lastGateClosedTime = 0;
unsigned long lastAuthPoll = 0;


// ============================================================
// SENSOR HELPERS
// ============================================================

bool entryVehicleDetected() {
  return digitalRead(ENTRY_IR_PIN) == SENSOR_ACTIVE;
}


bool exitVehicleDetected() {
  return digitalRead(EXIT_IR_PIN) == SENSOR_ACTIVE;
}


bool slot1Occupied() {
  return digitalRead(SLOT_1_IR_PIN) == SENSOR_ACTIVE;
}


bool slot2Occupied() {
  return digitalRead(SLOT_2_IR_PIN) == SENSOR_ACTIVE;
}


bool slot3Occupied() {
  return digitalRead(SLOT_3_IR_PIN) == SENSOR_ACTIVE;
}


// ============================================================
// WIFI
// ============================================================

void connectWiFi() {

  if (WiFi.status() == WL_CONNECTED) {
    return;
  }

  Serial.println();
  Serial.println("Connecting to Wi-Fi...");

  WiFi.begin(
    WIFI_SSID,
    WIFI_PASSWORD
  );

  unsigned long start = millis();

  while (
    WiFi.status() != WL_CONNECTED &&
    millis() - start < 15000
  ) {

    delay(500);
    Serial.print(".");
  }

  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {

    Serial.println("Wi-Fi connected.");

    Serial.print("ESP32 IP: ");
    Serial.println(WiFi.localIP());

  } else {

    Serial.println("Wi-Fi connection failed.");
  }
}


// ============================================================
// REPORT ENTRY SENSOR
// ============================================================

void reportEntrySensor() {

  if (WiFi.status() != WL_CONNECTED) {
    return;
  }

  HTTPClient http;

  String url =
      String(API_BASE_URL) +
      "/api/iot/entry";

  http.begin(url);

  http.addHeader(
    "Content-Type",
    "application/json"
  );

  http.addHeader(
    "X-IoT-Key",
    IOT_API_KEY
  );

  bool waiting = entryVehicleDetected();
  bool exitWaiting = exitVehicleDetected();

  String payload = "{\"vehicle_waiting\":" + String(waiting ? "true" : "false") +
                   ",\"exit_vehicle_waiting\":" + String(exitWaiting ? "true" : "false") + "}";

  int httpCode =
      http.POST(payload);

  if (
    httpCode >= 200 &&
    httpCode < 300
  ) {

    Serial.print(
      "Entry sensor reported: "
    );

    Serial.println(
      waiting ? "waiting" : "clear"
    );

  } else {

    Serial.print(
      "POST /api/iot/entry failed: "
    );

    Serial.println(httpCode);
  }

  http.end();
}


// ============================================================
// REPORT SLOT SENSORS
// ============================================================

void reportSlotSensors() {

  if (WiFi.status() != WL_CONNECTED) {
    return;
  }

  HTTPClient http;

  String url =
      String(API_BASE_URL) +
      "/api/iot/slots";

  http.begin(url);

  http.addHeader(
    "Content-Type",
    "application/json"
  );

  http.addHeader(
    "X-IoT-Key",
    IOT_API_KEY
  );

  bool s1 = slot1Occupied();
  bool s2 = slot2Occupied();
  bool s3 = slot3Occupied();

  String payload = "{";

  payload += "\"S1\":";
  payload += s1 ? "true" : "false";

  payload += ",\"S2\":";
  payload += s2 ? "true" : "false";

  payload += ",\"S3\":";
  payload += s3 ? "true" : "false";

  payload += "}";

  int httpCode =
      http.POST(payload);

  if (
    httpCode >= 200 &&
    httpCode < 300
  ) {

    Serial.print("Slots: ");

    Serial.print("S1=");
    Serial.print(
      s1 ? "OCCUPIED" : "EMPTY"
    );

    Serial.print(" | S2=");
    Serial.print(
      s2 ? "OCCUPIED" : "EMPTY"
    );

    Serial.print(" | S3=");
    Serial.println(
      s3 ? "OCCUPIED" : "EMPTY"
    );

  } else {

    Serial.print(
      "POST /api/iot/slots failed: "
    );

    Serial.println(httpCode);
  }

  http.end();
}


// ============================================================
// START EXIT SEQUENCE
// ============================================================

bool requestExitSequence() {

  if (WiFi.status() != WL_CONNECTED) {
    return false;
  }

  HTTPClient http;

  String url =
      String(API_BASE_URL) +
      "/api/iot/exit";

  http.begin(url);

  http.addHeader(
    "X-IoT-Key",
    IOT_API_KEY
  );

  int httpCode =
      http.POST("");

  if (httpCode == 200) {

    String response =
        http.getString();

    StaticJsonDocument<512> doc;

    DeserializationError error =
        deserializeJson(
          doc,
          response
        );

    if (error) {

      Serial.print(
        "Exit JSON error: "
      );

      Serial.println(
        error.c_str()
      );

      http.end();

      return false;
    }

    bool success =
        doc["success"] | false;

    bool started =
        doc["started"] | false;

    if (success && started) {

      Serial.println();
      Serial.println(
        "EXIT sequence started."
      );

      http.end();

      return true;
    }

    Serial.println(
      "Exit sequence was not started."
    );

  } else {

    Serial.print(
      "POST /api/iot/exit failed: "
    );

    Serial.println(httpCode);
  }

  http.end();

  return false;
}


// ============================================================
// CHECK ENTRY AUTHORIZATION
// ============================================================

void checkEntryAuthorization() {

  if (WiFi.status() != WL_CONNECTED) {
    return;
  }

  // Never request another authorization
  // while the gate is open.
  if (gateOpen) {
    return;
  }

  HTTPClient http;

  String url =
      String(API_BASE_URL) +
      "/api/iot/entry-status";

  http.begin(url);

  http.addHeader(
    "X-IoT-Key",
    IOT_API_KEY
  );

  int httpCode =
      http.GET();

  if (httpCode == 200) {

    String response =
        http.getString();

    StaticJsonDocument<512> doc;

    DeserializationError error =
        deserializeJson(
          doc,
          response
        );

    if (error) {

      Serial.print(
        "Authorization JSON error: "
      );

      Serial.println(
        error.c_str()
      );

      http.end();

      return;
    }

    bool success =
        doc["success"] | false;

    bool authorized =
        doc["authorized"] | false;

    if (success && authorized) {

      const char* bookingId =
          doc["booking_id"] |
          "UNKNOWN";

      const char* vehicleNumber =
          doc["vehicle_number"] |
          "UNKNOWN";

      Serial.println();
      Serial.println(
        "=============================="
      );

      Serial.println(
        "ENTRY AUTHORIZATION RECEIVED"
      );

      Serial.print(
        "Booking: "
      );

      Serial.println(
        bookingId
      );

      Serial.print(
        "Vehicle: "
      );

      Serial.println(
        vehicleNumber
      );

      Serial.println(
        "=============================="
      );

      // This is an ENTRY operation.
      gateOperation =
          GATE_ENTRY;

      openGate();
    }

  } else if (httpCode < 0) {

    Serial.print(
      "Authorization poll failed: "
    );

    Serial.println(httpCode);
  }

  http.end();
}


// ============================================================
// REPORT ENTRY CROSSING COMPLETION
// ============================================================

void reportEntryCrossed() {

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Wi-Fi disconnected - cannot report entry crossing.");
    return;
  }

  HTTPClient http;

  String url =
      String(API_BASE_URL) +
      "/api/iot/entry-crossed";

  http.begin(url);

  http.addHeader(
    "Content-Type",
    "application/json"
  );

  http.addHeader(
    "X-IoT-Key",
    IOT_API_KEY
  );

  int httpCode =
      http.POST("{}");

  if (httpCode >= 200 && httpCode < 300) {

    String response =
        http.getString();

    Serial.print("Entry crossing reported: ");
    Serial.println(response);

  } else {

    Serial.print(
      "POST /api/iot/entry-crossed failed: "
    );

    Serial.println(httpCode);
  }

  http.end();
}


// ============================================================
// CHECK EXIT SENSOR
// ============================================================

void checkExitSensor() {

  bool currentExit =
      exitVehicleDetected();

  // Don't start another exit sequence while the gate is already handling a vehicle,
  // or if we are inside the sensor lock window after gate closure / previous exit.
  if (
    !gateOpen &&
    (millis() - lastGateClosedTime >= SENSOR_LOCK_MS) &&
    (millis() - lastExitTriggerTime >= SENSOR_LOCK_MS)
  ) {

    // Detect a CLEAR -> ACTIVE transition.
    if (
      currentExit &&
      !previousExitSensorState
    ) {

      Serial.println();
      Serial.println(
        "Exit sensor detected vehicle."
      );

      bool started =
          requestExitSequence();

      if (started) {

        lastExitTriggerTime = millis();

        gateOperation =
            GATE_EXIT;

        openGate();
      }
    }
  }

  previousExitSensorState =
      currentExit;
}


// ============================================================
// OPEN GATE
// ============================================================

void openGate() {

  if (gateOpen) {
    return;
  }

  Serial.println();
  Serial.println(
    "Opening gate..."
  );

  gateServo.write(
    GATE_OPEN_ANGLE
  );

  gateOpen = true;

  gateOpenedAt =
      millis();

  if (gateOperation == GATE_ENTRY) {

    Serial.println(
      "Gate operation: ENTRY"
    );

  } else if (
    gateOperation == GATE_EXIT
  ) {

    Serial.println(
      "Gate operation: EXIT"
    );
  }

  Serial.println(
    "Gate OPEN."
  );
}


// ============================================================
// CLOSE GATE
// ============================================================

void closeGate() {

  if (!gateOpen) {
    return;
  }

  Serial.println();
  Serial.println(
    "Closing gate..."
  );

  gateServo.write(
    GATE_CLOSED_ANGLE
  );

  gateOpen = false;

  // Record timestamp to lock exit sensor from double-detecting immediately after gate closes
  lastGateClosedTime = millis();

  Serial.println(
    "Gate CLOSED."
  );

  gateOperation =
      GATE_NONE;
}


// ============================================================
// HANDLE OPEN GATE
// ============================================================

void handleOpenGate() {

  if (!gateOpen) {
    return;
  }

  // ----------------------------------------------------------
  // ENTRY OPERATION
  //
  // Entry -> Exit
  // Closes ONLY when the vehicle reaches the EXIT sensor.
  // ----------------------------------------------------------

  if (gateOperation == GATE_ENTRY) {

    if (exitVehicleDetected()) {

      Serial.println(
        "Vehicle reached EXIT sensor."
      );

      Serial.println(
        "Entry crossing completed."
      );

      // Tell Flask that the vehicle has crossed the gate.
      // Backend changes ENTERING -> IDLE.
      reportEntryCrossed();

      closeGate();

      return;
    }
  }


  // ----------------------------------------------------------
  // EXIT OPERATION
  //
  // Exit -> Entry
  // Closes ONLY when the vehicle reaches the ENTRY sensor.
  // ----------------------------------------------------------

  if (gateOperation == GATE_EXIT) {

    if (entryVehicleDetected()) {

      Serial.println(
        "Vehicle reached ENTRY sensor."
      );

      Serial.println(
        "Exit crossing completed."
      );

      closeGate();

      return;
    }
  }

  // Gate remains OPEN until the vehicle sensor detects the car crossing.
  // Timer-based auto-closing has been disabled per system requirements.
}


// ============================================================
// PRINT SENSOR STATUS
// ============================================================

void printSensorStatus() {

  static unsigned long lastPrint =
      0;

  if (
    millis() - lastPrint <
    2000
  ) {
    return;
  }

  lastPrint =
      millis();

  Serial.print("Entry (GPIO 18 raw=");
  Serial.print(digitalRead(ENTRY_IR_PIN));
  Serial.print("): ");
  Serial.print(
    entryVehicleDetected()
      ? "ACTIVE"
      : "CLEAR"
  );

  Serial.print(" | Exit (GPIO 19 raw=");
  Serial.print(digitalRead(EXIT_IR_PIN));
  Serial.print("): ");
  Serial.print(
    exitVehicleDetected()
      ? "ACTIVE"
      : "CLEAR"
  );

  Serial.print(" | S1: ");
  Serial.print(slot1Occupied() ? "OCCUPIED" : "EMPTY");
  Serial.print(" | S2: ");
  Serial.print(slot2Occupied() ? "OCCUPIED" : "EMPTY");
  Serial.print(" | S3: ");
  Serial.print(slot3Occupied() ? "OCCUPIED" : "EMPTY");


  Serial.print(" | Gate: ");

  if (gateOpen) {

    if (gateOperation == GATE_ENTRY) {
      Serial.println("OPEN-ENTRY");
    }
    else if (gateOperation == GATE_EXIT) {
      Serial.println("OPEN-EXIT");
    }
    else {
      Serial.println("OPEN");
    }

  } else {

    Serial.println("CLOSED");
  }
}


// ============================================================
// SETUP
// ============================================================

void setup() {

  Serial.begin(115200);

  delay(1000);

  Serial.println();
  Serial.println(
    "=============================="
  );

  Serial.println(
    "ParkEase Smart Parking ESP32"
  );

  Serial.println(
    "=============================="
  );


  // ----------------------------------------------------------
  // IR SENSORS
  // ----------------------------------------------------------

  pinMode(
    ENTRY_IR_PIN,
    INPUT_PULLUP
  );

  pinMode(
    EXIT_IR_PIN,
    INPUT_PULLUP
  );

  pinMode(
    SLOT_1_IR_PIN,
    INPUT_PULLUP
  );

  pinMode(
    SLOT_2_IR_PIN,
    INPUT_PULLUP
  );

  pinMode(
    SLOT_3_IR_PIN,
    INPUT_PULLUP
  );



  // ----------------------------------------------------------
  // INITIAL EXIT SENSOR STATE
  // ----------------------------------------------------------

  previousExitSensorState =
      exitVehicleDetected();


  // ----------------------------------------------------------
  // SERVO
  // ----------------------------------------------------------

  gateServo.setPeriodHertz(50);

  gateServo.attach(
    SERVO_PIN,
    500,
    2400
  );

  gateServo.write(
    GATE_CLOSED_ANGLE
  );

  gateOpen = false;

  gateOperation =
      GATE_NONE;

  Serial.println(
    "Gate initialized CLOSED."
  );


  // ----------------------------------------------------------
  // WIFI
  // ----------------------------------------------------------

  connectWiFi();

  Serial.println();
  Serial.println(
    "System ready."
  );
}


// ============================================================
// LOOP
// ============================================================

void loop() {

  // ----------------------------------------------------------
  // WIFI
  // ----------------------------------------------------------

  if (
    WiFi.status() !=
    WL_CONNECTED
  ) {

    static unsigned long
        lastWiFiAttempt = 0;

    if (
      millis() -
      lastWiFiAttempt >=
      WIFI_RETRY_MS
    ) {

      lastWiFiAttempt =
          millis();

      connectWiFi();
    }

    return;
  }


  // ----------------------------------------------------------
  // ENTRY SENSOR → FLASK
  // ----------------------------------------------------------

  if (
    millis() -
    lastEntryReport >=
    ENTRY_REPORT_MS
  ) {

    lastEntryReport =
        millis();

    reportEntrySensor();
  }


  // ----------------------------------------------------------
  // SLOT SENSORS → FLASK
  // ----------------------------------------------------------

  if (
    millis() -
    lastSlotReport >=
    SLOT_REPORT_MS
  ) {

    lastSlotReport =
        millis();

    reportSlotSensors();
  }


  // ----------------------------------------------------------
  // ENTRY AUTHORIZATION
  // ----------------------------------------------------------

  if (
    millis() -
    lastAuthPoll >=
    AUTH_POLL_MS
  ) {

    lastAuthPoll =
        millis();

    checkEntryAuthorization();
  }


  // ----------------------------------------------------------
  // EXIT SENSOR
  // ----------------------------------------------------------

  checkExitSensor();


  // ----------------------------------------------------------
  // GATE CONTROL
  // ----------------------------------------------------------

  handleOpenGate();


  // ----------------------------------------------------------
  // DEBUG
  // ----------------------------------------------------------

  printSensorStatus();
}