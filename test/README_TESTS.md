GPS Simulator Test Suite
=========================

This directory contains test scripts to validate the GPS simulator functionality, including comprehensive dual output testing.

## Core Test Scripts

### NMEA Output Testing
- **test_nmea.py**: Test NMEA output validation (single or dual output modes)
- **test_dual_output.py**: Comprehensive dual output functionality testing
- **test_usb_output.py**: USB Serial output specific testing
- **nmea_format_validator.py**: Validate NMEA sentence format compliance

### Web Interface Testing  
- **test_web_interface.py**: Test web interface functionality (enhanced with output configuration)

### Hardware Verification
- **test_sigrok_verification.py**: Hardware verification using logic analyzers

### Automation
- **run_verification.sh**: Run all tests automatically with dual output support

## New Dual Output Features

The test suite now includes comprehensive testing for the GPS Simulator's dual output capability:

- **GPIO UART Output**: Hardware UART1 on pins 32/33 at 9600 baud
- **USB Serial Output**: USB Serial port (UART0) at 9600 baud  
- **Simultaneous Operation**: Both outputs active with synchronized NMEA streams
- **Dynamic Configuration**: Web interface controls for output selection

## Requirements

```bash
# Python packages
pip install pyserial requests

# For logic analyzer verification (optional)
sudo apt-get install sigrok-cli    # Linux
brew install sigrok-cli            # macOS
```

## Quick Start

### Single Output Testing (USB Serial)
```bash
python test_usb_output.py 192.168.4.1 /dev/ttyUSB0
```

### Dual Output Testing  
```bash
python test_dual_output.py 192.168.4.1 /dev/ttyUSB0 /dev/ttyUSB1
```

### NMEA Comparison (GPIO vs USB)
```bash
python test_nmea.py /dev/ttyUSB0 9600 --dual-test /dev/ttyUSB1
```

### Complete Test Suite
```bash
./run_verification.sh --dual-only
```

## Test Coverage

- ✅ Output configuration API validation
- ✅ USB Serial output testing
- ✅ GPIO UART output testing
- ✅ Simultaneous dual output testing
- ✅ NMEA sentence validation and checksums
- ✅ Timing synchronization between outputs
- ✅ Web interface configuration controls
- ✅ Hardware-level verification (logic analyzer)
- ✅ Error handling and edge cases

## Documentation

See **DUAL_OUTPUT_TESTING.md** for comprehensive testing procedures, expected results, and troubleshooting guides.

## Usage Examples

### Basic Testing
```bash
# Test web interface and output configuration
python test_web_interface.py 192.168.4.1

# Test USB output only
python test_usb_output.py 192.168.4.1 /dev/ttyUSB0

# Test dual output functionality  
python test_dual_output.py 192.168.4.1 /dev/ttyUSB0 /dev/ttyUSB1
```

### Advanced Testing
```bash
# Complete verification suite
./run_verification.sh

# Specific test modes
./run_verification.sh --usb-only    # USB Serial tests only
./run_verification.sh --dual-only   # Dual output tests only
./run_verification.sh --nmea-only   # NMEA validation only

# Non-interactive with parameters
./run_verification.sh -i 192.168.4.1 -s /dev/ttyUSB0
```

### Hardware Verification
```bash
# With logic analyzer (professional verification)
python test_sigrok_verification.py 10

# NMEA format validation
python nmea_format_validator.py capture.log
```

The test suite validates that both output channels produce identical, valid NMEA streams suitable for GPS receiver testing and development workflows.