/*
GPS Simulator for ESP32 M5 Stick C Plus
========================================

This project simulates a u-blox neo-6m GPS module by:
1. Reading GPS track data from uploaded CSV files
2. Converting coordinates to proper NMEA format
3. Outputting authentic NMEA sentences via UART at 9600 baud
4. Providing web interface for control and file upload
5. Using NTP-synchronized timing for real-world timestamps

Educational Focus: Demonstrates embedded systems programming concepts including:
- Real-time systems and precise timing
- Serial communication protocols (UART, NMEA)
- File system management (SPIFFS)
- Network programming (WiFi, HTTP, NTP)
- State machine design patterns
- Memory management in embedded systems
- Hardware abstraction and GPIO control

Hardware: ESP32 M5 Stick C Plus with integrated display
Output: GPIO 32 (TX) at 9600 baud, 8N1, no flow control
*/

#include <Arduino.h>
#include <M5StickCPlus.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <Update.h>
#include <ESPAsyncWebServer.h>
#include <AsyncElegantOTA.h>
#include <SPIFFS.h>
#include <NTPClient.h>
#include <TimeLib.h>
#include <TinyGPS++.h>

#include "mercator_secrets.c"  // WiFi credentials and configuration

// =============================================================================
// HARDWARE CONFIGURATION
// =============================================================================

// GPS UART configuration - ESP32 has multiple hardware serial ports
// We use Serial1 (UART1) to avoid conflicts with USB debugging (Serial0)
HardwareSerial gpsSerial(1);
const int GPS_TX_PIN = 32;  // GPIO 32 for transmit to GPS receiver
const int GPS_RX_PIN = 33;  // GPIO 33 for receive (unused in TX-only simulation)

// =============================================================================
// NETWORK AND WEB SERVICES
// =============================================================================

// Asynchronous web server for handling multiple concurrent connections
// Port 80 is standard HTTP port - no HTTPS to keep example simple
AsyncWebServer server(80);
AsyncElegantOtaClass AsyncElegantOTA;  // Over-the-air update capability

// Network Time Protocol for accurate timestamp synchronization
// UDP is used because NTP is a connectionless protocol
WiFiUDP ntpUDP;
NTPClient timeClient(ntpUDP);  // Connects to pool.ntp.org by default

// =============================================================================
// GPS SIMULATION STATE VARIABLES
// =============================================================================

// File handle for the GPS track CSV data stored in SPIFFS flash memory
File csvFile;

// System state flags - using boolean for clarity and memory efficiency
bool gpsSimActive = false;     // Is GPS simulation currently running?
bool csvLoaded = false;        // Has a CSV file been successfully loaded?

// Timing control for precise 1-second GPS fix intervals
// Using unsigned long to handle millis() rollover after ~49 days
unsigned long lastGpsOutput = 0;

// Current position in CSV file - helps with debugging and status display
int currentLine = 0;

// =============================================================================
// GPS DATA STRUCTURES
// =============================================================================

/**
 * Structure to hold parsed GPS data from CSV file
 * 
 * This struct represents a single GPS fix with all the information needed
 * to generate authentic NMEA sentences. Using a struct improves code
 * readability and makes data passing more efficient than individual variables.
 */
struct GPSData {
  String utc_time;          // UTC time as string (HH:MM:SS format)
  float latitude;           // Latitude in decimal degrees (positive = North)
  float longitude;          // Longitude in decimal degrees (positive = East)
  int sats;                 // Number of satellites used in fix
  float hdop;               // Horizontal Dilution of Precision
  float gps_course;         // Course over ground in degrees (0-359)
  float gps_speed_knots;    // Speed over ground in knots
  bool valid = false;       // Is this GPS data valid and complete?
};

// Current GPS data being processed - represents the "now" position
GPSData currentGPS;

// Future enhancement: nextGPS could be used for interpolation between points
GPSData nextGPS;

// =============================================================================
// USER INTERFACE VARIABLES
// =============================================================================

