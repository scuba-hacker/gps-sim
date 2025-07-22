# GPS Simulator Verification Guide

## Overview

This guide explains how to verify that your GPS simulator produces authentic NMEA output using professional tools, specifically sigrok logic analyzers. This verification approach uses the same methodology that generated the reference sample data.

## Hardware Verification Setup

### Required Equipment

1. **Logic Analyzer** compatible with sigrok:
   - Saleae Logic (fx2lafw driver)
   - DSLogic series
   - Compatible USB logic analyzers
   
2. **Connections**:
   ```
   ESP32 M5 StickC Plus          Logic Analyzer
   ┌─────────────────┐          ┌──────────────┐
   │                 │          │              │
   │    GPIO 32 (TX) │ ────────►│ Channel D1   │
   │                 │          │              │
   │           GND   │ ────────►│ GND          │
   └─────────────────┘          └──────────────┘
   ```

3. **Software Requirements**:
   - sigrok-cli installed
   - PulseView (optional, for visual analysis)
   - Python 3.6+ for analysis scripts

## Verification Methods

### Method 1: Automated Sigrok Verification (Recommended)

This method captures live NMEA output and compares it to reference data:

```bash
# Run automated verification
cd test/
python test_sigrok_verification.py 10 ../samples/sigrok-logic-output-neo6m.log
```

**What it does**:
- Captures 10 seconds of GPS output using logic analyzer
- Decodes UART protocol at 9600 baud
- Validates NMEA checksums
- Analyzes timing intervals (should be 1 second)
- Compares sentence types and structure to reference
- Generates detailed verification report

### Method 2: Manual Sigrok Capture

For manual analysis and debugging:

```bash
# Capture GPS output to file
sigrok-cli \
  --driver fx2lafw \
  --channels D1 \
  --config samplerate=1MHz \
  --samples 10000000 \
  -P uart:rx=D1:baudrate=9600:format=ascii_stream \
  -A uart \
  --output-file my_gps_capture.log

# Compare manually with reference
diff -u samples/sigrok-logic-output-neo6m.log my_gps_capture.log
```

### Method 3: Real-time Monitoring

For live monitoring during development:

```bash
# Real-time NMEA stream (no file output)
sigrok-cli \
  --driver fx2lafw \
  --channels D1 \
  --config samplerate=1MHz \
  --continuous \
  -P uart:rx=D1:baudrate=9600:format=ascii_stream \
  -A uart
```

## What to Verify

### 1. NMEA Sentence Structure
✅ **Expected Output Pattern (every 1 second)**:
```
$GNRMC,123456.00,A,5123.49091,N,00017.24547,W,0.233,,220725,,,A,V*09
$GNGGA,123456.00,5123.49091,N,00017.24547,W,1,04,4.89,56.3,M,46.9,M,,*67
$GNGSA,A,3,01,02,04,31,,,,,,,,,6.27,4.89,3.92,1*0A
$GNGSA,A,3,,,,,,,,,,,,,6.27,4.89,3.92,4*0A
$GPGSV,2,1,05,01,57,120,12,02,28,127,27,04,43,173,23,17,,,21,0*5B
$GPGSV,2,2,05,31,17,085,30,0*5A
$BDGSV,1,1,00,0*74
$GNTXT,1,1,01,ANTENNA OK*2B
```

### 2. Timing Verification
- **Interval**: GPS fixes every 1.000 ± 0.010 seconds
- **Consistency**: No missed intervals or double transmissions
- **Sequence**: Messages in correct order within each fix

### 3. Data Integrity
- **Checksums**: All NMEA sentences must have valid checksums
- **Format**: Coordinates in proper DDMM.MMMMM format
- **Values**: Reasonable GPS data (valid lat/lng, speed, course)

### 4. Protocol Compliance
- **UART**: 9600 baud, 8N1, proper signal levels
- **Line Endings**: \r\n termination
- **Character Set**: ASCII only, no binary data

## Verification Results Interpretation

### Automated Report Analysis

The verification script generates a report with these sections:

