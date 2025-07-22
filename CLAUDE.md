Hello Claude.

Today we are building a GPS Simulator which will simulate NEMA output of a u-blox neo-6m GPS module, transmitting on a UART GPIO.

The platform we are developing for is ESP32 M5 Stick C Plus (with 4MB flash memory) with VS Code and Platform.IO. The language is C++, using the Arduino Framework and the espressif-edf libraries.

I have already built the skeleton of the project.

You can bring in any extra libraries or open source projects from github that you require.

The simulator will:

1. Have WiFi connectivity - assume a DHCP server will provide IP, Gateway, DNS etc and a good internet connection.
    - the SSID and password will be in a secrets file not uploaded to github.
    - I will populate these fields afterwards

2. allow OTA update of code using ElegantOTA frontend.

3. Allow reference csv file containing gps track info uploaded through the File upload feature of ElegantOTA.
    This file is to be stored in flash and can be up to 1MB in size. 
    Only one file will be present in flash at once.
    You will need to modify the Spiffs partitioning to allow this.
    Only the UTC_time, coordinates, sats, hdop, gps_course, gps_speed_knots fields are of relevance now, which may get added to in the future.
    See the CSV header line to identify which field is which. 
    The CSV file may change in the future to not contain all the extra fields so don't assume field positions will be the same with each file.

4. Use an NTP library to initialise the RTC, providing current date and time to the simulator. Timezone doesn't matter, use UTC.

5. Be able to convert csv file into NMEA format messages according to the samples/sigrok-logic-output-neo6m.log format which you will stream out on the UART port which the M5 Stick C Plus has at 9600 baud. This is a Transmit only task. The messages read from the file will all be converted to GPS FIX messages.

6. To figure out how to publish the simulated stream, parse the samples/sigrok-logic-output-neo6m.log:
    Ignore the "uart-1: " prefix and newline characters
    Assume the double question marks are unprintable characters representing the checksums which you must compute for each NMEA message you publish.
    Assume the file contains an exact number of GPS messages, no partial messages.
    There is a duty cycle of publishing of those messages. You must publish on a similar duty cycle in the same order as you see in the sample.
    The sample data contains other informational messages like $GNTXT which still need to be simulated appropriately.
    It is important to follow the pattern of messages in the sample.
    Note this sample is only indicative to give you the type of output needed.
    You will need to make your own output based upon the data supplied in the csv file plus derived data as described.

7. The messages must be published on a schedule mimicking the schedule in the sample log file, it is not a message dump as fast as possible. Time between messages is important.
   However, note that the csv file has timestamps which do not equate to one GPS FIX per second, you will need to fill in the gaps appropriately assuming the GPS module would normally transmit one FIX per second - for example by duplicating FIX messages while correcting the time. If there is two seconds between FIX messages, then fake out another message to fill in the gap half way between the two known FIXES.
   You will need to also publish non-FIX messages which you find like $GNTXT between the FIX messages - use your nouse to figure this out - there may be other messages in the sample of relevance.

8. It is very important that you timestamp the messages in line with NTP-primed RTC in real-time and not use the timestamps from the csv file.

9. You must calculate the correct checksum for each NMEA message you are to publish.

10. You must indicate status on the M5 Stick C Plus.

11. You will use GPIO pins 32 and 33 for Serial Transmit / Receive. Refer to the online documentation for which is by standard receive and which is transmit.

12. You will provide a test harness and documentation.