// Status message displayed on M5StickC screen
// String is used for convenience, though char arrays would be more memory efficient
String statusMsg = "Initializing...";

// =============================================================================
// DISPLAY AND USER INTERFACE FUNCTIONS
// =============================================================================

/**
 * Update the M5StickC Plus LCD display with current system status
 * 
 * The display provides immediate visual feedback about system state without
 * requiring network connectivity. This is crucial for debugging and field use.
 * 
 * Layout:
 * - Title and separator
 * - WiFi connection status and IP address
 * - CSV file load status
 * - GPS simulation active/stopped status  
 * - Current status message
 */
void displayStatus() {
  // Clear screen with black background for better contrast and power efficiency
  M5.Lcd.fillScreen(BLACK);
  M5.Lcd.setTextColor(WHITE);
  M5.Lcd.setCursor(0, 0);
  M5.Lcd.setTextSize(1);  // Small text to fit more information on tiny screen
  
  // Application title with visual separator
  M5.Lcd.println("GPS Simulator");
  M5.Lcd.println("=============");
  M5.Lcd.println();
  
  // Network status - critical for web interface access
  M5.Lcd.printf("WiFi: %s\n", WiFi.status() == WL_CONNECTED ? "Connected" : "Disconnected");
  if (WiFi.status() == WL_CONNECTED) {
    // Show IP address so user can access web interface
    // toString().c_str() converts IPAddress to String to char* for printf
    M5.Lcd.printf("IP: %s\n", WiFi.localIP().toString().c_str());
  }
  M5.Lcd.println();
  
  // File system status - shows if GPS data is available
  M5.Lcd.printf("CSV: %s\n", csvLoaded ? "Loaded" : "Not loaded");
  
  // GPS simulation status - shows if NMEA output is active
  M5.Lcd.printf("GPS: %s\n", gpsSimActive ? "Active" : "Stopped");
  M5.Lcd.println();
  
  // Dynamic status message for detailed information
  M5.Lcd.println(statusMsg);
}

// =============================================================================
// NETWORK CONNECTION FUNCTIONS
// =============================================================================

/**
 * Attempt to connect to WiFi with automatic fallback between networks
 * 
 * This implements a robust connection strategy for field deployment where
 * multiple networks might be available. The function tries each configured
 * network in sequence with individual timeouts.
 * 
 * @return true if connected successfully, false if all networks failed
 * 
 * Design pattern: This demonstrates graceful degradation - the system
 * continues to function even if WiFi connection fails, just without
 * NTP sync and web interface capabilities.
 */
bool connectToWiFi() {
  // Arrays of network credentials from secrets file
  // Using const char* arrays for memory efficiency vs String arrays
  const char* ssids[] = {ssid_1, ssid_2, ssid_3};
  const char* passwords[] = {password_1, password_2, password_3};
  const char* labels[] = {label_1, label_2, label_3};
  const int timeouts[] = {timeout_1, timeout_2, timeout_3};
  
  // Try each network in sequence
  for (int i = 0; i < 3; i++) {
    // Update display to show connection attempt
    statusMsg = "Connecting to " + String(labels[i]);
    displayStatus();
    
    // Begin WiFi connection attempt
    // This is non-blocking - it initiates the connection process
    WiFi.begin(ssids[i], passwords[i]);
    
    // Wait for connection with timeout
    // Using millis() instead of delay() allows for more responsive behavior
    unsigned long startTime = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - startTime < timeouts[i]) {
      delay(100);  // Small delay to prevent excessive CPU usage
      // Could add watchdog feed or button checking here for advanced behavior
    }
    
    // Check if connection succeeded
    if (WiFi.status() == WL_CONNECTED) {
      statusMsg = "Connected to " + String(labels[i]);
      return true;  // Success - exit immediately
    }
    
    // Connection failed, try next network
    // WiFi.begin() with new credentials automatically disconnects from previous attempt
  }
  
  // All networks failed
  statusMsg = "WiFi connection failed";
  return false;
}

