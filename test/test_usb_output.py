#!/usr/bin/env python3
"""
GPS Simulator USB Serial Output Test

This script specifically tests the USB Serial output functionality of the GPS simulator.
It focuses on validating that NMEA sentences are correctly transmitted via USB Serial port.

Requirements:
- Python 3.6+
- pyserial: pip install pyserial
- requests: pip install requests

Usage:
    python test_usb_output.py <device_ip> <usb_port>
    
Examples:
    python test_usb_output.py 192.168.1.100 /dev/ttyUSB0
    python test_usb_output.py 192.168.4.1 COM3
"""

import requests
import serial
import sys
import time
import re
from datetime import datetime, timedelta

def configure_usb_only_output(base_url):
    """Configure device for USB-only output"""
    print("Configuring device for USB-only output...")
    
    try:
        data = {"gpio": "false", "usb": "true"}
        response = requests.post(f"{base_url}/output-config", data=data)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print("✓ USB-only output configured successfully")
                return True
            else:
                print(f"✗ Configuration failed: {result.get('error', 'Unknown error')}")
                return False
        else:
            print(f"✗ Configuration request failed: {response.status_code}")
            return False
            
    except requests.RequestException as e:
        print(f"✗ Error configuring output: {e}")
        return False
    except ValueError as e:
        print(f"✗ Invalid JSON response: {e}")
        return False

def upload_test_csv(base_url):
    """Upload a test CSV file"""
    print("Uploading test CSV file...")
    
    # Create test CSV content
    csv_content = """UTC_time,coordinates,sats,hdop,gps_course,gps_speed_knots
17:07:30,"[51.459595, -0.547948]",6,2.3,45.0,0.1
17:07:31,"[51.459598, -0.547957]",6,2.2,46.0,0.5
17:07:32,"[51.4596, -0.547957]",6,2.2,47.0,1.0
17:07:33,"[51.459602, -0.547960]",6,2.2,48.0,1.5
17:07:34,"[51.459605, -0.547965]",8,2.1,49.0,2.0"""
    
    try:
        files = {'csv': ('test_gps_track.csv', csv_content.encode(), 'text/csv')}
        response = requests.post(f"{base_url}/upload", files=files)
        
        if response.status_code == 200:
            print("✓ Test CSV uploaded successfully")
            return True
        else:
            print(f"✗ CSV upload failed: {response.status_code}")
            return False
            
    except requests.RequestException as e:
        print(f"✗ Error uploading CSV: {e}")
        return False

def start_gps_simulation(base_url):
    """Start GPS simulation"""
    print("Starting GPS simulation...")
    
    try:
        response = requests.get(f"{base_url}/start")
        if response.status_code == 200:
            print("✓ GPS simulation started")
            return True
        else:
            print(f"✗ Failed to start simulation: {response.status_code}")
            return False
    except requests.RequestException as e:
        print(f"✗ Error starting simulation: {e}")
        return False

def stop_gps_simulation(base_url):
    """Stop GPS simulation"""
    try:
        response = requests.get(f"{base_url}/stop")
        return response.status_code == 200
    except requests.RequestException:
        return False

def validate_nmea_sentence(sentence):
    """Validate an NMEA sentence format and checksum"""
    sentence = sentence.strip()
    
    if not sentence.startswith('$'):
        return False, "Sentence doesn't start with $"
    
    if '*' not in sentence:
        return False, "No checksum delimiter (*) found"
    
    # Extract and validate checksum
    try:
        content = sentence[1:sentence.find('*')]
        checksum_str = sentence[sentence.find('*')+1:]
        expected_checksum = int(checksum_str, 16)
        
        calculated_checksum = 0
        for char in content:
            calculated_checksum ^= ord(char)
        
        if calculated_checksum != expected_checksum:
            return False, f"Checksum mismatch: expected {expected_checksum:02X}, got {calculated_checksum:02X}"
        
        return True, "Valid"
        
    except (ValueError, IndexError):
        return False, "Invalid checksum format"

