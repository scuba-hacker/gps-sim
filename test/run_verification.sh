#!/bin/bash

# GPS Simulator Comprehensive Verification Script
# =============================================
# This script runs all available verification methods for the GPS simulator

set -e  # Exit on any error

# Configuration
DEFAULT_DURATION=10
DEFAULT_REFERENCE="../samples/sigrok-logic-output-neo6m.log"
DEVICE_IP=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}"
    echo "=========================================================="
    echo "           GPS Simulator Verification Suite"
    echo "=========================================================="
    echo -e "${NC}"
}

print_step() {
    echo -e "${YELLOW}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

check_requirements() {
    print_step "Checking requirements..."
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is required but not installed"
        exit 1
    fi
    print_success "Python 3 found"
    
    # Check if test scripts exist
    if [ ! -f "test_nmea.py" ] || [ ! -f "test_web_interface.py" ]; then
        print_error "Test scripts not found. Run from test/ directory"
        exit 1
    fi
    
    return 0
}

run_nmea_validation() {
    print_step "Running NMEA output validation..."
    
    echo "Available serial ports:"
    if command -v ls &> /dev/null; then
        ls /dev/tty* | grep -E "(USB|ACM)" | head -5 || echo "No obvious serial ports found"
    fi
    
    read -p "Enter serial port (e.g., /dev/ttyUSB0 or COM3): " SERIAL_PORT
    
    if [ -n "$SERIAL_PORT" ]; then
        print_step "Testing NMEA output on $SERIAL_PORT..."
        timeout 30 python3 test_nmea.py "$SERIAL_PORT" 9600 || true
        print_success "NMEA validation completed"
    else
        print_warning "Skipping NMEA validation - no serial port specified"
    fi
}

run_web_interface_test() {
    print_step "Running web interface test..."
    
    if [ -z "$DEVICE_IP" ]; then
        read -p "Enter GPS simulator IP address: " DEVICE_IP
    fi
    
    if [ -n "$DEVICE_IP" ]; then
        print_step "Testing web interface at $DEVICE_IP..."
        python3 test_web_interface.py "$DEVICE_IP"
        print_success "Web interface test completed"
    else
        print_warning "Skipping web interface test - no IP address specified"
    fi
}

run_sigrok_verification() {
    print_step "Running sigrok logic analyzer verification..."
    
    # Check if sigrok is available
    if ! command -v sigrok-cli &> /dev/null; then
        print_warning "sigrok-cli not found. Install sigrok for hardware verification"
        return 1
    fi
    
    # Check for logic analyzer
    if ! sigrok-cli --scan | grep -q "fx2lafw\|dreamsourcelab\|saleae"; then
        print_warning "No compatible logic analyzer found"
        print_step "Available for sigrok verification:"
        print_step "- Connect ESP32 GPIO 32 to logic analyzer channel D1"
        print_step "- Ensure common ground connection"
        print_step "- Run: python3 test_sigrok_verification.py $DEFAULT_DURATION $DEFAULT_REFERENCE"
        return 1
    fi
    
    print_success "Logic analyzer detected"
    
    read -p "Run hardware verification with logic analyzer? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_step "Starting sigrok capture (${DEFAULT_DURATION}s)..."
        python3 test_sigrok_verification.py "$DEFAULT_DURATION" "$DEFAULT_REFERENCE"
        print_success "Sigrok verification completed"
    else
        print_warning "Skipping sigrok verification"
    fi
}

generate_summary_report() {
    print_step "Generating verification summary..."
    
    REPORT_FILE="verification_summary_$(date +%Y%m%d_%H%M%S).md"
    
    cat > "$REPORT_FILE" << EOF
# GPS Simulator Verification Summary

**Generated:** $(date)
**Test Duration:** ${DEFAULT_DURATION}s
**Reference File:** $DEFAULT_REFERENCE

## Test Results

### NMEA Output Validation
$([ -f "nmea_test.log" ] && echo "✅ COMPLETED - Check nmea_test.log" || echo "⏭️ SKIPPED")

### Web Interface Test
$([ -f "web_test.log" ] && echo "✅ COMPLETED - Check web_test.log" || echo "⏭️ SKIPPED")

### Hardware Verification (Sigrok)
$([ -f "verification_report.txt" ] && echo "✅ COMPLETED - Check verification_report.txt" || echo "⏭️ SKIPPED")

## Files Generated
EOF
    
    for file in nmea_test.log web_test.log verification_report.txt gps_capture.log; do
        if [ -f "$file" ]; then
            echo "- $file" >> "$REPORT_FILE"
        fi
    done
    
    echo "" >> "$REPORT_FILE"
    echo "## Next Steps" >> "$REPORT_FILE"
    echo "1. Review individual test logs for detailed results" >> "$REPORT_FILE"
    echo "2. Address any issues found in verification" >> "$REPORT_FILE"
    echo "3. Re-run specific tests as needed" >> "$REPORT_FILE"
    
    print_success "Summary report generated: $REPORT_FILE"
}

show_help() {
    echo "GPS Simulator Verification Script"
    echo
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Options:"
    echo "  -d, --duration SECONDS    Capture duration for sigrok (default: $DEFAULT_DURATION)"
    echo "  -r, --reference FILE      Reference file for comparison (default: $DEFAULT_REFERENCE)"
    echo "  -i, --ip IP_ADDRESS       GPS simulator IP address"
    echo "  -s, --serial PORT         Serial port for NMEA testing"
    echo "  --nmea-only               Run only NMEA validation"
    echo "  --web-only                Run only web interface test"
    echo "  --sigrok-only             Run only sigrok verification"
    echo "  -h, --help                Show this help message"
    echo
    echo "Examples:"
    echo "  $0                                    # Run all tests interactively"
    echo "  $0 -d 30 -i 192.168.1.100          # 30s capture, specific IP"
    echo "  $0 --nmea-only -s /dev/ttyUSB0      # Only NMEA test on specific port"
    echo "  $0 --sigrok-only -d 60              # Only hardware verification, 60s"
}

# Parse command line arguments
DURATION=$DEFAULT_DURATION
REFERENCE=$DEFAULT_REFERENCE
TEST_MODE="all"
SERIAL_PORT=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--duration)
            DURATION="$2"
            shift 2
            ;;
        -r|--reference)
            REFERENCE="$2"
            shift 2
            ;;
        -i|--ip)
            DEVICE_IP="$2"
            shift 2
            ;;
        -s|--serial)
            SERIAL_PORT="$2"
            shift 2
            ;;
        --nmea-only)
            TEST_MODE="nmea"
            shift
            ;;
        --web-only)
            TEST_MODE="web"
            shift
            ;;
        --sigrok-only)
            TEST_MODE="sigrok"
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Main execution
main() {
    print_header
    
    check_requirements
    
    case $TEST_MODE in
        "nmea")
            run_nmea_validation
            ;;
        "web")
            run_web_interface_test
            ;;
        "sigrok")
            run_sigrok_verification
            ;;
        "all")
            echo "Running comprehensive verification suite..."
            echo
            run_nmea_validation
            echo
            run_web_interface_test
            echo
            run_sigrok_verification
            echo
            generate_summary_report
            ;;
    esac
    
    print_header
    print_success "Verification suite completed!"
    
    if [ -f "verification_summary_*.md" ]; then
        echo "📋 Check the summary report for detailed results"
    fi
}

# Run main function
main