```
GPS Simulator Verification Report
=================================

SENTENCE COUNT COMPARISON:
  Captured: 85 sentences     ← Should be ~8 per second
  Reference: 87 sentences

SENTENCE TYPE ANALYSIS:
  Captured sentence types:
    $GNRMC: 10              ← 1 per second
    $GNGGA: 10              ← 1 per second
    $GNGSA: 20              ← 2 per second
    $GPGSV: 20              ← 2 per second
    $BDGSV: 10              ← 1 per second
    $GNTXT: 10              ← 1 per second

CHECKSUM VALIDATION:
  Invalid checksums: 0       ← Must be 0 for valid output

TIMING ANALYSIS:
  Average interval: 1.002s   ← Should be ~1.000s
  Target interval: 1.000s
  Timing accurate: true      ← Must be true

VERIFICATION VERDICT:
  ✅ GPS SIMULATOR OUTPUT VERIFIED - EXCELLENT
```

### Pass/Fail Criteria

**✅ PASS Criteria**:
- Zero checksum errors
- Timing accuracy within ±100ms (0.9s - 1.1s average)
- All expected sentence types present
- Proper NMEA format structure

**❌ FAIL Criteria**:
- Any checksum errors
- Timing drift > 100ms
- Missing sentence types
- Malformed NMEA sentences

## Troubleshooting

### Logic Analyzer Not Detected

```bash
# Check available devices
sigrok-cli --scan

# If no devices found:
# 1. Check USB connection
# 2. Install proper drivers (fx2lafw, etc.)
# 3. Check user permissions (Linux: add to dialout group)
```

### No UART Data Captured

1. **Check Connections**:
   - GPIO 32 → Logic Analyzer Channel D1
   - Common ground connected
   - No reversed connections

2. **Verify ESP32 Output**:
   ```bash
   # Test with oscilloscope or multimeter
   # GPIO 32 should show ~3.3V idle, switching to 0V for data
   ```

3. **Check Simulation Status**:
   - CSV file loaded on device?
   - GPS simulation started?
   - Green "GPS: Active" on display?

### Timing Issues

- **Slow Timing**: Check NTP synchronization
- **Fast Timing**: Verify millis() calculation in code
- **Irregular Timing**: Check for blocking operations in main loop

### Checksum Errors

- **Systematic Errors**: Check checksum calculation algorithm
- **Random Errors**: Check UART signal integrity, EMI
- **All Errors**: Verify NMEA sentence construction

## Advanced Verification

### Signal Quality Analysis

Use PulseView for detailed signal analysis:

1. Open captured data in PulseView
2. Add UART decoder
3. Analyze signal quality:
   - Clean edges (no ringing/overshoot)
   - Proper voltage levels (0V/3.3V)
   - Consistent bit timing

### Comparative Testing

Compare with real GPS module:

```bash
# Capture real GPS module
sigrok-cli --driver fx2lafw --channels D0 \
  --config samplerate=1MHz --samples 10000000 \
  -P uart:rx=D0:baudrate=9600:format=ascii_stream \
  -A uart --output-file real_gps.log

# Capture simulator
sigrok-cli --driver fx2lafw --channels D1 \
  --config samplerate=1MHz --samples 10000000 \
  -P uart:rx=D1:baudrate=9600:format=ascii_stream \
  -A uart --output-file sim_gps.log

# Compare outputs
python test_sigrok_verification.py --compare real_gps.log sim_gps.log
```

### Long-term Stability

Test extended operation:

```bash
# 1-hour capture for stability testing
python test_sigrok_verification.py 3600 ../samples/sigrok-logic-output-neo6m.log
```

## Integration with CI/CD

For automated testing in development:

```bash
#!/bin/bash
# verify_gps_output.sh - CI/CD verification script

echo "Starting GPS simulator verification..."

# Flash latest firmware
pio run --target upload

# Wait for startup
sleep 5

# Run verification
python test/test_sigrok_verification.py 30

# Check results
if grep -q "✅ GPS SIMULATOR OUTPUT VERIFIED" verification_report.txt; then
    echo "✅ Verification PASSED"
    exit 0
else
    echo "❌ Verification FAILED"
    cat verification_report.txt
    exit 1
fi
```

This verification approach provides professional-grade validation that your GPS simulator produces authentic, timing-accurate NMEA output that would be indistinguishable from a real GPS module to receiving equipment.