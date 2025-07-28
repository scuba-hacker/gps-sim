#!/usr/bin/env python3
"""
GPS Simulator Dual Output Test Suite

This script tests the dual output functionality of the GPS simulator, including:
- USB Serial output validation
- GPIO UART output validation  
- Simultaneous dual output testing
- Output configuration switching
- NMEA sentence synchronization between outputs

Requirements:
- Python 3.6+
- pyserial: pip install pyserial
- requests: pip install requests

Usage:
    python test_dual_output.py <device_ip> <usb_port> <gpio_port>
    
Example:
    python test_dual_output.py 192.168.1.100 /dev/ttyUSB0 /dev/ttyUSB1
    python test_dual_output.py 192.168.4.1 COM3 COM4
"""

import requests
import serial
import sys
import time
import threading
import queue
from datetime import datetime

class NMEACapture:
    """Captures NMEA sentences from a serial port"""
    
    def __init__(self, port, name):
        self.port = port
        self.name = name
        self.sentences = queue.Queue()
        self.running = False
        self.thread = None
        self.error_count = 0
        self.total_count = 0
        
    def start(self):
        """Start capturing NMEA sentences"""
        try:
            self.serial = serial.Serial(self.port, 9600, timeout=1)
            self.running = True
            self.thread = threading.Thread(target=self._capture_loop)
            self.thread.daemon = True
            self.thread.start()
            return True
        except serial.SerialException as e:
            print(f"✗ Failed to open {self.name} port {self.port}: {e}")
            return False
    
    def stop(self):
        """Stop capturing NMEA sentences"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        if hasattr(self, 'serial') and self.serial.is_open:
            self.serial.close()
    
    def _capture_loop(self):
        """Main capture loop running in separate thread"""
        while self.running:
            try:
                line = self.serial.readline().decode('utf-8', errors='ignore').strip()
                if line and line.startswith('$'):
                    self.sentences.put((time.time(), line))
                    self.total_count += 1
            except Exception as e:
                if self.running:  # Only log errors if we're supposed to be running
                    self.error_count += 1
    
    def get_sentences(self, timeout=1):
        """Get captured sentences within timeout period"""
        sentences = []
        end_time = time.time() + timeout
        
        while time.time() < end_time:
            try:
                timestamp, sentence = self.sentences.get(timeout=0.1)
                sentences.append((timestamp, sentence))
            except queue.Empty:
                continue
        
        return sentences

def validate_nmea_checksum(sentence):
    """Validate NMEA sentence checksum"""
    if '*' not in sentence:
        return False, "No checksum delimiter found"
    
    try:
        content = sentence[1:sentence.find('*')]
        checksum_str = sentence[sentence.find('*')+1:]
        expected_checksum = int(checksum_str, 16)
        
        calculated_checksum = 0
        for char in content:
            calculated_checksum ^= ord(char)
        
        return calculated_checksum == expected_checksum, f"Checksum: expected {expected_checksum:02X}, got {calculated_checksum:02X}"
    except (ValueError, IndexError):
        return False, "Invalid checksum format"

def test_output_configuration(base_url):
    """Test the output configuration API"""
    print("Testing output configuration API...")
    
    # Test getting current status
    try:
        response = requests.get(f"{base_url}/status")
        if response.status_code != 200:
            print(f"✗ Status endpoint failed: {response.status_code}")
            return False
        
        status_data = response.json()
        if 'gpio_output_enabled' not in status_data or 'usb_output_enabled' not in status_data:
            print("✗ Status response missing output configuration fields")
            return False
        
        print(f"✓ Current configuration: GPIO={status_data['gpio_output_enabled']}, USB={status_data['usb_output_enabled']}")
        
    except requests.RequestException as e:
        print(f"✗ Error getting status: {e}")
        return False
    except ValueError as e:
        print(f"✗ Invalid JSON response: {e}")
        return False
    
    # Test configuration changes
    test_configs = [
        {"gpio": "true", "usb": "false", "expected": "GPIO only"},
        {"gpio": "false", "usb": "true", "expected": "USB only"},
        {"gpio": "true", "usb": "true", "expected": "Both active"}
    ]
    
    for config in test_configs:
        try:
            data = {"gpio": config["gpio"], "usb": config["usb"]}
            response = requests.post(f"{base_url}/output-config", data=data)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    print(f"✓ Configuration set to {config['expected']}")
                else:
                    print(f"✗ Configuration failed: {result.get('error', 'Unknown error')}")
                    return False
            else:
                print(f"✗ Configuration request failed: {response.status_code}")
                return False
                
        except requests.RequestException as e:
            print(f"✗ Error setting configuration: {e}")
            return False
        
        time.sleep(1)  # Allow configuration to settle
    
    # Test invalid configuration (both disabled)
    try:
        data = {"gpio": "false", "usb": "false"}
        response = requests.post(f"{base_url}/output-config", data=data)
        
        if response.status_code == 400:
            result = response.json()
            if not result.get("success") and "at least one output" in result.get("error", "").lower():
                print("✓ Correctly rejected invalid configuration (both outputs disabled)")
            else:
                print("✗ Invalid configuration response format")
                return False
        else:
            print(f"✗ Invalid configuration should return 400, got {response.status_code}")
            return False
            
    except requests.RequestException as e:
        print(f"✗ Error testing invalid configuration: {e}")
        return False
    
    return True

def test_single_output(base_url, capture, output_name, enable_gpio, enable_usb):
    """Test a single output configuration"""
    print(f"\nTesting {output_name} output...")
    
    # Configure output
    data = {"gpio": "true" if enable_gpio else "false", "usb": "true" if enable_usb else "false"}
    response = requests.post(f"{base_url}/output-config", data=data)
    
    if response.status_code != 200 or not response.json().get("success"):
        print(f"✗ Failed to configure {output_name} output")
        return False
    
    print(f"✓ Configured for {output_name} output")
    time.sleep(2)  # Allow configuration to settle
    
    # Start GPS simulation
    response = requests.get(f"{base_url}/start")
    if response.status_code != 200:
        print(f"✗ Failed to start GPS simulation: {response.status_code}")
        return False
    
    print("✓ GPS simulation started")
    time.sleep(3)  # Allow data to flow
    
    # Capture sentences
    sentences = capture.get_sentences(timeout=5)
    
    # Stop simulation
    requests.get(f"{base_url}/stop")
    
    if not sentences:
        print(f"✗ No NMEA sentences received on {output_name}")
        return False
    
    print(f"✓ Received {len(sentences)} NMEA sentences on {output_name}")
    
    # Validate sentences
    valid_count = 0
    sentence_types = set()
    
    for timestamp, sentence in sentences:
        is_valid, msg = validate_nmea_checksum(sentence)
        if is_valid:
            valid_count += 1
            # Extract sentence type (first 6 characters after $)
            if len(sentence) >= 6:
                sentence_types.add(sentence[1:6])
    
    success_rate = (valid_count / len(sentences)) * 100 if sentences else 0
    print(f"✓ Validation: {valid_count}/{len(sentences)} valid ({success_rate:.1f}%)")
    print(f"✓ Sentence types: {', '.join(sorted(sentence_types))}")
    
    return success_rate >= 95  # Require 95% success rate

def test_simultaneous_output(base_url, usb_capture, gpio_capture):
    """Test simultaneous output on both channels"""
    print("\nTesting simultaneous dual output...")
    
    # Configure both outputs
    data = {"gpio": "true", "usb": "true"}
    response = requests.post(f"{base_url}/output-config", data=data)
    
    if response.status_code != 200 or not response.json().get("success"):
        print("✗ Failed to configure dual output")
        return False
    
    print("✓ Configured for dual output (GPIO + USB)")
    time.sleep(2)
    
    # Start GPS simulation
    response = requests.get(f"{base_url}/start")
    if response.status_code != 200:
        print(f"✗ Failed to start GPS simulation: {response.status_code}")
        return False
    
    print("✓ GPS simulation started")
    time.sleep(5)  # Allow data to flow
    
    # Capture sentences from both outputs
    usb_sentences = usb_capture.get_sentences(timeout=3)
    gpio_sentences = gpio_capture.get_sentences(timeout=3)
    
    # Stop simulation
    requests.get(f"{base_url}/stop")
    
    if not usb_sentences:
        print("✗ No sentences received on USB output")
        return False
    
    if not gpio_sentences:
        print("✗ No sentences received on GPIO output")
        return False
    
    print(f"✓ USB: {len(usb_sentences)} sentences, GPIO: {len(gpio_sentences)} sentences")
    
    # Compare sentence counts (should be similar)
    count_ratio = min(len(usb_sentences), len(gpio_sentences)) / max(len(usb_sentences), len(gpio_sentences))
    if count_ratio < 0.8:  # Allow 20% variance
        print(f"✗ Sentence count mismatch: USB={len(usb_sentences)}, GPIO={len(gpio_sentences)}")
        return False
    
    print(f"✓ Sentence counts are similar (ratio: {count_ratio:.2f})")
    
    # Check for sentence content similarity (at least some matching sentences)
    usb_content = {sentence for _, sentence in usb_sentences}
    gpio_content = {sentence for _, sentence in gpio_sentences}
    common_sentences = usb_content & gpio_content
    
    if len(common_sentences) < min(len(usb_content), len(gpio_content)) * 0.5:
        print("✗ Insufficient matching sentences between outputs")
        return False
    
    print(f"✓ Found {len(common_sentences)} matching sentences between outputs")
    
    # Validate sentences on both outputs
    for name, sentences in [("USB", usb_sentences), ("GPIO", gpio_sentences)]:
        valid_count = 0
        for timestamp, sentence in sentences:
            is_valid, _ = validate_nmea_checksum(sentence)
            if is_valid:
                valid_count += 1
        
        success_rate = (valid_count / len(sentences)) * 100 if sentences else 0
        print(f"✓ {name} validation: {valid_count}/{len(sentences)} valid ({success_rate:.1f}%)")
        
        if success_rate < 95:
            print(f"✗ {name} output has too many invalid sentences")
            return False
    
    return True

def test_timing_analysis(base_url, usb_capture, gpio_capture):
    """Test timing synchronization between outputs"""
    print("\nTesting output timing synchronization...")
    
    # Configure both outputs  
    data = {"gpio": "true", "usb": "true"}
    response = requests.post(f"{base_url}/output-config", data=data)
    
    if response.status_code != 200:
        print("✗ Failed to configure dual output")
        return False
    
    # Start simulation
    response = requests.get(f"{base_url}/start")
    if response.status_code != 200:
        print("✗ Failed to start GPS simulation")
        return False
    
    print("✓ Analyzing output timing for 10 seconds...")
    time.sleep(10)
    
    # Capture sentences with timestamps
    usb_sentences = usb_capture.get_sentences(timeout=2)
    gpio_sentences = gpio_capture.get_sentences(timeout=2)
    
    requests.get(f"{base_url}/stop")
    
    if len(usb_sentences) < 5 or len(gpio_sentences) < 5:
        print("✗ Insufficient data for timing analysis")
        return False
    
    # Calculate timing intervals for GPS fixes (should be ~1 second)
    def calculate_intervals(sentences):
        intervals = []
        last_timestamp = None
        
        for timestamp, sentence in sentences:
            if sentence.startswith('$GNRMC'):  # GPS fix sentences
                if last_timestamp is not None:
                    intervals.append(timestamp - last_timestamp)
                last_timestamp = timestamp
        
        return intervals
    
    usb_intervals = calculate_intervals(usb_sentences)
    gpio_intervals = calculate_intervals(gpio_sentences)
    
    if not usb_intervals or not gpio_intervals:
        print("✗ No GPS fix intervals found")
        return False
    
    # Check that intervals are close to 1 second (GPS standard)
    for name, intervals in [("USB", usb_intervals), ("GPIO", gpio_intervals)]:
        avg_interval = sum(intervals) / len(intervals)
        print(f"✓ {name} average interval: {avg_interval:.3f}s (target: 1.000s)")
        
        if abs(avg_interval - 1.0) > 0.1:  # Allow 100ms variance
            print(f"✗ {name} timing deviation too large")
            return False
    
    print("✓ Both outputs maintain proper 1-second GPS timing")
    return True

def main():
    if len(sys.argv) < 4:
        print("Usage: python test_dual_output.py <device_ip> <usb_port> <gpio_port>")
        print("Example: python test_dual_output.py 192.168.1.100 /dev/ttyUSB0 /dev/ttyUSB1")
        print("         python test_dual_output.py 192.168.4.1 COM3 COM4")
        sys.exit(1)
    
    device_ip = sys.argv[1]
    usb_port = sys.argv[2]
    gpio_port = sys.argv[3]
    base_url = f"http://{device_ip}"
    
    print("GPS Simulator Dual Output Test Suite")
    print("=" * 50)
    print(f"Device: {base_url}")
    print(f"USB Serial Port: {usb_port}")
    print(f"GPIO UART Port: {gpio_port}")
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # Initialize capture instances
    usb_capture = NMEACapture(usb_port, "USB")
    gpio_capture = NMEACapture(gpio_port, "GPIO")
    
    tests_passed = 0
    total_tests = 6
    
    try:
        # Test 1: Output configuration API
        print("\n1. Testing Output Configuration API")
        if test_output_configuration(base_url):
            tests_passed += 1
            print("✓ Output configuration API tests passed")
        else:
            print("✗ Output configuration API tests failed")
        
        # Start capture threads
        if not usb_capture.start():
            print("✗ Failed to start USB capture")
            sys.exit(1)
        
        if not gpio_capture.start():
            print("✗ Failed to start GPIO capture")
            sys.exit(1)
        
        print("✓ Serial capture threads started")
        
        # Test 2: USB output only
        print("\n2. Testing USB Serial Output Only")
        if test_single_output(base_url, usb_capture, "USB", False, True):
            tests_passed += 1
            print("✓ USB output test passed")
        else:
            print("✗ USB output test failed")
        
        # Test 3: GPIO output only
        print("\n3. Testing GPIO UART Output Only")
        if test_single_output(base_url, gpio_capture, "GPIO", True, False):
            tests_passed += 1
            print("✓ GPIO output test passed")
        else:
            print("✗ GPIO output test failed")
        
        # Test 4: Simultaneous output
        print("\n4. Testing Simultaneous Dual Output")
        if test_simultaneous_output(base_url, usb_capture, gpio_capture):
            tests_passed += 1
            print("✓ Simultaneous output test passed")
        else:
            print("✗ Simultaneous output test failed")
        
        # Test 5: Timing analysis
        print("\n5. Testing Output Timing Synchronization")
        if test_timing_analysis(base_url, usb_capture, gpio_capture):
            tests_passed += 1
            print("✓ Timing synchronization test passed")
        else:
            print("✗ Timing synchronization test failed")
        
        # Test 6: Error handling
        print("\n6. Testing Error Handling")
        try:
            # Test network error handling
            test_url = f"http://255.255.255.255/status"  # Invalid IP
            try:
                requests.get(test_url, timeout=2)
                print("✗ Should have failed with network error")
            except requests.RequestException:
                print("✓ Network error handling works")
                tests_passed += 1
        except Exception as e:
            print(f"✗ Error handling test failed: {e}")
    
    finally:
        # Clean up
        usb_capture.stop()
        gpio_capture.stop()
    
    # Print summary
    print("\n" + "=" * 50)
    print("DUAL OUTPUT TEST SUMMARY")
    print("=" * 50)
    print(f"Tests Passed: {tests_passed}/{total_tests}")
    print(f"Success Rate: {(tests_passed/total_tests)*100:.1f}%")
    
    if usb_capture.total_count > 0:
        print(f"USB Sentences: {usb_capture.total_count} (errors: {usb_capture.error_count})")
    if gpio_capture.total_count > 0:
        print(f"GPIO Sentences: {gpio_capture.total_count} (errors: {gpio_capture.error_count})")
    
    if tests_passed == total_tests:
        print("\n🎉 ALL TESTS PASSED! Dual output functionality is working correctly.")
        sys.exit(0)
    else:
        print("\n⚠️  SOME TESTS FAILED. Check the output above for details.")
        sys.exit(1)

if __name__ == "__main__":
    main()