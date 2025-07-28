/*
GPS Simulator for ESP32 M5 Stick C Plus
========================================

This project simulates a u-blox neo-6m GPS module by:
1. Reading GPS track data from uploaded CSV files
2. Converting coordinates to proper NMEA format
3. Outputting authentic NMEA sentences via dual channels (GPIO UART + USB Serial) at 9600 baud
4. Providing web interface for control, file upload, and output configuration
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
Output: Dual channel - GPIO 32 (UART1) + USB Serial (UART0) at 9600 baud, 8N1, no flow control
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
// WIFI CONFIGURATION AND STATE MANAGEMENT
// =============================================================================

// WiFi operation modes - affects network connectivity and web interface access
enum WiFiMode {
  WIFI_CLIENT_MODE,    // Connect to existing WiFi network (normal mode)
  WIFI_AP_MODE         // Create Access Point for direct connection
};

// WiFi Access Point configuration
const char* AP_SSID = "GPS-SIM";
const char* AP_PASSWORD = "cool-sim";
const IPAddress AP_IP(192, 168, 4, 1);        // Standard AP gateway IP
const IPAddress AP_GATEWAY(192, 168, 4, 1);
const IPAddress AP_SUBNET(255, 255, 255, 0);

// Current WiFi mode and connection state
WiFiMode currentWiFiMode = WIFI_CLIENT_MODE;  // Default to client mode
bool wifiModeChanged = false;                 // Flag to trigger mode switch
bool ntpSyncAvailable = false;                // NTP only works in client mode

// NTP synchronization state and timing
bool ntpSyncCompleted = false;                // Has NTP sync been successful at least once?
unsigned long lastNtpSyncAttempt = 0;         // When was the last NTP sync attempted
unsigned long lastSuccessfulNtpSync = 0;     // When was NTP last successful
const unsigned long NTP_SYNC_TIMEOUT = 10000; // 10 seconds timeout for NTP sync attempts

// =============================================================================
// OUTPUT CONFIGURATION
// =============================================================================

/**
 * 🎯 EDUCATIONAL BLOCK: Dual Output Management
 * 
 * WHAT: Manages NMEA output to both GPIO UART and USB Serial
 * WHY: Provides flexibility for different testing scenarios and connection methods
 * HOW: Separate enable flags allow independent control of each output channel
 * GOTCHAS: Both outputs cannot be disabled simultaneously to prevent silent failures
 * 
 * Example: GPIO for hardware GPS receivers, USB for computer-based analysis
 * References: ESP32 supports multiple serial interfaces (UART0=USB, UART1=GPIO)
 */

// Output channel control - default to both enabled for maximum compatibility
bool gpioOutputEnabled = true;    // Enable NMEA output via GPIO pins 32/33
bool usbOutputEnabled = true;     // Enable NMEA output via USB Serial port

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
  M5.Lcd.setTextSize(2);  // Small text to fit more information on tiny screen
  
  // Application title with visual separator
  M5.Lcd.println("GPS Simulator");
//  M5.Lcd.println("=============");
//  M5.Lcd.println();
  
  // Network status with mode indication - critical for web interface access
  const char* modeStr = (currentWiFiMode == WIFI_AP_MODE) ? "AP" : "Client";
  const char* statusStr = WiFi.status() == WL_CONNECTED ? "Connect" : "Discon";
  
  M5.Lcd.printf("WiFi %s: %s\n", modeStr, statusStr);
  
  if (WiFi.status() == WL_CONNECTED) {
    // Show IP address so user can access web interface
    // toString().c_str() converts IPAddress to String to char* for printf
    M5.Lcd.printf("IP: %s\n", WiFi.localIP().toString().c_str());
    
    // Show SSID in client mode, or indicate AP mode
    if (currentWiFiMode == WIFI_AP_MODE) {
      M5.Lcd.printf("ID: %s\n", AP_SSID);
    } else {
      M5.Lcd.printf("ID: %s\n", WiFi.SSID().c_str());
    }
  }