// =============================================================================
// NMEA PROTOCOL FUNCTIONS
// =============================================================================

/**
 * Calculate NMEA 0183 checksum using XOR algorithm
 * 
 * NMEA sentences require a checksum for data integrity verification.
 * The checksum is computed by XORing all characters between '$' and '*'.
 * 
 * @param sentence The NMEA sentence (must start with $ but not include *)
 * @return 8-bit checksum value
 * 
 * Example: For "$GPGGA,123456.00,1234.5678,N,12345.6789,W,1,08,0.9,545.4,M,46.9,M,,"
 * The checksum is calculated on: "GPGGA,123456.00,1234.5678,N,12345.6789,W,1,08,0.9,545.4,M,46.9,M,,"
 */
uint8_t calculateChecksum(const char* sentence) {
  uint8_t checksum = 0;  // Initialize accumulator
  
  // Start from index 1 to skip the '$' character
  // Continue until '*' delimiter or end of string
  for (int i = 1; sentence[i] != '*' && sentence[i] != '\0'; i++) {
    checksum ^= sentence[i];  // XOR operation - self-inverse for error detection
  }
  
  return checksum;
}

/**
 * Create complete NMEA sentence with calculated checksum
 * 
 * Takes a partial NMEA sentence (without checksum) and appends the
 * properly formatted checksum. The result is a complete, valid NMEA sentence.
 * 
 * @param sentence Partial NMEA sentence starting with $ (no checksum)
 * @return Complete NMEA sentence with *XX checksum appended
 * 
 * Example: "$GPGGA,..." becomes "$GPGGA,...*7E"
 */
String createNMEASentence(String sentence) {
  // Convert String to char array for checksum calculation
  // 256 bytes should be sufficient for any NMEA sentence
  char buffer[256];
  sentence.toCharArray(buffer, 256);
  
  // Calculate the checksum
  uint8_t checksum = calculateChecksum(buffer);
  
  // Convert checksum to uppercase hexadecimal string
  // Note: toUpperCase() modifies the string in place and returns void
  String checksumStr = String(checksum, HEX);
  checksumStr.toUpperCase();  // NMEA standard requires uppercase hex
  
  // Combine sentence with checksum delimiter and checksum
  return sentence + "*" + checksumStr;
}

/**
 * Generate and send GNRMC (Recommended Minimum Navigation Information) sentence
 * 
 * GNRMC is one of the most important NMEA sentences, containing essential
 * navigation data including position, speed, course, and time.
 * 
 * Format: $GNRMC,time,status,lat,NS,lon,EW,speed,course,date,magvar,mode,checksum
 * 
 * @param gps GPS data structure containing position and navigation information
 * 
 * Educational note: This demonstrates coordinate system conversion from
 * decimal degrees (used internally) to degrees/minutes format (NMEA standard).
 */
void sendGNRMC(const GPSData& gps) {
  // Validate GPS data before processing
  if (!gps.valid) return;
  
  // Begin NMEA sentence construction
  // GNRMC = Global Navigation Recommended Minimum Course
  // 'A' = Active (valid fix), 'V' would indicate void/invalid
  String sentence = "$GNRMC," + gps.utc_time + ",A,";
  
  // LATITUDE CONVERSION: Decimal degrees → Degrees + Minutes
  // NMEA format: DDMM.MMMMM (degrees + minutes to 5 decimal places)
  float lat = abs(gps.latitude);  // Work with absolute value
  int latDeg = (int)lat;          // Extract whole degrees
  float latMin = (lat - latDeg) * 60;  // Convert remainder to minutes
  
  sentence += String(latDeg, 0) + String(latMin, 5) + ",";  // DDMM.MMMMM
  sentence += gps.latitude >= 0 ? "N," : "S,";  // Hemisphere indicator
  
  // LONGITUDE CONVERSION: Same process as latitude
  // NMEA format: DDDMM.MMMMM (longitude has 3 digit degrees)
  float lng = abs(gps.longitude);
  int lngDeg = (int)lng;
  float lngMin = (lng - lngDeg) * 60;
  
  sentence += String(lngDeg, 0) + String(lngMin, 5) + ",";  // DDDMM.MMMMM
  sentence += gps.longitude >= 0 ? "E," : "W,";  // Hemisphere indicator
  
  // Navigation data
  sentence += String(gps.gps_speed_knots, 3) + ",";  // Speed over ground in knots
  sentence += String(gps.gps_course, 1) + ",";       // Course over ground in degrees
  
  // Date and magnetic variation (using fixed values for simplicity)
  sentence += "220725,,,A,V";  // Date: 25-Jul-2022, no mag var, mode indicators
  
  // Generate complete sentence with checksum and send via UART
  String fullSentence = createNMEASentence(sentence);
  gpsSerial.println(fullSentence);  // println adds \r\n line ending
}

