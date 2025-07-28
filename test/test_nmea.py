#!/usr/bin/env python3
"""
GPS Simulator NMEA Test Harness

This script can be used to test the NMEA output from the GPS simulator.
It connects to a serial port and validates the incoming NMEA sentences.

Requirements:
- Python 3.6+
- pyserial: pip install pyserial

Usage:
    python test_nmea.py [serial_port] [baud_rate]
    
Examples:
    python test_nmea.py /dev/ttyUSB0 9600
    python test_nmea.py COM3 9600
"""

import serial
import sys
import time
import re

def calculate_checksum(sentence):
    """Calculate NMEA checksum (XOR of all characters between $ and *)"""
    checksum = 0
    for char in sentence[1:sentence.find('*')]:
        checksum ^= ord(char)
    return checksum

def validate_nmea_sentence(sentence):
    """Validate an NMEA sentence format and checksum"""
    sentence = sentence.strip()
    
    if not sentence.startswith('$'):
        return False, "Sentence doesn't start with $"
    
    if '*' not in sentence:
        return False, "No checksum delimiter (*) found"
    
    # Extract checksum
    try:
        checksum_str = sentence[sentence.find('*')+1:]
        expected_checksum = int(checksum_str, 16)
    except ValueError:
        return False, "Invalid checksum format"
    
    # Calculate checksum
    calculated_checksum = calculate_checksum(sentence)
    
    if calculated_checksum != expected_checksum:
        return False, f"Checksum mismatch: expected {expected_checksum:02X}, got {calculated_checksum:02X}"
    
    return True, "Valid"

def parse_gnrmc(sentence):
    """Parse GNRMC sentence and extract key information"""
    parts = sentence.split(',')
    if len(parts) < 12:
        return None
    
    return {
        'type': 'GNRMC',
        'time': parts[1],
        'status': parts[2],
        'latitude': parts[3] + parts[4] if parts[3] and parts[4] else 'N/A',
        'longitude': parts[5] + parts[6] if parts[5] and parts[6] else 'N/A',
        'speed': parts[7] if parts[7] else '0',
        'course': parts[8] if parts[8] else '0'
    }

def parse_gngga(sentence):
    """Parse GNGGA sentence and extract key information"""
    parts = sentence.split(',')
    if len(parts) < 15:
        return None
    
    return {
        'type': 'GNGGA',
        'time': parts[1],
        'latitude': parts[2] + parts[3] if parts[2] and parts[3] else 'N/A',
        'longitude': parts[4] + parts[5] if parts[4] and parts[5] else 'N/A',
        'quality': parts[6],
        'satellites': parts[7],
        'hdop': parts[8],
        'altitude': parts[9] + 'M' if parts[9] else 'N/A'
    }

def main():
    # Parse command line arguments
    if len(sys.argv) < 2:
        print("Usage: python test_nmea.py <serial_port> [baud_rate] [--dual-test <second_port>]")
        print("Example: python test_nmea.py /dev/ttyUSB0 9600")
        print("         python test_nmea.py /dev/ttyUSB0 9600 --dual-test /dev/ttyUSB1")
        sys.exit(1)
    
    serial_port = sys.argv[1]
    baud_rate = int(sys.argv[2]) if len(sys.argv) > 2 else 9600
    
    # Check for dual-test mode
    dual_test = False
    second_port = None
    if len(sys.argv) > 3 and sys.argv[3] == '--dual-test' and len(sys.argv) > 4:
        dual_test = True
        second_port = sys.argv[4]
    
    print(f"GPS Simulator NMEA Test Harness")
    
    if dual_test:
        print(f"DUAL OUTPUT MODE")
        print(f"Primary port: {serial_port} at {baud_rate} baud")
        print(f"Secondary port: {second_port} at {baud_rate} baud")
        return test_dual_output(serial_port, second_port, baud_rate)
    else:
        print(f"SINGLE OUTPUT MODE")
        print(f"Connecting to {serial_port} at {baud_rate} baud...")
        return test_single_output(serial_port, baud_rate)

def test_single_output(serial_port, baud_rate):
    """Test single serial output"""
    try:
        # Open serial connection
        ser = serial.Serial(serial_port, baud_rate, timeout=1)
        print(f"Connected successfully!")
        print("=" * 60)
        
        sentence_count = 0
        valid_count = 0
        error_count = 0
        last_time = time.time()
        
        print("Listening for NMEA sentences... (Press Ctrl+C to stop)")
        print()
        
        while True:
            try:
                # Read line from serial
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                
                if not line:
                    continue
                
                sentence_count += 1
                current_time = time.time()
                
                # Validate sentence
                is_valid, validation_msg = validate_nmea_sentence(line)
                
                if is_valid:
                    valid_count += 1
                    status = "✓ VALID"
                    
                    # Parse specific sentence types
                    if line.startswith('$GNRMC'):
                        data = parse_gnrmc(line)
                        if data:
                            print(f"{status:8} GNRMC - Time:{data['time']} Lat:{data['latitude']} Lng:{data['longitude']} Speed:{data['speed']}kts")
                    
                    elif line.startswith('$GNGGA'):
                        data = parse_gngga(line)
                        if data:
                            print(f"{status:8} GNGGA - Time:{data['time']} Lat:{data['latitude']} Lng:{data['longitude']} Sats:{data['satellites']} HDOP:{data['hdop']}")
                    
                    elif line.startswith('$GNGSA'):
                        print(f"{status:8} GNGSA - DOP and active satellites")
                    
                    elif line.startswith('$GPGSV'):
                        print(f"{status:8} GPGSV - GPS satellites in view")
                    
                    elif line.startswith('$BDGSV'):
                        print(f"{status:8} BDGSV - BeiDou satellites in view")
                    
                    elif line.startswith('$GNTXT'):
                        print(f"{status:8} GNTXT - Text message")
                    
                    else:
                        print(f"{status:8} {line[:6]} - {line}")
                
                else:
                    error_count += 1
                    print(f"✗ ERROR  {line[:20]}... - {validation_msg}")
                
                # Show statistics every 30 sentences
                if sentence_count % 30 == 0:
                    elapsed = current_time - last_time if sentence_count > 30 else current_time - last_time
                    rate = 30 / elapsed if elapsed > 0 else 0
                    print(f"\n--- Statistics (last 30 sentences) ---")
                    print(f"Rate: {rate:.1f} sentences/sec")
                    print(f"Valid: {valid_count}/{sentence_count} ({100*valid_count/sentence_count:.1f}%)")
                    print(f"Errors: {error_count}")
                    print()
                    last_time = current_time
                
            except KeyboardInterrupt:
                break
            
            except Exception as e:
                print(f"Error reading from serial: {e}")
                break
    
    except serial.SerialException as e:
        print(f"Error opening serial port: {e}")
        return False
    
    except KeyboardInterrupt:
        pass
    
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
        
        print(f"\n\nTest Summary:")
        print(f"Total sentences received: {sentence_count}")
        print(f"Valid sentences: {valid_count}")
        print(f"Invalid sentences: {error_count}")
        if sentence_count > 0:
            print(f"Success rate: {100*valid_count/sentence_count:.1f}%")
        print("Test completed.")
        return True

