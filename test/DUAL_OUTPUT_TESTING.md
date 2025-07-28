# Dual Output Testing Guide

This document provides comprehensive testing procedures for the GPS Simulator's dual output functionality, which enables simultaneous NMEA sentence transmission via both GPIO UART and USB Serial channels.

## Overview

The GPS Simulator now supports two independent output channels:
- **GPIO UART**: Hardware UART1 on pins 32/33 at 9600 baud (for connecting to GPS receivers, logic analyzers)
- **USB Serial**: USB Serial port (UART0) at 9600 baud (for direct computer connection)

Both outputs can be enabled simultaneously or individually controlled via the web interface.

## Test Scripts

### 1. `test_dual_output.py` - Comprehensive Dual Output Testing

**Purpose**: Tests all aspects of dual output functionality including configuration, simultaneous output, and timing synchronization.

**Usage**:
```bash
python test_dual_output.py <device_ip> <usb_port> <gpio_port>

# Examples:
python test_dual_output.py 192.168.1.100 /dev/ttyUSB0 /dev/ttyUSB1
python test_dual_output.py 192.168.4.1 COM3 COM4
```

**Test Coverage**:
- ✅ Output configuration API validation
- ✅ USB Serial output-only mode
- ✅ GPIO UART output-only mode  
- ✅ Simultaneous dual output mode
- ✅ Timing synchronization between outputs
- ✅ Error handling and validation
- ✅ NMEA sentence consistency

**Expected Results**:
- All 6 tests should pass
- Both outputs should produce identical NMEA streams
- GPS fix intervals should be 1.000 ±0.1 seconds
- At least 95% of sentences should be valid

### 2. `test_usb_output.py` - USB Serial Specific Testing

**Purpose**: Focused testing of USB Serial output functionality.

**Usage**:
```bash
python test_usb_output.py <device_ip> <usb_port>

# Examples:
python test_usb_output.py 192.168.1.100 /dev/ttyUSB0
python test_usb_output.py 192.168.4.1 COM3
```

**Test Coverage**:
- ✅ USB-only output configuration
- ✅ NMEA sentence validation and checksums
- ✅ Sentence content analysis (GNRMC, GNGGA parsing)
- ✅ Configuration persistence
- ✅ Expected sentence types (GNRMC, GNGGA, GNGSA, GPGSV, etc.)

### 3. `test_nmea.py` - Enhanced with Dual Output Support

**Purpose**: Updated NMEA validation script with dual output comparison.

**Usage**:
```bash
# Single output mode (existing functionality)
python test_nmea.py /dev/ttyUSB0 9600

# Dual output comparison mode (new functionality)
python test_nmea.py /dev/ttyUSB0 9600 --dual-test /dev/ttyUSB1
```

**Dual Output Test Coverage**:
- ✅ Parallel data collection from both ports
- ✅ Sentence count comparison
- ✅ Content overlap analysis (should be >80%)
- ✅ Validation rate comparison
- ✅ Sentence type consistency

### 4. `test_web_interface.py` - Enhanced with Output Configuration

**Purpose**: Updated web interface testing with dual output configuration API.

**New Test Coverage**:
- ✅ Status endpoint includes `gpio_output_enabled` and `usb_output_enabled` fields
- ✅ `/output-config` POST endpoint functionality
- ✅ Configuration validation (prevents disabling both outputs)
- ✅ Configuration persistence and status reflection

## Test Setup Requirements

### Hardware Requirements

**For Full Dual Output Testing**:
- ESP32 M5 Stick C Plus with GPS Simulator firmware
- 2x USB-Serial adapters or equivalent serial ports
- GPIO connections: ESP32 GPIO 32 → Serial adapter RX, common GND

**For USB-Only Testing**:
- ESP32 M5 Stick C Plus with GPS Simulator firmware
- 1x USB connection (programming cable)

**For Logic Analyzer Verification**:
- Compatible logic analyzer (sigrok-supported)
- Probe connections: ESP32 GPIO 32 → Logic analyzer D1, common GND

### Software Requirements

```bash
# Required Python packages
pip install pyserial requests

# Optional for logic analyzer verification
sudo apt-get install sigrok-cli  # Linux
brew install sigrok-cli          # macOS
```

## Testing Procedures

### Quick Dual Output Test

1. **Setup Hardware**:
   ```bash
   # Connect two serial adapters:
   # USB1: ESP32 USB port (/dev/ttyUSB0)
   # USB2: ESP32 GPIO 32 → Serial RX (/dev/ttyUSB1)
   ```

2. **Run Comprehensive Test**:
   ```bash
   cd test/
   python test_dual_output.py 192.168.4.1 /dev/ttyUSB0 /dev/ttyUSB1
   ```

3. **Verify Results**:
   - All 6 tests should pass
   - Look for "🎉 ALL TESTS PASSED!" message
   - Check timing accuracy (should be ~1.000s intervals)

### Manual Configuration Testing

1. **Test Output Configuration API**:
   ```bash
   # Configure GPIO only
   curl -X POST -d "gpio=true&usb=false" http://192.168.4.1/output-config
   
   # Configure USB only  
   curl -X POST -d "gpio=false&usb=true" http://192.168.4.1/output-config
   
   # Configure both outputs
   curl -X POST -d "gpio=true&usb=true" http://192.168.4.1/output-config
   
   # Try invalid configuration (should fail)
   curl -X POST -d "gpio=false&usb=false" http://192.168.4.1/output-config
   ```

