# GPS Simulator Quick Start Guide

## Prerequisites

- ESP32 M5 Stick C Plus development board
- VS Code with PlatformIO extension installed
- USB-C cable for programming
- GPS receiver or logic analyzer for testing (optional)

## Hardware Setup

1. **Connect M5 Stick C Plus to computer** via USB-C cable
2. **GPS Output Connections**:
   - GPIO 32 → GPS RX (or test equipment)
   - GND → Common ground
   - GPIO 33 is configured but not used (TX-only simulation)

## Software Setup

### 1. Clone and Open Project
```bash
git clone <repository-url>
cd gps-sim
code .  # Opens in VS Code
```

### 2. WiFi Configuration
WiFi credentials are already configured in `src/mercator_secrets.c`:
- Multiple networks with automatic fallback
- Modify as needed for your environment

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
- Open browser to displayed IP address
- Example: `http://192.168.1.100`

### 3. Upload GPS Track
- Click "Upload GPS Track CSV"
- Select a CSV file with GPS coordinates
- File format: Must contain `coordinates` column with `[latitude, longitude]`
- Maximum size: 1MB

### 4. Start Simulation
- Click "Start GPS Simulation" or press Button A
- NMEA sentences begin outputting on GPIO 32 at 9600 baud
- Status shown on device display

## Hardware Controls

- **Button A**: Start/Stop GPS simulation
- **Button B**: Reload CSV file from storage
- **Reset Button**: Restart device

## Testing the Output

### Using Serial Monitor
```bash
# Connect USB-Serial adapter to GPIO 32
# Set terminal to 9600 baud, 8N1
screen /dev/ttyUSB0 9600
# or
minicom -D /dev/ttyUSB0 -b 9600
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
- Verify GPIO 32 connections
- Check that CSV file is loaded (display shows "CSV: Loaded")
- Ensure simulation is started (display shows "GPS: Active")
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