//  M5.Lcd.println();
  
  // File system status - shows if GPS data is available
  M5.Lcd.printf("CSV: %s\n", csvLoaded ? "Loaded" : "Not loaded");
  
  // GPS simulation status - shows if NMEA output is active
  M5.Lcd.printf("GPS: %s\n", gpsSimActive ? "Active" : "Stopped");
  
  // Output configuration status - shows which outputs are enabled
  String outputStr = "";
  if (gpioOutputEnabled && usbOutputEnabled) {
    outputStr = "GPIO+USB";
  } else if (gpioOutputEnabled) {
    outputStr = "GPIO only";
  } else if (usbOutputEnabled) {
    outputStr = "USB only";
  } else {
    outputStr = "No output!";  // Should never happen due to validation
  }
  M5.Lcd.printf("Out: %s\n", outputStr.c_str());
//  M5.Lcd.println();
  
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

/**
 * Setup WiFi Access Point mode for direct device connection
 * 
 * Creates a local WiFi network that devices can connect to directly.
 * Useful for field deployment where no existing WiFi infrastructure exists.
 * 
 * Network Configuration:
 * - SSID: GPS-SIM
 * - Password: cool-sim  
 * - IP: 192.168.4.1 (standard AP gateway)
 * - DHCP: Automatic IP assignment for connected devices
 * 
 * @return true if AP started successfully, false if setup failed
 * 
 * Note: NTP synchronization is not available in AP mode since there's
 * no internet connection. GPS timestamps will use internal RTC only.
 */
bool setupAccessPoint() {
  statusMsg = "Starting Access Point...";
  displayStatus();
  
  // Stop any existing WiFi connections
  WiFi.disconnect(true);
  delay(100);
  
  // Configure Access Point with static IP
  if (!WiFi.softAPConfig(AP_IP, AP_GATEWAY, AP_SUBNET)) {
    statusMsg = "AP config failed";
    return false;
  }
  
  // Start the Access Point
  if (!WiFi.softAP(AP_SSID, AP_PASSWORD)) {
    statusMsg = "AP startup failed";
    return false;
  }
  
  // Wait for AP to be ready
  delay(2000);
  
  // Verify AP is running
  if (WiFi.softAPgetStationNum() >= 0) {  // AP is active (even with 0 clients)
    statusMsg = "Access Point: " + String(AP_SSID);
    ntpSyncAvailable = false;  // No internet connection in AP mode
    currentWiFiMode = WIFI_AP_MODE;
    return true;
  } else {
    statusMsg = "AP verification failed";
    return false;
  }
}

/**
 * Switch between WiFi Client and Access Point modes
 * 
 * This function handles the transition between different WiFi modes.
 * Client mode connects to existing networks, AP mode creates a hotspot.
 * 
 * @param newMode The desired WiFi mode to switch to
 * @return true if mode switch successful, false if failed
 * 
 * Side effects:
 * - Disconnects from current network
 * - Updates global currentWiFiMode variable
 * - Affects NTP sync availability
 * - May restart web server if needed
 */
bool switchWiFiMode(WiFiMode newMode) {
  if (newMode == currentWiFiMode) {
    return true;  // Already in desired mode
  }
  
  statusMsg = "Switching WiFi mode...";
  displayStatus();
  
  // Disconnect from current network/stop current AP
  WiFi.disconnect(true);
  WiFi.softAPdisconnect(true);
  delay(500);
  
  bool success = false;
  
  if (newMode == WIFI_AP_MODE) {
    success = setupAccessPoint();
  } else {
    success = connectToWiFi();
    if (success) {
      // Re-initialize NTP in client mode
      timeClient.begin();
      timeClient.update();
      setTime(timeClient.getEpochTime());
      ntpSyncAvailable = true;
    }
  }
  
  if (success) {
    currentWiFiMode = newMode;
    
    // Save mode preference to SPIFFS for persistence across reboots
    File modeFile = SPIFFS.open("/wifi_mode.txt", "w");
    if (modeFile) {
      modeFile.println(newMode == WIFI_AP_MODE ? "AP" : "CLIENT");
      modeFile.close();
    }
  }
  
  return success;
}

/**
 * Load saved WiFi mode preference from SPIFFS
 * 
 * Reads the last used WiFi mode from flash storage to maintain
 * user preference across device reboots.
 * 
 * @return WiFiMode enum value, defaults to CLIENT mode if no preference saved
 */