def test_dual_output(port1, port2, baud_rate):
    """Test dual serial output - compare sentences from both ports"""
    import threading
    import queue
    
    print("=" * 60)
    print("DUAL OUTPUT COMPARISON TEST")
    print("=" * 60)
    
    # Queues to store sentences from each port
    queue1 = queue.Queue()
    queue2 = queue.Queue()
    
    # Threading control
    stop_threads = threading.Event()
    
    def read_port(port, port_queue, port_name):
        """Thread function to read from a serial port"""
        try:
            ser = serial.Serial(port, baud_rate, timeout=1)
            print(f"✓ Connected to {port_name}: {port}")
            
            while not stop_threads.is_set():
                try:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    if line and line.startswith('$'):
                        port_queue.put((time.time(), line))
                except Exception as e:
                    if not stop_threads.is_set():
                        print(f"Error reading from {port_name}: {e}")
            
            ser.close()
            
        except serial.SerialException as e:
            print(f"✗ Error opening {port_name} ({port}): {e}")
    
    # Start reader threads
    thread1 = threading.Thread(target=read_port, args=(port1, queue1, "Port 1"))
    thread2 = threading.Thread(target=read_port, args=(port2, queue2, "Port 2"))
    
    thread1.daemon = True
    thread2.daemon = True
    
    thread1.start()
    thread2.start()
    
    time.sleep(2)  # Allow connections to establish
    
    print("Collecting data from both ports for 30 seconds...")
    print("Press Ctrl+C to stop early")
    
    try:
        time.sleep(30)
    except KeyboardInterrupt:
        print("\nStopping collection...")
    
    stop_threads.set()
    thread1.join(timeout=2)
    thread2.join(timeout=2)
    
    # Collect sentences from both queues
    sentences1 = []
    sentences2 = []
    
    while not queue1.empty():
        sentences1.append(queue1.get())
    
    while not queue2.empty():
        sentences2.append(queue2.get())
    
    print(f"\nCollection Results:")
    print(f"Port 1 ({port1}): {len(sentences1)} sentences")
    print(f"Port 2 ({port2}): {len(sentences2)} sentences")
    
    if not sentences1 or not sentences2:
        print("✗ No data received from one or both ports")
        return False
    
    # Validate sentences
    def validate_sentences(sentences, port_name):
        valid_count = 0
        sentence_types = set()
        
        for timestamp, sentence in sentences:
            is_valid, _ = validate_nmea_sentence(sentence)
            if is_valid:
                valid_count += 1
                if len(sentence) >= 6:
                    sentence_types.add(sentence[1:6])
        
        success_rate = (valid_count / len(sentences)) * 100
        print(f"{port_name} validation: {valid_count}/{len(sentences)} valid ({success_rate:.1f}%)")
        print(f"{port_name} sentence types: {', '.join(sorted(sentence_types))}")
        
        return success_rate >= 95, sentence_types
    
    port1_valid, types1 = validate_sentences(sentences1, "Port 1")
    port2_valid, types2 = validate_sentences(sentences2, "Port 2")
    
    # Compare sentence content
    content1 = {sentence for _, sentence in sentences1}
    content2 = {sentence for _, sentence in sentences2}
    common_sentences = content1 & content2
    
    overlap_ratio = len(common_sentences) / min(len(content1), len(content2))
    print(f"\nSentence overlap: {len(common_sentences)} common sentences")
    print(f"Overlap ratio: {overlap_ratio:.2f} (target: >0.8)")
    
    # Overall assessment
    success = (
        port1_valid and port2_valid and  # Both ports have valid sentences
        overlap_ratio > 0.8 and  # Good overlap between outputs
        len(types1 & types2) >= 4  # Common sentence types
    )
    
    if success:
        print("\n✓ DUAL OUTPUT TEST PASSED")
        print("Both outputs are producing consistent, valid NMEA data")
    else:
        print("\n✗ DUAL OUTPUT TEST FAILED")
        print("Issues detected with dual output consistency")
    
    return success

if __name__ == "__main__":
    main()