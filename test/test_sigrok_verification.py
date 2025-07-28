#!/usr/bin/env python3
"""
GPS Simulator Sigrok Verification System

This script uses sigrok-cli to capture and verify the NMEA output from our GPS simulator,
comparing it against reference GPS module behavior and NMEA protocol standards.

Hardware Setup Required:
- Logic analyzer compatible with sigrok (fx2lafw, etc.)
- Connection: ESP32 GPIO 32 → Logic Analyzer Channel D1
- Common ground between ESP32 and logic analyzer

Requirements:
- sigrok-cli installed and working
- Logic analyzer connected and detected
- Python 3.6+ with required packages

Usage:
    python test_sigrok_verification.py [capture_duration] [reference_file]
    
Example:
    python test_sigrok_verification.py 10 ../samples/sigrok-logic-output-neo6m.log
"""

import subprocess
import sys
import time
import re
import os
from datetime import datetime
import tempfile

class SigrokGPSVerifier:
    def __init__(self, capture_duration=10, driver="fx2lafw", channel="D1", samplerate="1MHz"):
        """
        Initialize the Sigrok GPS verification system
        
        Args:
            capture_duration: Duration in seconds to capture GPS data
            driver: Sigrok driver name (fx2lafw, etc.)
            channel: Logic analyzer channel to use
            samplerate: Sample rate for capture (1MHz recommended for 9600 baud)
        """
        self.capture_duration = capture_duration
        self.driver = driver
        self.channel = channel
        self.samplerate = samplerate
        self.samples = int(capture_duration * 1e6)  # 1MHz * duration
        
    def check_sigrok_available(self):
        """Verify that sigrok-cli is installed and logic analyzer is connected"""
        try:
            # Check if sigrok-cli is installed
            result = subprocess.run(['sigrok-cli', '--version'], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                print("❌ sigrok-cli not found. Please install sigrok-cli.")
                return False
                
            print(f"✓ sigrok-cli found: {result.stdout.split()[1]}")
            
            # List available devices
            result = subprocess.run(['sigrok-cli', '--scan'], 
                                  capture_output=True, text=True)
            if self.driver not in result.stdout:
                print(f"❌ Logic analyzer with driver '{self.driver}' not found.")
                print("Available devices:")
                print(result.stdout)
                return False
                
            print(f"✓ Logic analyzer found with driver: {self.driver}")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Error checking sigrok: {e}")
            return False
        except FileNotFoundError:
            print("❌ sigrok-cli not found. Please install sigrok and PulseView.")
            return False
    
    def capture_gps_output(self, output_file="gps_capture.log"):
        """
        Capture GPS NMEA output using sigrok logic analyzer
        
        Returns path to captured file or None if capture failed
        """
        print(f"🔍 Starting GPS capture for {self.capture_duration} seconds...")
        print(f"   Channel: {self.channel}")
        print(f"   Sample rate: {self.samplerate}")
        print(f"   Samples: {self.samples:,}")
        
        # Build sigrok command similar to the reference
        cmd = [
            'sigrok-cli',
            f'--driver={self.driver}',
            f'--channels={self.channel}',
            f'--config=samplerate={self.samplerate}',
            f'--samples={self.samples}',
            '-P', f'uart:rx={self.channel}:baudrate=9600:format=ascii_stream',
            '-A', 'uart',
            '--output-file', output_file
        ]
        
        print(f"Running: {' '.join(cmd)}")
        
        try:
            # Start capture
            start_time = time.time()
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=self.capture_duration + 10)
            end_time = time.time()
            
            if result.returncode == 0:
                print(f"✓ Capture completed in {end_time - start_time:.1f}s")
                return output_file
            else:
                print(f"❌ Capture failed: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            print("❌ Capture timeout - check connections and device settings")
            return None
        except Exception as e:
            print(f"❌ Capture error: {e}")
            return None
    
    def parse_nmea_sentences(self, filename):
        """
        Parse NMEA sentences from captured or reference file
        
        Returns list of parsed NMEA sentences with metadata
        """
        sentences = []
        
        if not os.path.exists(filename):
            print(f"❌ File not found: {filename}")
            return sentences
        
        try:
            with open(filename, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    
                    # Handle sigrok format (uart-1: prefix) or plain NMEA
                    if 'uart-1:' in line:
                        # Extract NMEA from sigrok output
                        nmea_part = line.split('uart-1:')[1].strip()
                        # Remove any unprintable characters (represented as ??)
                        nmea_part = re.sub(r'\?\?', '', nmea_part)
                        sentences.extend(self._extract_nmea_from_line(nmea_part, line_num))
                    elif line.startswith('$'):
                        # Plain NMEA sentence
                        sentences.append(self._parse_single_nmea(line, line_num))
                        
        except Exception as e:
            print(f"❌ Error parsing file {filename}: {e}")
            
        return sentences
    
    def _extract_nmea_from_line(self, line, line_num):
        """Extract multiple NMEA sentences from a single line"""
        sentences = []
        # Find all NMEA sentences starting with $
        nmea_matches = re.findall(r'\$[^$]*', line)
        
        for match in nmea_matches:
            sentences.append(self._parse_single_nmea(match, line_num))
            
        return sentences
    
    def _parse_single_nmea(self, sentence, line_num):
        """Parse a single NMEA sentence"""
        # Basic NMEA sentence structure
        parts = sentence.split(',')
        sentence_type = parts[0] if parts else "UNKNOWN"
        
        # Extract checksum if present
        checksum = None
        if '*' in sentence:
            try:
                checksum_part = sentence.split('*')[1][:2]
                checksum = int(checksum_part, 16)
            except (IndexError, ValueError):
                pass
        
        return {
            'raw': sentence,
            'type': sentence_type,
            'fields': parts,
            'checksum': checksum,
            'line': line_num,
            'valid': self._validate_nmea_checksum(sentence)
        }
    
    def _validate_nmea_checksum(self, sentence):
        """Validate NMEA sentence checksum"""
        if '*' not in sentence:
            return False
            
        try:
            content, checksum_str = sentence.split('*')
            expected_checksum = int(checksum_str[:2], 16)
            
            # Calculate checksum (XOR of all characters between $ and *)
            calculated_checksum = 0
            for char in content[1:]:  # Skip the $
                calculated_checksum ^= ord(char)
                
            return calculated_checksum == expected_checksum
            
        except (ValueError, IndexError):
            return False
    
    def compare_outputs(self, captured_file, reference_file):
        """
        Compare captured GPS output with reference file
        
        Returns detailed comparison report
        """
        print("\n📊 Analyzing captured GPS output...")
        
        captured_sentences = self.parse_nmea_sentences(captured_file)
        reference_sentences = self.parse_nmea_sentences(reference_file)
        
        print(f"   Captured sentences: {len(captured_sentences)}")
        print(f"   Reference sentences: {len(reference_sentences)}")
        
        # Analyze sentence types
        captured_types = {}
        reference_types = {}
        
        for sentence in captured_sentences:
            sentence_type = sentence['type']
            captured_types[sentence_type] = captured_types.get(sentence_type, 0) + 1
            
        for sentence in reference_sentences:
            sentence_type = sentence['type']
            reference_types[sentence_type] = reference_types.get(sentence_type, 0) + 1
        
        # Generate comparison report
        report = {
            'captured_count': len(captured_sentences),
            'reference_count': len(reference_sentences),
            'captured_types': captured_types,
            'reference_types': reference_types,
            'checksum_errors': 0,
            'timing_analysis': None,
            'sentence_structure_match': True
        }
        
        # Check checksum validity
        for sentence in captured_sentences:
            if not sentence['valid']:
                report['checksum_errors'] += 1
        
        # Analyze timing if we have timestamps
        report['timing_analysis'] = self._analyze_timing(captured_sentences)
        
        return report
    
    def _analyze_timing(self, sentences):
        """Analyze timing between GPS fixes"""
        # Look for GNRMC sentences (main fix sentences)
        gnrmc_sentences = [s for s in sentences if s['type'] == '$GNRMC']
        
        if len(gnrmc_sentences) < 2:
            return {"error": "Not enough GNRMC sentences for timing analysis"}
        
        # Extract timestamps from GNRMC sentences
        timestamps = []
        for sentence in gnrmc_sentences:
            if len(sentence['fields']) > 1:
                time_field = sentence['fields'][1]  # UTC time field
                timestamps.append(time_field)
        
        # Calculate intervals
        intervals = []
        for i in range(1, len(timestamps)):
            try:
                # Parse HHMMSS.SS format
                prev_time = self._parse_gps_time(timestamps[i-1])
                curr_time = self._parse_gps_time(timestamps[i])
                
                if prev_time and curr_time:
                    interval = curr_time - prev_time
                    if interval < 0:  # Handle day rollover
                        interval += 86400  # Add 24 hours
                    intervals.append(interval)
                    
            except Exception:
                continue
        
        if intervals:
            avg_interval = sum(intervals) / len(intervals)
            return {
                "average_interval": avg_interval,
                "intervals": intervals,
                "target_interval": 1.0,  # GPS fixes should be 1 second apart
                "timing_accuracy": abs(avg_interval - 1.0) < 0.1
            }
        
        return {"error": "Could not parse timing information"}
    
    def _parse_gps_time(self, time_str):
        """Parse GPS time in HHMMSS.SS format to seconds since midnight"""
        try:
            if not time_str or len(time_str) < 6:
                return None
                
            hours = int(time_str[:2])
            minutes = int(time_str[2:4])
            seconds = float(time_str[4:])
            
            return hours * 3600 + minutes * 60 + seconds
            
        except (ValueError, IndexError):
            return None
    
    def generate_report(self, report, output_file="verification_report.txt"):
        """Generate detailed verification report"""
        with open(output_file, 'w') as f:
            f.write("GPS Simulator Verification Report\n")
            f.write("=" * 50 + "\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("SENTENCE COUNT COMPARISON:\n")
            f.write(f"  Captured: {report['captured_count']} sentences\n")
            f.write(f"  Reference: {report['reference_count']} sentences\n\n")
            
            f.write("SENTENCE TYPE ANALYSIS:\n")
            f.write("  Captured sentence types:\n")
            for sentence_type, count in sorted(report['captured_types'].items()):
                f.write(f"    {sentence_type}: {count}\n")
            
            f.write("\n  Reference sentence types:\n")
            for sentence_type, count in sorted(report['reference_types'].items()):
                f.write(f"    {sentence_type}: {count}\n")
            
            f.write(f"\nCHECKSUM VALIDATION:\n")
            f.write(f"  Invalid checksums: {report['checksum_errors']}\n")
            
            if report['timing_analysis'] and 'average_interval' in report['timing_analysis']:
                timing = report['timing_analysis']
                f.write(f"\nTIMING ANALYSIS:\n")
                f.write(f"  Average interval: {timing['average_interval']:.3f}s\n")
                f.write(f"  Target interval: {timing['target_interval']}s\n")
                f.write(f"  Timing accurate: {timing['timing_accuracy']}\n")
            
            # Verdict
            f.write(f"\nVERIFICATION VERDICT:\n")
            if (report['checksum_errors'] == 0 and 
                report['timing_analysis'] and 
                report['timing_analysis'].get('timing_accuracy', False)):
                f.write("  ✅ GPS SIMULATOR OUTPUT VERIFIED - EXCELLENT\n")
            elif report['checksum_errors'] < 5:
                f.write("  ⚠️  GPS SIMULATOR OUTPUT MOSTLY VALID - MINOR ISSUES\n")
            else:
                f.write("  ❌ GPS SIMULATOR OUTPUT HAS SIGNIFICANT ISSUES\n")
        
        print(f"\n📋 Detailed report saved to: {output_file}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python test_sigrok_verification.py <capture_duration> [reference_file]")
        print("Example: python test_sigrok_verification.py 10 ../samples/sigrok-logic-output-neo6m.log")
        sys.exit(1)
    
    capture_duration = int(sys.argv[1])
    reference_file = sys.argv[2] if len(sys.argv) > 2 else "../samples/sigrok-logic-output-neo6m.log"
    
    print("🔬 GPS Simulator Sigrok Verification System")
    print("=" * 50)
    
    verifier = SigrokGPSVerifier(capture_duration=capture_duration)
    
    # Check if sigrok is available
    if not verifier.check_sigrok_available():
        sys.exit(1)
    
    print(f"\n📋 Test Configuration:")
    print(f"   Capture duration: {capture_duration}s")
    print(f"   Reference file: {reference_file}")
    print(f"   Expected samples: {verifier.samples:,}")
    
    input("\n🔌 Connect ESP32 GPIO 32 to logic analyzer channel D1, then press Enter...")
    
    # Capture GPS output
    captured_file = verifier.capture_gps_output()
    if not captured_file:
        print("❌ Capture failed. Check connections and try again.")
        sys.exit(1)
    
    # Compare with reference
    report = verifier.compare_outputs(captured_file, reference_file)
    
    # Generate detailed report
    verifier.generate_report(report)
    
    # Print summary
    print(f"\n🎯 VERIFICATION SUMMARY:")
    print(f"   Sentences captured: {report['captured_count']}")
    print(f"   Checksum errors: {report['checksum_errors']}")
    
    if report['timing_analysis'] and 'timing_accuracy' in report['timing_analysis']:
        accuracy = "✅ GOOD" if report['timing_analysis']['timing_accuracy'] else "⚠️  NEEDS IMPROVEMENT"
        print(f"   Timing accuracy: {accuracy}")
    
    print(f"\n📁 Files generated:")
    print(f"   - {captured_file} (raw capture)")
    print(f"   - verification_report.txt (analysis)")

if __name__ == "__main__":
    main()