void sendGNGGA(const GPSData& gps) {
  if (!gps.valid) return;
  
  String sentence = "$GNGGA," + gps.utc_time + ",";
  
  // Latitude
  float lat = abs(gps.latitude);
  int latDeg = (int)lat;
  float latMin = (lat - latDeg) * 60;
  sentence += String(latDeg, 0) + String(latMin, 5) + ",";
  sentence += gps.latitude >= 0 ? "N," : "S,";
  
  // Longitude
  float lng = abs(gps.longitude);
  int lngDeg = (int)lng;
  float lngMin = (lng - lngDeg) * 60;
  sentence += String(lngDeg, 0) + String(lngMin, 5) + ",";
  sentence += gps.longitude >= 0 ? "E," : "W,";
  
  sentence += "1,";  // Fix quality
  sentence += String(gps.sats, 0) + ",";  // Number of satellites
  sentence += String(gps.hdop, 2) + ",";  // HDOP
  sentence += "56.3,M,46.9,M,,";  // Altitude and geoidal separation
  
  String fullSentence = createNMEASentence(sentence);
  gpsSerial.println(fullSentence);
}

void sendGNGSA() {
  String sentence1 = "$GNGSA,A,3,01,02,04,31,,,,,,,,,6.27,4.89,3.92,1";
  String sentence2 = "$GNGSA,A,3,,,,,,,,,,,,,6.27,4.89,3.92,4";
  
  gpsSerial.println(createNMEASentence(sentence1));
  delay(50);
  gpsSerial.println(createNMEASentence(sentence2));
}

void sendGPGSV() {
  String sentence1 = "$GPGSV,2,1,05,01,57,120,12,02,28,127,27,04,43,173,23,17,,,21";
  String sentence2 = "$GPGSV,2,2,05,31,17,085,30";
  
  gpsSerial.println(createNMEASentence(sentence1));
  delay(50);
  gpsSerial.println(createNMEASentence(sentence2));
}

void sendBDGSV() {
  String sentence = "$BDGSV,1,1,00";
  gpsSerial.println(createNMEASentence(sentence));
}

void sendGNTXT() {
  String sentence = "$GNTXT,1,1,01,ANTENNA OK";
  gpsSerial.println(createNMEASentence(sentence));
}

void parseCSVLine(String line, GPSData& gps) {
  int fieldIndex = 0;
  int startPos = 0;
  int commaPos = 0;
  
  gps.valid = false;
  
  while ((commaPos = line.indexOf(',', startPos)) != -1) {
    String field = line.substring(startPos, commaPos);
    
    switch (fieldIndex) {
      case 3: // UTC_time
        gps.utc_time = field;
        break;
      case 6: // coordinates
        if (field.length() > 4) {
          int bracketStart = field.indexOf('[');
          int commaIndex = field.indexOf(',', bracketStart);
          int bracketEnd = field.indexOf(']', commaIndex);
          
          if (bracketStart != -1 && commaIndex != -1 && bracketEnd != -1) {
            gps.latitude = field.substring(bracketStart + 1, commaIndex).toFloat();
            gps.longitude = field.substring(commaIndex + 2, bracketEnd).toFloat();
            gps.valid = true;
          }
        }
        break;
      case 16: // gps_course
        gps.gps_course = field.toFloat();
        break;
      case 17: // gps_speed_knots
        gps.gps_speed_knots = field.toFloat();
        break;
      case 18: // hdop
        gps.hdop = field.toFloat();
        break;
      case 60: // sats
        gps.sats = field.toInt();
        if (gps.sats == 0) gps.sats = 4; // Default to 4 satellites
        break;
    }
    
    startPos = commaPos + 1;
    fieldIndex++;
  }
}