2. **Verify Status**:
   ```bash
   curl http://192.168.4.1/status | jq '.gpio_output_enabled, .usb_output_enabled'
   ```

### Performance Testing

1. **Long-Duration Test**:
   ```bash
   # Run for extended period to check stability
   timeout 300 python test_dual_output.py 192.168.4.1 /dev/ttyUSB0 /dev/ttyUSB1
   ```

2. **Rapid Configuration Changes**:
   ```bash
   # Test configuration switching under load
   ./test_rapid_config_changes.sh  # Custom script for stress testing
   ```

## Automated Testing with run_verification.sh

The main verification script has been enhanced with dual output support:

```bash
# Run all tests including dual output
./run_verification.sh

# Run only dual output tests
./run_verification.sh --dual-only

# Run only USB output tests  
./run_verification.sh --usb-only

# Specify parameters for non-interactive testing
./run_verification.sh -i 192.168.4.1 -s /dev/ttyUSB0
```

**New Command Line Options**:
- `--usb-only`: Run only USB Serial output tests
- `--dual-only`: Run only comprehensive dual output tests
- Enhanced `--nmea-only`: Now supports dual port comparison

## Expected Test Results

### Successful Test Indicators

**Dual Output Functionality**:
- ✅ Configuration API returns success for valid configurations
- ✅ Configuration API returns 400 error for invalid configurations (both disabled)
- ✅ Both outputs produce valid NMEA sentences (>95% success rate)
- ✅ Sentence overlap between outputs >80%
- ✅ GPS timing intervals within 1.000 ±0.1 seconds
- ✅ Expected sentence types present (GNRMC, GNGGA, GNGSA, GPGSV, BDGSV, GNTXT)

**Performance Metrics**:
- ✅ Sentence rate: ~6-8 sentences per second per output
- ✅ Data consistency: Identical content on both outputs
- ✅ Timing synchronization: <10ms variance between outputs
- ✅ Memory stability: No memory leaks during extended operation

### Common Issues and Solutions

**Issue**: No output on GPIO UART
- **Solution**: Check GPIO 32 wiring, ensure common ground, verify serial adapter compatibility

**Issue**: USB Serial not working
- **Solution**: Check USB cable, verify correct port (/dev/ttyUSB0 vs /dev/ttyACM0), ensure driver installation

**Issue**: Configuration API returns errors
- **Solution**: Verify device IP, check network connectivity, ensure device is running latest firmware

**Issue**: Timing intervals inconsistent
- **Solution**: Check for WiFi interference, verify NTP synchronization, ensure stable power supply

**Issue**: Low sentence validation rate
- **Solution**: Check serial port configuration (9600 8N1), verify UART signal levels, check for electrical interference

## Integration with CI/CD

The dual output tests can be integrated into continuous integration pipelines:

```yaml
# Example GitHub Actions integration
- name: Test Dual Output Functionality
  run: |
    cd test/
    python test_dual_output.py ${{ env.DEVICE_IP }} /dev/ttyUSB0 /dev/ttyUSB1
    python test_usb_output.py ${{ env.DEVICE_IP }} /dev/ttyUSB0
```

## Debugging and Troubleshooting

### Enable Debug Logging

Add debug output to test scripts:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Monitor Device Display

The M5StickC Plus display shows current output configuration:
- "GPIO+USB": Both outputs active
- "GPIO only": GPIO UART only  
- "USB only": USB Serial only

### Check Serial Port Status

```bash
# Linux: List available ports
ls -la /dev/tty*

# Check port permissions
sudo chmod 666 /dev/ttyUSB0

# Monitor port activity
sudo lsof /dev/ttyUSB0
```

### Network Diagnostics

```bash
# Check device connectivity
ping 192.168.4.1

# Test web interface manually
curl -v http://192.168.4.1/status

# Check WiFi mode
curl http://192.168.4.1/status | jq '.wifi_mode'
```

## Test Data Analysis

### Logging and Reports

All test scripts generate detailed logs:
- **Timestamps**: Precise timing for GPS fix intervals
- **Validation Results**: Pass/fail for each NMEA sentence
- **Configuration Changes**: API request/response logging
- **Performance Metrics**: Sentence rates, timing accuracy

### Statistical Analysis

Key metrics to monitor:
- **Sentence Validation Rate**: Should be >95%
- **Timing Accuracy**: GPS fixes at 1.000 ±0.100 second intervals
- **Output Consistency**: >80% sentence overlap between outputs
- **API Response Times**: <100ms for configuration changes

## Conclusion

The dual output testing framework provides comprehensive validation of the GPS Simulator's enhanced functionality. Regular testing ensures:

1. **Reliability**: Both output channels function consistently
2. **Accuracy**: NMEA sentences conform to specification
3. **Performance**: Timing and throughput meet GPS standards  
4. **Flexibility**: Configuration changes work as expected
5. **Compatibility**: Integration with existing GPS workflows

For additional support or to report issues with the dual output functionality, refer to the main project documentation or create detailed bug reports with test logs and hardware configuration details.