WiFiMode loadWiFiModePreference() {
  if (!SPIFFS.exists("/wifi_mode.txt")) {
    return WIFI_CLIENT_MODE;  // Default to client mode
  }
  
  File modeFile = SPIFFS.open("/wifi_mode.txt", "r");
  if (!modeFile) {
    return WIFI_CLIENT_MODE;
  }
  
  String mode = modeFile.readStringUntil('\n');
  modeFile.close();
  
  mode.trim();
  return (mode == "AP") ? WIFI_AP_MODE : WIFI_CLIENT_MODE;
}

/**
 * Perform NTP time synchronization, potentially switching WiFi modes temporarily
 * 
 * This function can be called from any WiFi mode and will attempt to synchronize
 * the system clock with NTP servers. If currently in AP mode, it will temporarily
 * switch to Client mode, perform the sync, then return to AP mode.
 * 
 * @param forceSync If true, attempt sync even if recently completed
 * @return true if NTP synchronization was successful, false otherwise
 * 
 * Educational note: This demonstrates a common embedded systems pattern where
 * a device temporarily changes modes to perform a specific operation, then
 * returns to its original state. This is useful for IoT devices that need
 * occasional internet connectivity but primarily operate standalone.
 */
bool performNtpSync(bool forceSync = false) {
  // Check if we need to sync (rate limiting to avoid excessive attempts)
  if (!forceSync && (millis() - lastNtpSyncAttempt < 60000)) {
    return ntpSyncCompleted;  // Return last known sync status
  }
  
  lastNtpSyncAttempt = millis();
  
  // Store original WiFi mode for restoration
  WiFiMode originalMode = currentWiFiMode;
  bool modeWasSwitched = false;
  
  statusMsg = "Attempting NTP sync...";
  displayStatus();
  
  try {
    // If we're in AP mode, temporarily switch to Client mode for NTP access
    if (currentWiFiMode == WIFI_AP_MODE) {
      statusMsg = "Switching to Client mode for NTP...";
      displayStatus();
      
      if (!connectToWiFi()) {
        statusMsg = "Failed to connect for NTP sync";
        displayStatus();
        return false;
      }
      
      modeWasSwitched = true;
      currentWiFiMode = WIFI_CLIENT_MODE;  // Temporary mode change
    }
    
    // Ensure we have a WiFi connection
    if (WiFi.status() != WL_CONNECTED) {
      statusMsg = "No WiFi connection for NTP";
      if (modeWasSwitched) {
        setupAccessPoint();  // Restore AP mode
        currentWiFiMode = originalMode;
      }
      displayStatus();
      return false;
    }
    
    // Initialize and attempt NTP synchronization
    statusMsg = "Synchronizing with NTP servers...";
    displayStatus();
    
    timeClient.begin();
    
    // Attempt NTP sync with timeout
    unsigned long syncStartTime = millis();
    bool syncSuccess = false;
    
    while (millis() - syncStartTime < NTP_SYNC_TIMEOUT) {
      if (timeClient.update()) {
        // NTP sync successful
        setTime(timeClient.getEpochTime());
        lastSuccessfulNtpSync = millis();
        ntpSyncCompleted = true;
        syncSuccess = true;
        break;
      }
      delay(500);  // Wait before retry
    }
    
    if (syncSuccess) {
      time_t now = timeClient.getEpochTime();
      statusMsg = "NTP sync successful: " + String(ctime(&now)).substring(0, 19);
    } else {
      statusMsg = "NTP sync timeout";
    }
    
    // Restore original WiFi mode if we switched
    if (modeWasSwitched && originalMode == WIFI_AP_MODE) {
      statusMsg += " - Returning to AP mode...";
      displayStatus();
      delay(1000);  // Give user time to see message
      
      setupAccessPoint();
      currentWiFiMode = originalMode;
    }
    
    displayStatus();
    return syncSuccess;
    
  } catch (...) {
    // Error handling - restore original mode
    statusMsg = "NTP sync error occurred";
    if (modeWasSwitched && originalMode == WIFI_AP_MODE) {
      setupAccessPoint();
      currentWiFiMode = originalMode;
    }
    displayStatus();
    return false;
  }
}

/**
 * Get formatted time sync status for display
 * 
 * @return String describing current NTP sync status and last sync time
 */
