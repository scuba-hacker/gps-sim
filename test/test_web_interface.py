#!/usr/bin/env python3
"""
GPS Simulator Web Interface Test Script

This script tests the web interface of the GPS simulator, including:
- Status checking
- Starting/stopping simulation
- CSV file upload

Requirements:
- Python 3.6+
- requests: pip install requests

Usage:
    python test_web_interface.py <device_ip>
    
Example:
    python test_web_interface.py 192.168.1.100
"""

import requests
import sys
import time
import os

def test_main_page(base_url):
    """Test the main web page"""
    print("Testing main page...")
    try:
        response = requests.get(f"{base_url}/")
        if response.status_code == 200:
            print("✓ Main page accessible")
            if "GPS Simulator Control" in response.text:
                print("✓ Main page content correct")
                return True
            else:
                print("✗ Main page content incorrect")
                return False
        else:
            print(f"✗ Main page returned status {response.status_code}")
            return False
    except requests.RequestException as e:
        print(f"✗ Error accessing main page: {e}")
        return False

def test_start_simulation(base_url):
    """Test starting GPS simulation"""
    print("Testing start simulation...")
    try:
        response = requests.get(f"{base_url}/start")
        if response.status_code == 200:
            print("✓ Start command accepted")
            print(f"  Response: {response.text}")
            return True
        elif response.status_code == 400:
            print("⚠ Start command returned 400 (no CSV loaded)")
            print(f"  Response: {response.text}")
            return False
        else:
            print(f"✗ Start command returned status {response.status_code}")
            return False
    except requests.RequestException as e:
        print(f"✗ Error starting simulation: {e}")
        return False

def test_stop_simulation(base_url):
    """Test stopping GPS simulation"""
    print("Testing stop simulation...")
    try:
        response = requests.get(f"{base_url}/stop")
        if response.status_code == 200:
            print("✓ Stop command accepted")
            print(f"  Response: {response.text}")
            return True
        else:
            print(f"✗ Stop command returned status {response.status_code}")
            return False
    except requests.RequestException as e:
        print(f"✗ Error stopping simulation: {e}")
        return False

def test_csv_upload(base_url, csv_file_path):
    """Test CSV file upload"""
    print(f"Testing CSV upload with file: {csv_file_path}")
    
    if not os.path.exists(csv_file_path):
        print(f"✗ CSV file not found: {csv_file_path}")
        return False
    
    try:
        with open(csv_file_path, 'rb') as f:
            files = {'csv': ('test_gps_track.csv', f, 'text/csv')}
            response = requests.post(f"{base_url}/upload", files=files)
            
        if response.status_code == 200:
            print("✓ CSV upload successful")
            print(f"  Response: {response.text}")
            return True
        else:
            print(f"✗ CSV upload failed with status {response.status_code}")
            print(f"  Response: {response.text}")
            return False
            
    except requests.RequestException as e:
        print(f"✗ Error uploading CSV: {e}")
        return False
    except IOError as e:
        print(f"✗ Error reading CSV file: {e}")
        return False

