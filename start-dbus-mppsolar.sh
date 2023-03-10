#!/bin/bash
#
# Start script for gps_dbus
#   First parameter: tty device to use
#
# Keep this script running with daemon tools. If it exits because the
# connection crashes, or whatever, daemon tools will start a new one.
#

. /opt/victronenergy/serial-starter/run-service.sh

app=/data/etc/dbus-mppsolar/dbus-mppsolar.py

# Baudrates to use
start -b 2400 -s /dev/$tty