String getNtpSyncStatus() {
  if (!ntpSyncCompleted) {
    return "Never synchronized";
  }
  
  unsigned long timeSinceSync = millis() - lastSuccessfulNtpSync;
  if (timeSinceSync < 60000) {
    return "Synced " + String(timeSinceSync / 1000) + "s ago";
  } else if (timeSinceSync < 3600000) {
    return "Synced " + String(timeSinceSync / 60000) + "m ago";
  } else {
    return "Synced " + String(timeSinceSync / 3600000) + "h ago";
  }
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
 * 🎯 EDUCATIONAL BLOCK: Dual Output Manager
 * 
 * WHAT: Sends NMEA sentences to enabled output channels (GPIO UART and/or USB Serial)
 * WHY: Provides flexible output routing for different testing and deployment scenarios
 * HOW: Checks enable flags and outputs to active channels simultaneously
 * GOTCHAS: USB Serial (Serial) is same as debug console - may interfere with debugging
 * 
 * Example: GPIO for connecting to GPS receivers, USB for computer-based analysis tools
 * References: ESP32 Serial0=USB debug, Serial1=GPIO hardware UART
 */
void outputNMEASentence(const String& sentence) {
  // Output to GPIO UART (pins 32/33) if enabled
  // This is the primary output for connecting to GPS receivers or logic analyzers
  if (gpioOutputEnabled) {
    gpsSerial.println(sentence);  // Hardware UART1 on GPIO pins
  }
  
  // Output to USB Serial if enabled
  // This allows direct connection to computer without additional hardware
  if (usbOutputEnabled) {
    Serial.println(sentence);     // USB Serial port (UART0)
  }
  
  // Note: At least one output must always be enabled (enforced by web interface)
  // This prevents silent failures where NMEA data is generated but not transmitted
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
  
  // Generate complete sentence with checksum and send via configured outputs
  String fullSentence = createNMEASentence(sentence);
  outputNMEASentence(fullSentence);  // Send to enabled output channels (GPIO/USB)
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
  outputNMEASentence(fullSentence);
}

void sendGNGSA() {
  String sentence1 = "$GNGSA,A,3,01,02,04,31,,,,,,,,,6.27,4.89,3.92,1";
  String sentence2 = "$GNGSA,A,3,,,,,,,,,,,,,6.27,4.89,3.92,4";
  
  outputNMEASentence(createNMEASentence(sentence1));
  delay(50);
  outputNMEASentence(createNMEASentence(sentence2));
}

void sendGPGSV() {
  String sentence1 = "$GPGSV,2,1,05,01,57,120,12,02,28,127,27,04,43,173,23,17,,,21";
  String sentence2 = "$GPGSV,2,2,05,31,17,085,30";
  
  outputNMEASentence(createNMEASentence(sentence1));
  delay(50);
  outputNMEASentence(createNMEASentence(sentence2));
}

void sendBDGSV() {
  String sentence = "$BDGSV,1,1,00";
  outputNMEASentence(createNMEASentence(sentence));
}

void sendGNTXT() {
  String sentence = "$GNTXT,1,1,01,ANTENNA OK";
  outputNMEASentence(createNMEASentence(sentence));
}

void parseCSVLine(String line, GPSData& gps) {
  Serial.println("parseCSVLine(): entered");
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
    Serial.printf("loadCSV(): %s",statusMsg.c_str());
    return false;
  }
  
  csvFile = SPIFFS.open("/gps_track.csv", "r");
  if (!csvFile) {
    statusMsg = "Failed to open CSV";
    Serial.printf("loadCSV(): %s",statusMsg.c_str());
    return false;
  }
  
  // Skip header line
  csvFile.readStringUntil('\n');
  currentLine = 0;
  csvLoaded = true;
  statusMsg = "CSV loaded successfully";
  Serial.printf("loadCSV(): %s",statusMsg.c_str());
  return true;
}

GPSData getNextGPSData() {
  Serial.println("getNextGPSData(): entered");
  GPSData gps;
  if (!csvFile || !csvFile.available()) {
    Serial.println("getNextGPSData(): csv file not available");
    return gps; // Invalid GPS data
  }
  
  String line = csvFile.readStringUntil('\n');
  if (line.length() > 0) {
    Serial.printf("getNextGPSData(): parse next line %i\n",currentLine);
    parseCSVLine(line, gps);
    currentLine++;
  }
  else
  {
    Serial.println("getNextGPSData(): line length 0");
  }
  
  return gps;
}

