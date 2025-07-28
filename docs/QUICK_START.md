# GPS Simulator Quick Start Guide

## Prerequisites

- ESP32 M5 Stick C Plus development board
- VS Code with PlatformIO extension installed
- USB-C cable for programming
- GPS receiver or logic analyzer for testing (optional)

## Hardware Setup

1. **Connect M5 Stick C Plus to computer** via USB-C cable
2. **NMEA Output Options**:
   - **USB Serial**: Direct output via USB cable connection (default enabled)
   - **GPIO Hardware UART**: GPIO 32 → GPS RX (or test equipment), GND → Common ground (default enabled)
   - GPIO 33 is configured but not used (TX-only simulation)
   - Both outputs can be used simultaneously or individually configured

## Software Setup

### 1. Clone and Open Project
```bash
git clone <repository-url>
cd gps-sim
code .  # Opens in VS Code
```

### 2. WiFi Configuration
The GPS Simulator supports two WiFi modes:

#### **Access Point Mode (Recommended for field use)**
- **SSID**: `GPS-SIM`
- **Password**: `cool-sim`
- **IP Address**: `192.168.4.1`
- **Advantages**: Works anywhere, no network dependency, instant setup
- **Limitations**: No internet access, no NTP time sync

#### **Client Mode (For internet connectivity)**
WiFi credentials are configured in `src/mercator_secrets.c`:
- Multiple networks with automatic fallback
- Provides NTP time synchronization
- Modify credentials as needed for your environment

**Switching Modes:**
- **Hardware**: Press Button B on M5StickC Plus
- **Web Interface**: Use WiFi Configuration section
- **Default**: Client mode, falls back to AP mode if no networks available

### 3. Build and Upload
```bash
# Build project
pio run

# Upload to device
pio run --target upload

# Monitor serial output (optional)
pio device monitor
```

## First Run

### 1. Power On
- Device displays "GPS Simulator" screen
- Shows WiFi connection status
- Displays IP address when connected

### 2. Access Web Interface

#### **Access Point Mode (Default):**
- Connect device to WiFi network: `GPS-SIM` (password: `cool-sim`)
- Open browser to: `http://192.168.4.1/`

#### **Client Mode:**
- Device connects to existing WiFi and displays IP address
- Open browser to displayed IP (example: `http://192.168.1.100`)

### 3. Upload GPS Track
- Click "Upload GPS Track CSV"
- Select a CSV file with GPS coordinates
- File format: Must contain `coordinates` column with `[latitude, longitude]`
- Maximum size: 1MB

### 4. Configure Outputs (Optional)
- **Output Configuration** section allows enabling/disabling outputs:
  - **GPIO Output**: Hardware UART on pins 32/33 for connecting GPS receivers
  - **USB Output**: Serial output via USB connection for computer analysis
  - At least one output must be enabled
- Default: Both outputs enabled for maximum compatibility

### 5. Start Simulation
- Click "Start GPS Simulation" or press Button A
- NMEA sentences begin outputting on configured channels at 9600 baud
- Status shown on device display

## Hardware Controls

- **Button A**: Start/Stop GPS simulation
- **Button B**: Switch WiFi mode (AP ↔ Client)
- **Reset Button**: Restart device

## Testing the Output

### Option 1: USB Serial Output (Easiest)
```bash
# Direct USB connection (no additional hardware needed)
# Set terminal to 9600 baud, 8N1
screen /dev/ttyUSB0 9600
# or on some systems:
screen /dev/ttyACM0 9600
# Windows: Use Putty or Device Manager to find COM port
```

### Option 2: GPIO Hardware UART
```bash
# Connect USB-Serial adapter to GPIO 32
# Set terminal to 9600 baud, 8N1
screen /dev/ttyUSB1 9600  # Note: may be different port than USB programming
# or
minicom -D /dev/ttyUSB1 -b 9600
```

### Expected Output
```
$GNRMC,123456.00,A,5123.49091,N,00017.24547,W,0.233,,220725,,,A,V*09
$GNGGA,123456.00,5123.49091,N,00017.24547,W,1,04,4.89,56.3,M,46.9,M,,*67
$GNGSA,A,3,01,02,04,31,,,,,,,,,6.27,4.89,3.92,1*0A
...
```

### Using Provided Test Scripts
```bash
# Test NMEA output validation
cd test/
python test_nmea.py /dev/ttyUSB0 9600

# Test web interface
python test_web_interface.py 192.168.1.100
```

## Troubleshooting

### Device Won't Connect to WiFi
- Check WiFi credentials in `src/mercator_secrets.c`
- Ensure network is 2.4GHz (ESP32 limitation)
- Move closer to router

### No NMEA Output
- Check output configuration (web interface → Output Configuration)
- Verify connections if using GPIO output (GPIO 32)
- For USB output, check correct serial port
- Check that CSV file is loaded (display shows "CSV: Loaded")
- Ensure simulation is started (display shows "GPS: Active")
- Device display shows current output configuration ("GPIO+USB", "GPIO only", or "USB only")
- Test with provided test scripts

### CSV Upload Fails
- Check file size (must be < 1MB)
- Ensure file is valid CSV format
- Verify coordinates are in `[lat, lng]` format

### Web Interface Not Accessible
- Check IP address on device display
- Ensure you're on same WiFi network
- Try accessing individual endpoints: `/start`, `/stop`

## Sample CSV Format

Create a test CSV file:
```csv
UTC_time,coordinates,sats,hdop,gps_course,gps_speed_knots
17:07:30,"[51.459595, -0.547948]",6,2.3,45.0,0.1
17:07:31,"[51.459598, -0.547957]",6,2.2,46.0,0.5
17:07:32,"[51.4596, -0.547957]",6,2.2,47.0,1.0
```

## Quick Commands Reference

```bash
# Build only
pio run

# Upload firmware
pio run --target upload

# Serial monitor
pio device monitor

# Clean build
pio run --target clean

# Upload filesystem (if needed)
pio run --target uploadfs
```

## Next Steps

1. **Upload your own GPS track data** in CSV format
2. **Connect to actual GPS receiver** for testing
3. **Explore the web interface** for remote control
4. **Modify the code** to add custom NMEA sentences
5. **Read the technical documentation** in `docs/TECHNICAL_OVERVIEW.md`

## Support

- Check `docs/README.md` for detailed documentation
- Review the heavily commented source code in `src/main.cpp`
- Use the test scripts in `test/` for validation
- Examine sample data in `samples/` for format examples