def create_sample_csv():
    """Create a sample CSV file for testing"""
    csv_content = """KB_to_qubitro,KB_uplinked_from_mako,UTC_date,UTC_time,act_sens_read,console_downlink_msg,coordinates,depth,distance_to_target,downlink_send_duration,enclosure_air_pressure,enclosure_humidity,enclosure_temperature,fix_count,geo_location,gps_course,gps_speed_knots,hdop,heading_to_target,journey_course,journey_distance,lemon_bat_voltage,lemon_imu_gyro_z,lemon_imu_lin_acc_x,lemon_imu_lin_acc_y,lemon_imu_lin_acc_z,lemon_imu_rot_acc_x,lemon_imu_rot_acc_y,lemon_imu_rot_acc_z,lemon_on_mins,lemon_usb_current,lemon_usb_voltage,live_metrics,magnetic_heading_compensated,mako_direction_metric,mako_imu_gyro_x,mako_imu_gyro_y,mako_imu_gyro_z,mako_imu_lin_acc_x,mako_imu_lin_acc_y,mako_imu_lin_acc_z,mako_imu_rot_acc_x,mako_imu_rot_acc_y,mako_imu_rot_acc_z,mako_lsm_acc_x,mako_lsm_acc_y,mako_lsm_acc_z,mako_on_mins,mako_rx_bad_checksum_msgs,mako_rx_good_checksum_msgs,mako_screen_display,mako_target_code,mako_usb_current,mako_usb_voltage,mako_user_action,mako_waymarker_e,mako_waymarker_label,max_act_sens_read,max_sens_read,min_sens_read,msgs_to_qubitro,qubitro_msg_length,qubitro_upload_duty_cycle,quiet_b4_uplink,sats,sens_read,uplink_bad_msgs_from_mako,uplink_bad_percentage,uplink_good_msgs_from_mako,uplink_latency,uplink_missing_msgs_from_mako,uplink_msg_length,water_pressure,water_temperature
0.0,0.0,06:08:2024,17:07:30,0,2,"[51.459595, -0.547948]",0.0,0.0,124749,0.0,0.0,0.0,2,"Test Location",0.0,0.1,2.3,0.0,0.0,0.0,4.139,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0,144.0,4.593,75,0.0,,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0,0,0,,,0.0,0.0,0,0,,0,0,0,0,0,49995,0,6,0,0,0.0,0,0,0,0,0.0,0.0
1.0,0.1,06:08:2024,17:07:31,5,8,"[51.459598, -0.547957]",0.0,52.7,87942,1011.9,34.9,24.1,8,"Test Location",45.0,0.5,2.2,331.8,0.0,0.0,4.139,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0,170.25,4.603,75,19.7,CH,-1.159668,0.976562,13.061523,-0.130615,-0.080322,1.029785,2.871585,-1.604443,-3.055346,0.114738,-1.453345,-10.020434,0,0,29,CM,Z01,189.0,5.46,0,2,AH,13,75,75,1,1932,2482,0,6,75,0,0.0,3,1748,0,0,0.99,22.7
2.0,0.2,06:08:2024,17:07:32,0,12,"[51.4596, -0.547957]",0.0,52.5,88526,1011.9,34.9,24.1,12,"Test Location",90.0,1.0,2.2,331.7,0.0,0.0,4.139,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0,154.5,4.608,75,21.0,CH,-0.488281,1.281738,12.207031,-0.125244,-0.074951,1.033936,3.34534,-1.834713,-2.070144,0.076492,-1.300362,-10.24991,0,0,33,CM,Z01,187.5,5.46,0,1,AC,13,75,75,2,1971,1999,0,6,75,0,0.0,5,1753,0,114,0.99,22.6
3.0,0.3,06:08:2024,17:07:33,0,18,"[51.459602, -0.547960]",0.0,52.6,87820,1012.1,34.9,24.2,18,"Test Location",135.0,1.5,2.2,331.6,0.0,0.0,4.139,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0,203.6,4.617,75,19.8,CH,-0.671387,1.098633,12.512207,-0.127686,-0.087891,1.034424,3.899549,-2.129262,-0.628557,0.038246,-1.453345,-9.982189,0,0,39,CM,Z01,206.6,5.487,0,1,AC,13,75,75,3,1975,2998,0,6,75,1,12.5,7,1746,0,114,0.99,22.7
4.0,0.4,06:08:2024,17:07:34,6,22,"[51.459605, -0.547965]",0.0,52.7,88277,1012.1,34.9,24.2,22,"Test Location",180.0,2.0,2.2,331.7,0.0,0.0,4.139,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0,173.25,4.595,75,19.9,CH,1.037598,0.854492,12.512207,-0.132812,-0.081055,1.042725,4.30015,-2.223362,0.329178,0.076492,-1.262116,-10.020434,0,0,43,CM,Z01,173.6,5.477,0,1,AC,13,75,75,4,1975,1999,0,8,75,1,10.0,9,1757,0,114,0.99,22.7"""
    
    with open('test_gps_track.csv', 'w') as f:
        f.write(csv_content)
    
    return 'test_gps_track.csv'

def main():
    if len(sys.argv) < 2:
        print("Usage: python test_web_interface.py <device_ip>")
        print("Example: python test_web_interface.py 192.168.1.100")
        sys.exit(1)
    
    device_ip = sys.argv[1]
    base_url = f"http://{device_ip}"
    
    print(f"GPS Simulator Web Interface Test")
    print(f"Testing device at: {base_url}")
    print("=" * 50)
    
    # Create sample CSV for testing
    csv_file = create_sample_csv()
    print(f"Created sample CSV file: {csv_file}")
    print()
    
    # Test sequence
    tests_passed = 0
    total_tests = 5
    
    # Test 1: Main page
    if test_main_page(base_url):
        tests_passed += 1
    print()
    
    # Test 2: Stop simulation (ensure clean state)
    if test_stop_simulation(base_url):
        tests_passed += 1
    print()
    
    # Test 3: Start simulation (should fail - no CSV)
    print("Expected to fail - no CSV loaded yet:")
    test_start_simulation(base_url)
    print()
    
    # Test 4: Upload CSV
    if test_csv_upload(base_url, csv_file):
        tests_passed += 1
        time.sleep(2)  # Give device time to process
    print()
    
    # Test 5: Start simulation (should succeed now)
    if test_start_simulation(base_url):
        tests_passed += 1
    print()
    
    # Test 6: Stop simulation
    if test_stop_simulation(base_url):
        tests_passed += 1
    print()
    
    # Clean up
    try:
        os.remove(csv_file)
        print(f"Cleaned up sample CSV file: {csv_file}")
    except OSError:
        pass
    
    print("=" * 50)
    print(f"Test Results: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("🎉 All tests passed! GPS Simulator web interface is working correctly.")
        sys.exit(0)
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        sys.exit(1)

if __name__ == "__main__":
    main()