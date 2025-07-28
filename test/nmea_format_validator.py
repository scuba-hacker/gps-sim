#!/usr/bin/env python3
"""
NMEA Format Validator

This script validates NMEA sentences for correct formatting, checksums, and protocol compliance
without requiring hardware. It can be used to verify NMEA output files or live serial streams.

Usage:
    python nmea_format_validator.py <input_file_or_port> [--live]
    
Examples:
    python nmea_format_validator.py ../samples/sigrok-logic-output-neo6m.log
    python nmea_format_validator.py /dev/ttyUSB0 --live
    python nmea_format_validator.py capture.txt
"""

import sys
import re
import serial
import time
from datetime import datetime

class NMEAValidator:
    def __init__(self):
        self.sentence_patterns = {
            '$GNRMC': r'^\$GNRMC,(\d{6}\.\d{2}),([AV]),(\d{4}\.\d{5}),([NS]),(\d{5}\.\d{5}),([EW]),(\d+\.\d*),(\d*\.\d*|\d*),(\d{6}),([^,]*),([^,]*),([AV]),([^*]*)\*([0-9A-F]{2})$',
            '$GNGGA': r'^\$GNGGA,(\d{6}\.\d{2}),(\d{4}\.\d{5}),([NS]),(\d{5}\.\d{5}),([EW]),([012]),(\d{2}),(\d+\.\d*),(\d+\.\d*),M,(\d+\.\d*),M,([^,]*),([^*]*)\*([0-9A-F]{2})$',
            '$GNGSA': r'^\$GNGSA,([AM]),([123]),([^,]*),([^,]*),([^,]*),([^,]*),([^,]*),([^,]*),([^,]*),([^,]*),([^,]*),([^,]*),([^,]*),([^,]*),(\d+\.\d*),(\d+\.\d*),(\d+\.\d*),([1-4])\*([0-9A-F]{2})$',
            '$GPGSV': r'^\$GPGSV,([1-4]),([1-4]),(\d{2}),([^*]*)\*([0-9A-F]{2})$',
            '$BDGSV': r'^\$BDGSV,([1-4]),([1-4]),(\d{2}),([^*]*)\*([0-9A-F]{2})$',
            '$GNTXT': r'^\$GNTXT,(\d{2}),(\d{2}),(\d{2}),([^*]*)\*([0-9A-F]{2})$'
        }
        
        self.validation_stats = {
            'total_sentences': 0,
            'valid_sentences': 0,
            'checksum_errors': 0,
            'format_errors': 0,
            'sentence_counts': {},
            'timing_intervals': [],
            'coordinate_ranges': {'lat': [], 'lon': []}
        }
        
        self.last_timestamp = None
        
    def calculate_checksum(self, sentence):
        """Calculate NMEA checksum (XOR between $ and *)"""
        if '*' not in sentence:
            return None
            
        content = sentence[sentence.find('$')+1:sentence.find('*')]
        checksum = 0
        for char in content:
            checksum ^= ord(char)
        return checksum
    
    def validate_checksum(self, sentence):
        """Validate NMEA sentence checksum"""
        if '*' not in sentence:
            return False, "No checksum delimiter found"
            
        try:
            content, checksum_str = sentence.split('*')
            expected_checksum = int(checksum_str.strip(), 16)
            calculated_checksum = self.calculate_checksum(sentence)
            
            if calculated_checksum == expected_checksum:
                return True, "Checksum valid"
            else:
                return False, f"Checksum mismatch: expected {expected_checksum:02X}, got {calculated_checksum:02X}"
                
        except (ValueError, IndexError) as e:
            return False, f"Checksum parsing error: {e}"
    
    def validate_format(self, sentence):
        """Validate NMEA sentence format using regex patterns"""
        sentence = sentence.strip()
        
        # Find matching sentence type
        sentence_type = None
        for stype in self.sentence_patterns:
            if sentence.startswith(stype):
                sentence_type = stype
                break
        
        if not sentence_type:
            return False, "Unknown sentence type", None
        
        # Check format with regex
        pattern = self.sentence_patterns[sentence_type]
        match = re.match(pattern, sentence)
        
        if match:
            return True, "Format valid", sentence_type
        else:
            return False, f"Format invalid for {sentence_type}", sentence_type
    
    def extract_timing(self, sentence):
        """Extract timing information from GNRMC sentences"""
        if not sentence.startswith('$GNRMC'):
            return None
            
        parts = sentence.split(',')
        if len(parts) < 2:
            return None
            
        time_str = parts[1]  # HHMMSS.SS format
        if not time_str:
            return None
            
        try:
            hours = int(time_str[:2])
            minutes = int(time_str[2:4])
            seconds = float(time_str[4:])
            
            # Convert to seconds since midnight
            total_seconds = hours * 3600 + minutes * 60 + seconds
            
            if self.last_timestamp is not None:
                interval = total_seconds - self.last_timestamp
                if interval < 0:  # Day rollover
                    interval += 86400
                if 0.5 < interval < 2.0:  # Reasonable interval
                    self.validation_stats['timing_intervals'].append(interval)
            
            self.last_timestamp = total_seconds
            return total_seconds
            
        except (ValueError, IndexError):
            return None
    
    def extract_coordinates(self, sentence):
        """Extract and validate coordinates from GNRMC or GNGGA sentences"""
        if not (sentence.startswith('$GNRMC') or sentence.startswith('$GNGGA')):
            return None, None
            
        parts = sentence.split(',')
        
        try:
            if sentence.startswith('$GNRMC'):
                lat_str, lat_ns, lon_str, lon_ew = parts[3], parts[4], parts[5], parts[6]
            else:  # GNGGA
                lat_str, lat_ns, lon_str, lon_ew = parts[2], parts[3], parts[4], parts[5]
            
            if not all([lat_str, lat_ns, lon_str, lon_ew]):
                return None, None
            
            # Convert DDMM.MMMMM to decimal degrees
            lat_deg = int(lat_str[:2])
            lat_min = float(lat_str[2:])
            latitude = lat_deg + lat_min / 60.0
            if lat_ns == 'S':
                latitude = -latitude
            
            lon_deg = int(lon_str[:3])
            lon_min = float(lon_str[3:])
            longitude = lon_deg + lon_min / 60.0
            if lon_ew == 'W':
                longitude = -longitude
            
            # Validate reasonable ranges
            if -90 <= latitude <= 90 and -180 <= longitude <= 180:
                self.validation_stats['coordinate_ranges']['lat'].append(latitude)
                self.validation_stats['coordinate_ranges']['lon'].append(longitude)
                return latitude, longitude
            else:
                return None, None
                
        except (ValueError, IndexError):
            return None, None
    
    def validate_sentence(self, sentence):
        """Comprehensive validation of a single NMEA sentence"""
        sentence = sentence.strip()
        if not sentence or not sentence.startswith('$'):
            return {
                'valid': False,
                'error': 'Not a valid NMEA sentence',
                'sentence': sentence
            }
        
        self.validation_stats['total_sentences'] += 1
        
        # Validate checksum
        checksum_valid, checksum_msg = self.validate_checksum(sentence)
        if not checksum_valid:
            self.validation_stats['checksum_errors'] += 1
        
        # Validate format
        format_valid, format_msg, sentence_type = self.validate_format(sentence)
        if not format_valid:
            self.validation_stats['format_errors'] += 1
        
        # Count sentence types
        if sentence_type:
            self.validation_stats['sentence_counts'][sentence_type] = \
                self.validation_stats['sentence_counts'].get(sentence_type, 0) + 1
        
        # Extract timing and coordinates
        timing = self.extract_timing(sentence)
        lat, lon = self.extract_coordinates(sentence)
        
        # Overall validity
        valid = checksum_valid and format_valid
        if valid:
            self.validation_stats['valid_sentences'] += 1
        
        return {
            'valid': valid,
            'sentence_type': sentence_type,
            'checksum_valid': checksum_valid,
            'checksum_msg': checksum_msg,
            'format_valid': format_valid,
            'format_msg': format_msg,
            'timing': timing,
            'latitude': lat,
            'longitude': lon,
            'sentence': sentence
        }
    
    def validate_file(self, filename):
        """Validate NMEA sentences from a file"""
        print(f"📁 Validating NMEA file: {filename}")
        print("=" * 60)
        
        try:
            with open(filename, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    
                    # Handle sigrok format
                    if 'uart-1:' in line:
                        # Extract NMEA from sigrok output
                        nmea_part = line.split('uart-1:')[1].strip()
                        # Remove unprintable characters
                        nmea_part = re.sub(r'\?\?', '', nmea_part)
                        
                        # Extract individual NMEA sentences
                        sentences = re.findall(r'\$[^$]*', nmea_part)
                        for sentence in sentences:
                            if sentence.strip():
                                result = self.validate_sentence(sentence)
                                self.print_validation_result(result, line_num)
                    
                    elif line.startswith('$'):
                        # Plain NMEA sentence
                        result = self.validate_sentence(line)
                        self.print_validation_result(result, line_num)
                        
        except FileNotFoundError:
            print(f"❌ File not found: {filename}")
            return False
        except Exception as e:
            print(f"❌ Error reading file: {e}")
            return False
        
        return True
    
    def validate_live_serial(self, port, baudrate=9600, timeout=30):
        """Validate live NMEA stream from serial port"""
        print(f"📡 Validating live NMEA stream: {port} @ {baudrate} baud")
        print(f"🕐 Timeout: {timeout} seconds")
        print("=" * 60)
        
        try:
            ser = serial.Serial(port, baudrate, timeout=1)
            start_time = time.time()
            line_num = 0
            
            print("Listening for NMEA sentences... (Ctrl+C to stop)")
            
            while time.time() - start_time < timeout:
                try:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    if line and line.startswith('$'):
                        line_num += 1
                        result = self.validate_sentence(line)
                        self.print_validation_result(result, line_num)
                        
                except KeyboardInterrupt:
                    print("\n⏹️  Stopped by user")
                    break
                    
            ser.close()
            return True
            
        except serial.SerialException as e:
            print(f"❌ Serial port error: {e}")
            return False
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def print_validation_result(self, result, line_num):
        """Print validation result for a single sentence"""
        if result['valid']:
            status = "✅"
            msg = f"VALID {result['sentence_type']}"
        else:
            status = "❌"
            errors = []
            if not result['checksum_valid']:
                errors.append(f"CHECKSUM({result['checksum_msg']})")
            if not result['format_valid']:
                errors.append(f"FORMAT({result['format_msg']})")
            msg = f"INVALID - {' + '.join(errors)}"
        
        # Show coordinates if available
        coord_info = ""
        if result['latitude'] is not None and result['longitude'] is not None:
            coord_info = f" [{result['latitude']:.6f}, {result['longitude']:.6f}]"
        
        print(f"{status} Line {line_num:3d}: {msg}{coord_info}")
        
        if not result['valid']:
            print(f"     Raw: {result['sentence']'][:80]}...")
    
    def print_summary(self):
        """Print comprehensive validation summary"""
        stats = self.validation_stats
        
        print("\n" + "=" * 60)
        print("📊 VALIDATION SUMMARY")
        print("=" * 60)
        
        # Basic stats
        print(f"Total sentences processed: {stats['total_sentences']}")
        print(f"Valid sentences: {stats['valid_sentences']}")
        print(f"Invalid sentences: {stats['total_sentences'] - stats['valid_sentences']}")
        
        if stats['total_sentences'] > 0:
            success_rate = (stats['valid_sentences'] / stats['total_sentences']) * 100
            print(f"Success rate: {success_rate:.1f}%")
        
        # Error breakdown
        print(f"\nError breakdown:")
        print(f"  Checksum errors: {stats['checksum_errors']}")
        print(f"  Format errors: {stats['format_errors']}")
        
        # Sentence type distribution
        print(f"\nSentence type distribution:")
        for sentence_type, count in sorted(stats['sentence_counts'].items()):
            print(f"  {sentence_type}: {count}")
        
        # Timing analysis
        if stats['timing_intervals']:
            intervals = stats['timing_intervals']
            avg_interval = sum(intervals) / len(intervals)
            min_interval = min(intervals)
            max_interval = max(intervals)
            
            print(f"\nTiming analysis (GPS fix intervals):")
            print(f"  Average interval: {avg_interval:.3f}s")
            print(f"  Min interval: {min_interval:.3f}s")
            print(f"  Max interval: {max_interval:.3f}s")
            print(f"  Target interval: 1.000s")
            
            timing_ok = 0.95 <= avg_interval <= 1.05
            print(f"  Timing accuracy: {'✅ GOOD' if timing_ok else '⚠️ NEEDS IMPROVEMENT'}")
        
        # Coordinate analysis
        if stats['coordinate_ranges']['lat'] and stats['coordinate_ranges']['lon']:
            lats = stats['coordinate_ranges']['lat']
            lons = stats['coordinate_ranges']['lon']
            
            print(f"\nCoordinate analysis:")
            print(f"  Latitude range: {min(lats):.6f}° to {max(lats):.6f}°")
            print(f"  Longitude range: {min(lons):.6f}° to {max(lons):.6f}°")
            print(f"  Coordinate samples: {len(lats)}")
        
        # Final verdict
        print(f"\n🎯 FINAL VERDICT:")
        if stats['checksum_errors'] == 0 and stats['format_errors'] == 0:
            print("  ✅ ALL NMEA SENTENCES VALID - EXCELLENT!")
        elif stats['checksum_errors'] + stats['format_errors'] < 5:
            print("  ⚠️ MOSTLY VALID - MINOR ISSUES DETECTED")
        else:
            print("  ❌ SIGNIFICANT ISSUES - NEEDS ATTENTION")

def main():
    if len(sys.argv) < 2:
        print("Usage: python nmea_format_validator.py <input_file_or_port> [--live]")
        print("\nExamples:")
        print("  python nmea_format_validator.py ../samples/sigrok-logic-output-neo6m.log")
        print("  python nmea_format_validator.py /dev/ttyUSB0 --live")
        print("  python nmea_format_validator.py COM3 --live")
        sys.exit(1)
    
    input_source = sys.argv[1]
    is_live = len(sys.argv) > 2 and sys.argv[2] == '--live'
    
    validator = NMEAValidator()
    
    print(f"🔍 NMEA Format Validator")
    print(f"📅 Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    if is_live:
        success = validator.validate_live_serial(input_source)
    else:
        success = validator.validate_file(input_source)
    
    if success:
        validator.print_summary()
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())