def analyze_nmea_sentences(sentences):
    """Analyze captured NMEA sentences"""
    sentence_types = {}
    valid_count = 0
    total_count = len(sentences)
    timing_intervals = []
    last_timestamp = None
    
    for timestamp, sentence in sentences:
        # Count sentence types
        if len(sentence) >= 6:
            sentence_type = sentence[1:6]  # Extract sentence type (e.g., GNRMC)
            sentence_types[sentence_type] = sentence_types.get(sentence_type, 0) + 1
        
        # Validate sentence
        is_valid, _ = validate_nmea_sentence(sentence)
        if is_valid:
            valid_count += 1
        
        # Calculate timing intervals for GPS fixes
        if sentence.startswith('$GNRMC') and last_timestamp is not None:
            interval = timestamp - last_timestamp
            timing_intervals.append(interval)
        
        if sentence.startswith('$GNRMC'):
            last_timestamp = timestamp
    
    return {
        'sentence_types': sentence_types,
        'valid_count': valid_count,
        'total_count': total_count,
        'success_rate': (valid_count / total_count) * 100 if total_count > 0 else 0,
        'timing_intervals': timing_intervals,
        'avg_interval': sum(timing_intervals) / len(timing_intervals) if timing_intervals else 0
    }

def test_usb_serial_output(usb_port, capture_duration=10):
    """Test USB Serial output"""
    print(f"Testing USB Serial output on {usb_port}...")
    
    try:
        # Open serial connection
        ser = serial.Serial(usb_port, 9600, timeout=1)
        print(f"✓ Connected to {usb_port} at 9600 baud")
        
        sentences = []
        start_time = time.time()
        
        print(f"Capturing NMEA data for {capture_duration} seconds...")
        
        while (time.time() - start_time) < capture_duration:
            try:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line and line.startswith('$'):
                    sentences.append((time.time(), line))
            except Exception as e:
                print(f"⚠ Error reading from serial: {e}")
        
        ser.close()
        
        if not sentences:
            print("✗ No NMEA sentences received")
            return False
        
        print(f"✓ Captured {len(sentences)} NMEA sentences")
        
        # Analyze sentences
        analysis = analyze_nmea_sentences(sentences)
        
        print(f"✓ Validation: {analysis['valid_count']}/{analysis['total_count']} valid ({analysis['success_rate']:.1f}%)")
        print(f"✓ Sentence types: {', '.join(analysis['sentence_types'].keys())}")
        
        if analysis['timing_intervals']:
            print(f"✓ Average GPS fix interval: {analysis['avg_interval']:.3f}s (target: 1.000s)")
            
            # Check timing accuracy
            if abs(analysis['avg_interval'] - 1.0) > 0.2:  # Allow 200ms variance
                print("⚠ GPS timing intervals are outside expected range")
            else:
                print("✓ GPS timing intervals are within acceptable range")
        
        # Check for expected sentence types
        expected_types = ['GNRMC', 'GNGGA', 'GNGSA', 'GPGSV']
        missing_types = [t for t in expected_types if t not in analysis['sentence_types']]
        
        if missing_types:
            print(f"⚠ Missing expected sentence types: {', '.join(missing_types)}")
        else:
            print("✓ All expected NMEA sentence types present")
        
        # Overall success criteria
        success = (
            analysis['success_rate'] >= 95 and  # At least 95% valid sentences
            len(analysis['sentence_types']) >= 4 and  # At least 4 different sentence types
            analysis['total_count'] >= capture_duration * 5  # At least 5 sentences per second
        )
        
        if success:
            print("✓ USB Serial output test PASSED")
        else:
            print("✗ USB Serial output test FAILED")
            
        return success
        
    except serial.SerialException as e:
        print(f"✗ Error opening USB serial port: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

def test_sentence_content(usb_port, test_duration=5):
    """Test specific NMEA sentence content"""
    print("Testing NMEA sentence content...")
    
    try:
        ser = serial.Serial(usb_port, 9600, timeout=1)
        
        gnrmc_sentences = []
        gngga_sentences = []
        start_time = time.time()
        
        while (time.time() - start_time) < test_duration:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            
            if line.startswith('$GNRMC'):
                gnrmc_sentences.append(line)
            elif line.startswith('$GNGGA'):
                gngga_sentences.append(line)
        
        ser.close()
        
        if not gnrmc_sentences and not gngga_sentences:
            print("✗ No GPS fix sentences found")
            return False
        
        print(f"✓ Found {len(gnrmc_sentences)} GNRMC and {len(gngga_sentences)} GNGGA sentences")
        
        # Test GNRMC sentence structure
        if gnrmc_sentences:
            sample_gnrmc = gnrmc_sentences[0]
            parts = sample_gnrmc.split(',')
            
            if len(parts) >= 12:
                print("✓ GNRMC sentence has correct field count")
                
                # Check for latitude/longitude
                if parts[3] and parts[4] and parts[5] and parts[6]:
                    print("✓ GNRMC contains position data")
                else:
                    print("⚠ GNRMC missing position data")
                
                # Check for time field
                if parts[1] and re.match(r'\d{6}\.\d{2}', parts[1]):
                    print("✓ GNRMC has valid time format")
                else:
                    print("⚠ GNRMC has invalid time format")
                    
            else:
                print("✗ GNRMC sentence has incorrect field count")
                return False
        
        # Test GNGGA sentence structure
        if gngga_sentences:
            sample_gngga = gngga_sentences[0]
            parts = sample_gngga.split(',')
            
            if len(parts) >= 15:
                print("✓ GNGGA sentence has correct field count")
                
                # Check for satellite count
                if parts[7] and parts[7].isdigit():
                    sat_count = int(parts[7])
                    print(f"✓ GNGGA reports {sat_count} satellites")
                else:
                    print("⚠ GNGGA missing satellite count")
                
                # Check for HDOP
                if parts[8]:
                    print(f"✓ GNGGA reports HDOP: {parts[8]}")
                else:
                    print("⚠ GNGGA missing HDOP")
                    
            else:
                print("✗ GNGGA sentence has incorrect field count")
                return False
        
        return True
        
    except serial.SerialException as e:
        print(f"✗ Error opening USB serial port: {e}")
        return False

def main():
    if len(sys.argv) < 3:
        print("Usage: python test_usb_output.py <device_ip> <usb_port>")
        print("Example: python test_usb_output.py 192.168.1.100 /dev/ttyUSB0")
        print("         python test_usb_output.py 192.168.4.1 COM3")
        sys.exit(1)
    
    device_ip = sys.argv[1]
    usb_port = sys.argv[2]
    base_url = f"http://{device_ip}"
    
    print("GPS Simulator USB Serial Output Test")
    print("=" * 50)
    print(f"Device: {base_url}")
    print(f"USB Port: {usb_port}")
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    tests_passed = 0
    total_tests = 6
    
    try:
        # Test 1: Configure USB-only output
        print("\n1. Configuring USB-only output")
        if configure_usb_only_output(base_url):
            tests_passed += 1
        
        # Test 2: Upload test CSV
        print("\n2. Uploading test CSV file")
        if upload_test_csv(base_url):
            tests_passed += 1
        
        # Test 3: Start simulation
        print("\n3. Starting GPS simulation")
        if start_gps_simulation(base_url):
            tests_passed += 1
            time.sleep(2)  # Allow simulation to start
        else:
            print("Cannot continue tests without simulation running")
            sys.exit(1)
        
        # Test 4: Test USB serial output
        print("\n4. Testing USB Serial output")
        if test_usb_serial_output(usb_port, capture_duration=15):
            tests_passed += 1
        
        # Test 5: Test sentence content
        print("\n5. Testing NMEA sentence content")
        if test_sentence_content(usb_port, test_duration=8):
            tests_passed += 1
        
        # Test 6: Test configuration persistence
        print("\n6. Testing configuration persistence")
        try:
            # Change to dual output
            data = {"gpio": "true", "usb": "true"}
            response = requests.post(f"{base_url}/output-config", data=data)
            
            if response.status_code == 200 and response.json().get("success"):
                # Verify status reflects change
                status_response = requests.get(f"{base_url}/status")
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    if status_data.get('gpio_output_enabled') and status_data.get('usb_output_enabled'):
                        print("✓ Configuration persistence test passed")
                        tests_passed += 1
                    else:
                        print("✗ Configuration not reflected in status")
                else:
                    print("✗ Status check failed")
            else:
                print("✗ Configuration change failed")
                
        except requests.RequestException as e:
            print(f"✗ Configuration persistence test failed: {e}")
    
    finally:
        # Clean up
        stop_gps_simulation(base_url)
    
    # Print summary
    print("\n" + "=" * 50)
    print("USB SERIAL OUTPUT TEST SUMMARY")
    print("=" * 50)
    print(f"Tests Passed: {tests_passed}/{total_tests}")
    print(f"Success Rate: {(tests_passed/total_tests)*100:.1f}%")
    
    if tests_passed == total_tests:
        print("\n🎉 ALL TESTS PASSED! USB Serial output is working correctly.")
        sys.exit(0)
    else:
        print("\n⚠️  SOME TESTS FAILED. Check the output above for details.")
        sys.exit(1)

if __name__ == "__main__":
    main()