void simulateGPS() {
  if (!gpsSimActive || !csvLoaded) return;
  Serial.println("SimulateGPS(): entered");
  unsigned long now = millis();
  if (now - lastGpsOutput >= 1000) { // 1 second interval
    Serial.println("SimulateGPS(): send next simulated message");
    // Get current time and format as HHMMSS.00
    // Use NTP time if available and synchronized, otherwise use system time
    unsigned long epochTime;
    if (ntpSyncAvailable && currentWiFiMode == WIFI_CLIENT_MODE) {
      // In client mode with NTP available, get fresh NTP time periodically
      static unsigned long lastNtpRefresh = 0;
      if (millis() - lastNtpRefresh > 30000) {  // Refresh every 30 seconds
        Serial.println("SimulateGPS(): refreshing Time by NTP (30 second cycle)");
        timeClient.update();
        lastNtpRefresh = millis();
      }
      epochTime = timeClient.getEpochTime();
    } else if (ntpSyncCompleted) {
      // Use last known NTP time + elapsed time (more accurate than system clock)
      unsigned long elapsedSinceSync = millis() - lastSuccessfulNtpSync;
      epochTime = (lastSuccessfulNtpSync / 1000) + 946684800UL + (elapsedSinceSync / 1000);
    } else {
      // Fallback to system time if no NTP sync has occurred
      epochTime = millis() / 1000 + 946684800UL;  // Use system millis as fallback
    }
    
    int hours = (epochTime % 86400L) / 3600;
    int minutes = (epochTime % 3600) / 60;
    int seconds = epochTime % 60;
    
    char timeStr[12];
    sprintf(timeStr, "%02d%02d%02d.00", hours, minutes, seconds);
    currentGPS.utc_time = String(timeStr);
    
    if (currentGPS.valid) {
      Serial.println("SimulateGPS(): current gps is valid - send");
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
        Serial.println("SimulateGPS(): end of file reached");
        // Restart from beginning if we reach end of file
        csvFile.close();
        loadCSV();
        currentGPS = getNextGPSData();
      }
      else {
        Serial.println("SimulateGPS(): got next gps data");
      }
    }
    else {
      Serial.println("SimulateGPS(): current gps is invalid - skip");
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

const uint8_t RED_LED_GPIO = 10;
int redLEDStatus=LOW;

void toggleRedLED()
{
  redLEDStatus=!redLEDStatus;
  digitalWrite(RED_LED_GPIO, redLEDStatus); // switch off
}

void flashRedLED()
{
  toggleRedLED();
  delay(200);
  toggleRedLED();
}

void setup() {
  pinMode(RED_LED_GPIO, OUTPUT); // Red LED - the interior LED to M5 Stick
  toggleRedLED(); // initially off

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
  
  // Load saved WiFi mode preference
  currentWiFiMode = loadWiFiModePreference();
  
  // Initialize WiFi based on saved preference
  bool wifiConnected = false;
  
  if (currentWiFiMode == WIFI_AP_MODE) {
    // Even in AP mode preference, try to get NTP time first
    statusMsg = "Attempting NTP sync before AP mode...";
    displayStatus();
    
    if (performNtpSync(true)) {
      statusMsg = "NTP sync completed - starting AP mode";
      displayStatus();
      delay(2000);  // Show success message
    }
    
    // Now start AP mode (performNtpSync will have restored this if it switched modes)
    wifiConnected = setupAccessPoint();
    
  } else {
    // Client mode - connect and sync NTP
    wifiConnected = connectToWiFi();
    if (wifiConnected) {
      // Initialize and sync NTP in client mode
      ntpSyncAvailable = true;
      performNtpSync(true);  // Force initial sync
    }
  }
  
  if (!wifiConnected) {
    statusMsg = "WiFi setup failed - trying NTP then AP mode";
    displayStatus();
    
    // Final attempt: try to get time before falling back to AP
    performNtpSync(true);
    
    // Fallback to AP mode if client mode fails
    if (currentWiFiMode == WIFI_CLIENT_MODE) {
      setupAccessPoint();
    }
  }
  
  // Setup web server for OTA
  server.on("/", HTTP_GET, [](AsyncWebServerRequest *request) {
    // Generate current status information for display
    String wifiModeStr = (currentWiFiMode == WIFI_AP_MODE) ? "Access Point" : "Client";
    String wifiStatusStr = WiFi.status() == WL_CONNECTED ? "Connected" : "Disconnected";
    String ipAddress = WiFi.localIP().toString();
    String ssidName = (currentWiFiMode == WIFI_AP_MODE) ? String(AP_SSID) : WiFi.SSID();
    String csvStatus = csvLoaded ? "Loaded" : "Not loaded";
    String gpsStatus = gpsSimActive ? "Active" : "Stopped";
    String ntpStatus = ntpSyncAvailable ? "Available" : "Not available";
    String ntpSyncStatus = getNtpSyncStatus();
    
    String html = "<!DOCTYPE html><html><head><title>GPS Simulator Control</title>";
    html += "<meta name='viewport' content='width=device-width, initial-scale=1'>";
    html += "<style>body{font-family:Arial,sans-serif;margin:20px}.status-panel{background:#f0f0f0;padding:15px;border-radius:5px;margin-bottom:20px}";
    html += ".control-section{margin-bottom:25px}.button{background:#007cba;color:white;padding:10px 15px;text-decoration:none;border-radius:5px;margin:5px;display:inline-block}";
    html += ".button:hover{background:#005a87}.danger{background:#d32f2f}.danger:hover{background:#b71c1c}.success{background:#388e3c}.success:hover{background:#2e7d32}";
    html += "select,input[type='file']{padding:8px;margin:5px}</style></head><body>";
    html += "<h1>GPS Simulator Control Panel</h1>";
    
    // System Status Panel
    html += "<div class='status-panel'><h3>System Status</h3>";
    html += "<p><strong>WiFi Mode:</strong> " + wifiModeStr + " (" + wifiStatusStr + ")</p>";
    html += "<p><strong>Network:</strong> " + ssidName + " (IP: " + ipAddress + ")</p>";
    html += "<p><strong>NTP Status:</strong> " + ntpStatus + "</p>";
    html += "<p><strong>Time Sync:</strong> " + ntpSyncStatus + "</p>";
    html += "<p><strong>CSV File:</strong> " + csvStatus + "</p>";
    html += "<p><strong>GPS Output:</strong> " + gpsStatus + "</p></div>";
    
    // Output Configuration
    html += "<div class='control-section'><h3>Output Configuration</h3>";
    html += "<p><strong>Current Output:</strong> <span id='output-status'>Loading...</span></p>";
    html += "<div style='margin:10px 0'>";
    html += "<label><input type='checkbox' id='gpio-output'> GPIO Pins 32/33 (Hardware UART)</label><br>";
    html += "<label><input type='checkbox' id='usb-output'> USB Serial Port</label></div>";
    html += "<button onclick='updateOutputConfig()' class='button'>Update Output Configuration</button>";
    html += "<div id='output-message' style='margin-top:10px'></div>";
    html += "<p><small><strong>GPIO Output:</strong> Hardware connection for GPS modules/analyzers<br>";
    html += "<strong>USB Output:</strong> Direct computer connection<br>";
    html += "<em>Note: At least one output must be enabled</em></small></p></div>";
    
    // GPS Simulation Control
    html += "<div class='control-section'><h3>GPS Simulation Control</h3>";
    html += "<a href='/start' class='button success'>Start GPS Simulation</a>";
    html += "<a href='/stop' class='button danger'>Stop GPS Simulation</a>";
    html += "<p><small>NMEA output via configured channels at 9600 baud</small></p></div>";
    
    // GPS Data Management
    html += "<div class='control-section'><h3>GPS Data Management</h3>";
    html += "<form action='/upload' method='post' enctype='multipart/form-data'>";
    html += "<input type='file' name='csv' accept='.csv' required>";
    html += "<input type='submit' value='Upload GPS Track CSV' class='button'></form>";
    html += "<p><small>Upload CSV file with GPS track data (max 1MB)</small></p></div>";
    
    // System Maintenance
    html += "<div class='control-section'><h3>System Maintenance</h3>";
    html += "<a href='/update' target='_blank' class='button'>Firmware Update (OTA)</a>";
    html += "<a href='/status' class='button'>Detailed Status</a>";
    html += "<a href='/restart' class='button danger' onclick='return confirm(\"Restart?\")'>Restart Device</a></div>";
    
    // JavaScript
    html += "<script>";
    html += "function updateOutputStatus(){fetch('/status').then(r=>r.json()).then(d=>{";
    html += "document.getElementById('gpio-output').checked=d.gpio_output_enabled;";
    html += "document.getElementById('usb-output').checked=d.usb_output_enabled;";
    html += "var s=document.getElementById('output-status');";
    html += "if(d.gpio_output_enabled&&d.usb_output_enabled)s.textContent='GPIO + USB (Both active)';";
    html += "else if(d.gpio_output_enabled)s.textContent='GPIO only';";
    html += "else if(d.usb_output_enabled)s.textContent='USB only';";
    html += "else s.textContent='Error: No outputs enabled';";
    html += "}).catch(e=>document.getElementById('output-status').textContent='Error loading status');}";
    html += "function updateOutputConfig(){";
    html += "var gpio=document.getElementById('gpio-output').checked;";
    html += "var usb=document.getElementById('usb-output').checked;";
    html += "var msg=document.getElementById('output-message');";
    html += "if(!gpio&&!usb){msg.innerHTML='<span style=\"color:red\">Error: At least one output must be enabled</span>';return;}";
    html += "msg.innerHTML='<span style=\"color:blue\">Updating...</span>';";
    html += "var fd=new FormData();fd.append('gpio',gpio?'true':'false');fd.append('usb',usb?'true':'false');";
    html += "fetch('/output-config',{method:'POST',body:fd}).then(r=>r.json()).then(d=>{";
    html += "if(d.success){msg.innerHTML='<span style=\"color:green\">Configuration updated successfully</span>';updateOutputStatus();}";
    html += "else msg.innerHTML='<span style=\"color:red\">Error: '+d.error+'</span>';";
    html += "}).catch(e=>msg.innerHTML='<span style=\"color:red\">Network error</span>');}";
    html += "window.onload=function(){updateOutputStatus();};";
    html += "</script></body></html>";
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
  
  // WiFi mode switching endpoint
  server.on("/wifi-mode", HTTP_POST, [](AsyncWebServerRequest *request) {
    if (request->hasParam("mode", true)) {
      String mode = request->getParam("mode", true)->value();
      WiFiMode newMode = (mode == "ap") ? WIFI_AP_MODE : WIFI_CLIENT_MODE;
      
      if (switchWiFiMode(newMode)) {
        request->redirect("/");
      } else {
        request->send(500, "text/plain", "Failed to switch WiFi mode");
      }
    } else {
      request->send(400, "text/plain", "Missing mode parameter");
    }
  });
  
  // NTP synchronization endpoint
  server.on("/sync-ntp", HTTP_GET, [](AsyncWebServerRequest *request) {
    // Perform NTP sync (may temporarily switch WiFi modes)
    if (performNtpSync(true)) {
      request->send(200, "text/plain", "NTP synchronization successful");
    } else {
      request->send(500, "text/plain", "NTP synchronization failed");
    }
  });
  
  // Detailed status endpoint (JSON for API access)
  server.on("/status", HTTP_GET, [](AsyncWebServerRequest *request) {
    String json = "{";
    json += "\"wifi_mode\":\"" + String(currentWiFiMode == WIFI_AP_MODE ? "ap" : "client") + "\",";
    json += "\"wifi_connected\":" + String(WiFi.status() == WL_CONNECTED ? "true" : "false") + ",";
    json += "\"ip_address\":\"" + WiFi.localIP().toString() + "\",";
    json += "\"ssid\":\"" + (currentWiFiMode == WIFI_AP_MODE ? String(AP_SSID) : WiFi.SSID()) + "\",";
    json += "\"ntp_available\":" + String(ntpSyncAvailable ? "true" : "false") + ",";
    json += "\"ntp_sync_completed\":" + String(ntpSyncCompleted ? "true" : "false") + ",";
    json += "\"last_ntp_sync\":" + String(lastSuccessfulNtpSync) + ",";
    json += "\"ntp_sync_status\":\"" + getNtpSyncStatus() + "\",";
    json += "\"csv_loaded\":" + String(csvLoaded ? "true" : "false") + ",";
    json += "\"gps_active\":" + String(gpsSimActive ? "true" : "false") + ",";
    json += "\"current_line\":" + String(currentLine) + ",";
    json += "\"gpio_output_enabled\":" + String(gpioOutputEnabled ? "true" : "false") + ",";
    json += "\"usb_output_enabled\":" + String(usbOutputEnabled ? "true" : "false") + ",";
    json += "\"free_heap\":" + String(ESP.getFreeHeap()) + ",";
    json += "\"uptime_ms\":" + String(millis());
    
    // Add connected clients info for AP mode
    if (currentWiFiMode == WIFI_AP_MODE) {
      json += ",\"ap_clients\":" + String(WiFi.softAPgetStationNum());
    }
    
    json += "}";
    request->send(200, "application/json", json);
  });
  
  // Device restart endpoint
  server.on("/restart", HTTP_GET, [](AsyncWebServerRequest *request) {
    request->send(200, "text/plain", "Restarting GPS Simulator...");
    delay(1000);
    ESP.restart();
  });

  // Output configuration endpoint
  server.on("/output-config", HTTP_POST, [](AsyncWebServerRequest *request) {
    bool newGpioEnabled = gpioOutputEnabled;
    bool newUsbEnabled = usbOutputEnabled;
    
    // Parse GPIO output parameter
    if (request->hasParam("gpio", true)) {
      String gpioParam = request->getParam("gpio", true)->value();
      newGpioEnabled = (gpioParam == "true" || gpioParam == "1");
    }
    
    // Parse USB output parameter  
    if (request->hasParam("usb", true)) {
      String usbParam = request->getParam("usb", true)->value();
      newUsbEnabled = (usbParam == "true" || usbParam == "1");
    }
    
    // Validation: At least one output must be enabled
    if (!newGpioEnabled && !newUsbEnabled) {
      request->send(400, "application/json", 
        "{\"success\":false,\"error\":\"At least one output must be enabled\"}");
      return;
    }
    
    // Apply new configuration
    gpioOutputEnabled = newGpioEnabled;
    usbOutputEnabled = newUsbEnabled;
    
    // Update status message for display
    String outputStatus = "";
    if (gpioOutputEnabled && usbOutputEnabled) {
      outputStatus = "GPIO+USB";
    } else if (gpioOutputEnabled) {
      outputStatus = "GPIO only";
    } else {
      outputStatus = "USB only";
    }
    statusMsg = "Output: " + outputStatus;
    displayStatus();
    
    // Send success response
    String json = "{\"success\":true,\"gpio_enabled\":" + String(gpioOutputEnabled ? "true" : "false") + 
                  ",\"usb_enabled\":" + String(usbOutputEnabled ? "true" : "false") + "}";
    request->send(200, "application/json", json);
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
  
  // Only update NTP time in client mode
  if (ntpSyncAvailable) {
    static unsigned long lastNTPUpdate = 0;
    if (millis() - lastNTPUpdate > 60000) {  // Update every minute
      timeClient.update();
      lastNTPUpdate = millis();
    }
  }
  
  // Button A: Start/Stop simulation
  if (M5.BtnA.wasReleased()) {
    if (csvLoaded) {
      gpsSimActive = !gpsSimActive;
      if (gpsSimActive && !currentGPS.valid) {
        currentGPS = getNextGPSData();
      }
      statusMsg = gpsSimActive ? "GPS started" : "GPS stopped";
      displayStatus();
      Serial.printf("Button A: %s\n",statusMsg.c_str());
    }
  }
  
  // Button B: Switch WiFi Mode (short press) or NTP Sync (long press)
  static unsigned long btnBPressTime = 0;
  
  if (M5.BtnB.wasPressed()) {
    btnBPressTime = millis();
  }
  
  if (M5.BtnB.wasReleased()) {
    unsigned long pressDuration = millis() - btnBPressTime;
    
    if (pressDuration > 2000) {
      // Long press (>2 seconds): NTP Sync
      statusMsg = "Starting NTP sync...";
      displayStatus();
      
      if (performNtpSync(true)) {
        statusMsg = "NTP sync successful";
      } else {
        statusMsg = "NTP sync failed";
      }
      displayStatus();
      Serial.printf("Button B: %s\n",statusMsg.c_str());
    } else {
      // Short press: Switch WiFi Mode
      WiFiMode newMode = (currentWiFiMode == WIFI_AP_MODE) ? WIFI_CLIENT_MODE : WIFI_AP_MODE;
      if (switchWiFiMode(newMode)) {
        statusMsg = "WiFi mode switched";
      } else {
        statusMsg = "WiFi mode switch failed";
      }
      displayStatus();
      Serial.printf("Button B: %s\n",statusMsg.c_str());
    }
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