bool loadCSV() {
  if (!SPIFFS.exists("/gps_track.csv")) {
    statusMsg = "No CSV file found";
    return false;
  }
  
  csvFile = SPIFFS.open("/gps_track.csv", "r");
  if (!csvFile) {
    statusMsg = "Failed to open CSV";
    return false;
  }
  
  // Skip header line
  csvFile.readStringUntil('\n');
  currentLine = 0;
  csvLoaded = true;
  statusMsg = "CSV loaded successfully";
  return true;
}

GPSData getNextGPSData() {
  GPSData gps;
  if (!csvFile || !csvFile.available()) {
    return gps; // Invalid GPS data
  }
  
  String line = csvFile.readStringUntil('\n');
  if (line.length() > 0) {
    parseCSVLine(line, gps);
    currentLine++;
  }
  
  return gps;
}

void simulateGPS() {
  if (!gpsSimActive || !csvLoaded) return;
  
  unsigned long now = millis();
  if (now - lastGpsOutput >= 1000) { // 1 second interval
    
    // Get current time and format as HHMMSS.00
    unsigned long epochTime = timeClient.getEpochTime();
    int hours = (epochTime % 86400L) / 3600;
    int minutes = (epochTime % 3600) / 60;
    int seconds = epochTime % 60;
    
    char timeStr[12];
    sprintf(timeStr, "%02d%02d%02d.00", hours, minutes, seconds);
    currentGPS.utc_time = String(timeStr);
    
    if (currentGPS.valid) {
      // Send NMEA sentences in proper order
      sendGNRMC(currentGPS);
      delay(50);
      sendGNGGA(currentGPS);
      delay(50);
      sendGNGSA();
      delay(50);
      sendGPGSV();
      delay(50);
      sendBDGSV();
      delay(50);
      sendGNTXT();
      
      // Load next GPS data point
      currentGPS = getNextGPSData();
      if (!currentGPS.valid) {
        // Restart from beginning if we reach end of file
        csvFile.close();
        loadCSV();
        currentGPS = getNextGPSData();
      }
    }
    
    lastGpsOutput = now;
  }
}

// =============================================================================
// MAIN PROGRAM ENTRY POINTS
// =============================================================================

/**
 * Arduino setup() function - runs once at system startup
 * 
 * PROGRAM FLOW OVERVIEW:
 * 1. Hardware initialization (M5StickC, UART, SPIFFS)
 * 2. Network connectivity (WiFi with fallback)
 * 3. Time synchronization (NTP for accurate GPS timestamps)
 * 4. Web server setup (control interface and file upload)
 * 5. GPS simulation initialization (load existing CSV if present)
 * 
 * DESIGN PATTERNS DEMONSTRATED:
 * - Initialization sequence with error handling
 * - Service layer architecture (display, network, file system)
 * - Graceful degradation (continues without WiFi)
 * - State machine initialization
 * 
 * MEMORY LAYOUT AT STARTUP:
 * - Stack: ~8KB for local variables and function calls
 * - Heap: ~250KB available for dynamic allocation (String, File objects)
 * - Flash: Code in app partition, CSV data in SPIFFS partition
 * - PSRAM: Not used in this application (M5StickC Plus has none)
 */
