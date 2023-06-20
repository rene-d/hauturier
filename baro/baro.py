#!/usr/bin/env python3

import serial
from datetime import datetime

# Synology:
# insmod /lib/modules/cdc-acm.ko
# /dev/ttyACM0

ser = serial.Serial("/dev/cu.usbmodem101", baudrate=9600)

# https://gpsd.gitlab.io/gpsd/NMEA.html#_xdr_transducer_measurement

while True:
    line = ser.readline()

    now = datetime.now()
    line = line.decode().rstrip()
    print(f"{now.isoformat()};{line}")