void setup() {
  // Initialize M5StickC Plus hardware
  // Parameters: LCD, Serial, I2C, State (enable all except state button)
  M5.begin(true, true, true, false);
  M5.Lcd.setRotation(3);
  
  // Initialize SPIFFS
  if (!SPIFFS.begin(true)) {
    statusMsg = "SPIFFS Mount Failed";
    displayStatus();
    return;
  }
  
  // Initialize GPS Serial
  gpsSerial.begin(9600, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);
  
  displayStatus();
  
  // Connect to WiFi
  if (!connectToWiFi()) {
    displayStatus();
    return;
  }
  
  // Initialize NTP
  timeClient.begin();
  timeClient.update();
  setTime(timeClient.getEpochTime());
  
  // Setup web server for OTA
  server.on("/", HTTP_GET, [](AsyncWebServerRequest *request) {
    String html = R"(
<!DOCTYPE html>
<html>
<head><title>GPS Simulator</title></head>
<body>
<h1>GPS Simulator Control</h1>
<p><a href="/update" target="_blank">Firmware Update (ElegantOTA)</a></p>
<p><a href="/upload">Upload GPS Track CSV</a></p>
<form action="/upload" method="post" enctype="multipart/form-data">
  <input type="file" name="csv" accept=".csv">
  <input type="submit" value="Upload CSV">
</form>
<p><a href="/start">Start GPS Simulation</a></p>
<p><a href="/stop">Stop GPS Simulation</a></p>
</body>
</html>
    )";
    request->send(200, "text/html", html);
  });
  
  server.on("/upload", HTTP_POST, [](AsyncWebServerRequest *request) {
    request->send(200, "text/plain", "CSV uploaded successfully");
  }, [](AsyncWebServerRequest *request, String filename, size_t index, uint8_t *data, size_t len, bool final) {
    if (index == 0) {
      // Delete old file
      if (SPIFFS.exists("/gps_track.csv")) {
        SPIFFS.remove("/gps_track.csv");
      }
      csvFile = SPIFFS.open("/gps_track.csv", "w");
    }
    
    if (csvFile) {
      csvFile.write(data, len);
    }
    
    if (final) {
      csvFile.close();
      csvLoaded = false;
      gpsSimActive = false;
      loadCSV();
    }
  });
  
  server.on("/start", HTTP_GET, [](AsyncWebServerRequest *request) {
    if (csvLoaded) {
      gpsSimActive = true;
      currentGPS = getNextGPSData();
      statusMsg = "GPS simulation started";
      request->send(200, "text/plain", "GPS simulation started");
    } else {
      request->send(400, "text/plain", "No CSV file loaded");
    }
  });
  
  server.on("/stop", HTTP_GET, [](AsyncWebServerRequest *request) {
    gpsSimActive = false;
    statusMsg = "GPS simulation stopped";
    request->send(200, "text/plain", "GPS simulation stopped");
  });
  
  AsyncElegantOTA.begin(&server);
  server.begin();
  
  statusMsg = "Ready - " + WiFi.localIP().toString();
  displayStatus();
  
  // Try to load existing CSV
  loadCSV();
  displayStatus();
}

void loop() {
  M5.update();
  timeClient.update();
  
  // Button A: Start/Stop simulation
  if (M5.BtnA.wasReleased()) {
    if (csvLoaded) {
      gpsSimActive = !gpsSimActive;
      if (gpsSimActive && !currentGPS.valid) {
        currentGPS = getNextGPSData();
      }
      statusMsg = gpsSimActive ? "GPS started" : "GPS stopped";
      displayStatus();
    }
  }
  
  // Button B: Reload CSV
  if (M5.BtnB.wasReleased()) {
    gpsSimActive = false;
    loadCSV();
    displayStatus();
  }
  
  simulateGPS();
  
  // Update display every 5 seconds
  static unsigned long lastDisplayUpdate = 0;
  if (millis() - lastDisplayUpdate > 5000) {
    displayStatus();
    lastDisplayUpdate = millis();
  }
  
  delay(50);
}
