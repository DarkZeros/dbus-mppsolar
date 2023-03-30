#!/usr/bin/env python3

"""
Handle automatic connection with MPP Solar inverter compatible device (VEVOR)
This will output 2 dbus services, one for Inverter data another one for control
via VRM of the features.
"""
VERSION = 'v0.1' 

from gi.repository import GLib
import platform
import argparse
import logging
import sys
import os
import subprocess as sp
import json
from enum import Enum
import datetime
import dbus
import dbus.service

# our own packages
sys.path.insert(1, os.path.join(os.path.dirname(__file__), 'velib_python'))
from vedbus import VeDbusService

# Should we import and call manually? Mppsolar?
# sys.path.insert(1, os.path.join(os.path.dirname(__file__), 'mppsolar'))
#from vedbus import mppsolar

# Inverter commands to read from the serial
def runInverterCommand(command):
    global args
    global mainloop
    try: 
        output = sp.getoutput("mpp-solar -b {} -P PI30 -p {} -o json -c {}".format(args.baudrate, args.serial, command)).split('\n')
        parsed = [json.loads(o) for o in output]
    except Exception:
        mainloop.quit()
    return parsed

def setOutputSource(source):
    #POP<NN>: Setting device output source priority
    #    NN = 00 for utility first, 01 for solar first, 02 for SBU priority
    return runInverterCommand('POP{:02d}'.format(source))

def setChargerPriority(priority):
    #PCP<NN>: Setting device charger priority
    #  For KS: 00 for utility first, 01 for solar first, 02 for solar and utility, 03 for only solar charging
    #  For MKS: 00 for utility first, 01 for solar first, 03 for only solar charging
    return runInverterCommand('PCP{:02d}'.format(priority))

# def setMaxChargingCurrent(current):
#     #MNCHGC<mnnn><cr>: Setting max charging current (More than 100A)
#     #  Setting value can be gain by QMCHGCR command.
#     #  nnn is max charging current, m is parallel number.
#     return runInverterCommand('MNCHGC0{:04d}'.format(current))

def setMaxUtilityChargingCurrent(current):
    #MUCHGC<nnn><cr>: Setting utility max charging current
    #  Setting value can be gain by QMCHGCR command.
    #  nnn is max charging current, m is parallel number.
    return runInverterCommand('MUCHGC{:03d}'.format(current))

def isNaN(num):
    return num != num


# Allow to have multiple DBUS connections
class SystemBus(dbus.bus.BusConnection):
    def __new__(cls):
        return dbus.bus.BusConnection.__new__(cls, dbus.bus.BusConnection.TYPE_SYSTEM) 
class SessionBus(dbus.bus.BusConnection):
    def __new__(cls):
        return dbus.bus.BusConnection.__new__(cls, dbus.bus.BusConnection.TYPE_SESSION)
def dbusconnection():
    return SessionBus() if 'DBUS_SESSION_BUS_ADDRESS' in os.environ else SystemBus()

# Our MPP solar service that conencts to 2 dbus services (multi & vebus)
class DbusMppSolarService(object):
    def __init__(self, tty, deviceinstance, productname='MPPSolar Inverter', connection='MPPSolar interface'):
        self._tty = tty

        # Get data before broadcasting anything, or it will fail here
        self._invData = runInverterCommand('QID#QVFW')
        logging.debug("Successfully connected to inverter on {tty}, setting up dbus with /DeviceInstance = {deviceinstance}")

        # Create the services
        self._dbusmulti = VeDbusService(f'com.victronenergy.multi.mppsolar.{tty}', dbusconnection())
        #self._dbusvebus = VeDbusService(f'com.victronenergy.asd.mppsolar.{tty}', dbusconnection())

        # Set up default paths
        self.setupDefaultPaths(self._dbusmulti, connection, deviceinstance, productname)
        #self.setupDefaultPaths(self._dbusvebus, connection, deviceinstance, productname)

        # Create paths for 'multi'
        self._dbusmulti.add_path('/Ac/In/1/L1/V', 0)
        self._dbusmulti.add_path('/Ac/In/1/L1/I', 0)
        self._dbusmulti.add_path('/Ac/In/1/L1/P', 0)
        self._dbusmulti.add_path('/Ac/In/1/L1/F', 0)
        self._dbusmulti.add_path('/Ac/In/2/L1/V', 0)
        self._dbusmulti.add_path('/Ac/In/2/L1/I', 0)
        self._dbusmulti.add_path('/Ac/In/2/L1/P', 0)
        self._dbusmulti.add_path('/Ac/In/2/L1/F', 0)
        self._dbusmulti.add_path('/Ac/Out/L1/V', 0)
        self._dbusmulti.add_path('/Ac/Out/L1/I', 0)
        self._dbusmulti.add_path('/Ac/Out/L1/P', 0)
        self._dbusmulti.add_path('/Ac/Out/L1/S', 0)
        self._dbusmulti.add_path('/Ac/Out/L1/F', 0)
        self._dbusmulti.add_path('/Ac/In/1/Type', 1) #0=Unused;1=Grid;2=Genset;3=Shore
        self._dbusmulti.add_path('/Ac/In/2/Type', 1) #0=Unused;1=Grid;2=Genset;3=Shore
        self._dbusmulti.add_path('/Ac/In/1/CurrentLimit', 20)
        self._dbusmulti.add_path('/Ac/In/2/CurrentLimit', 20)
        self._dbusmulti.add_path('/Ac/NumberOfPhases', 1)
        self._dbusmulti.add_path('/Ac/ActiveIn/ActiveInput', 0)
        self._dbusmulti.add_path('/Ac/ActiveIn/Type', 0)
        self._dbusmulti.add_path('/Dc/0/Voltage', 0)
        self._dbusmulti.add_path('/Dc/0/Current', 0)
        #self._dbusmulti.add_path('/Dc/0/Temperature', 10)
        #self._dbusmulti.add_path('/Soc', 10)
        self._dbusmulti.add_path('/State', 0) #0=Off;1=Low Power;2=Fault;3=Bulk;4=Absorption;5=Float;6=Storage;7=Equalize;8=Passthru;9=Inverting;10=Power assist;11=Power supply;252=External control
        self._dbusmulti.add_path('/Mode', 0, writeable=True, onchangecallback=self._handlechangedvalue) #1=Charger Only;2=Inverter Only;3=On;4=Off
        self._dbusmulti.add_path('/Alarms/HighTemperature', 0)
        self._dbusmulti.add_path('/Alarms/HighVoltage', 0)
        self._dbusmulti.add_path('/Alarms/HighVoltageAcOut', 0)
        self._dbusmulti.add_path('/Alarms/LowTemperature', 0)
        self._dbusmulti.add_path('/Alarms/LowVoltage', 0)
        self._dbusmulti.add_path('/Alarms/LowVoltageAcOut', 0)
        self._dbusmulti.add_path('/Alarms/Overload', 0)
        self._dbusmulti.add_path('/Alarms/Ripple', 0)
        self._dbusmulti.add_path('/Yield/Power', 0)
        self._dbusmulti.add_path('/Yield/User', 0)
        self._dbusmulti.add_path('/Relay/0/State', None)
        self._dbusmulti.add_path('/MppOperationMode', 0) #0=Off;1=Voltage/current limited;2=MPPT active;255=Not available
        self._dbusmulti.add_path('/Pv/V', 0)
        self._dbusmulti.add_path('/ErrorCode', 0)
        self._dbusmulti.add_path('/Energy/AcIn1ToAcOut', 0)
        self._dbusmulti.add_path('/Energy/AcIn1ToInverter', 0)
        #self._dbusmulti.add_path('/Energy/AcIn2ToAcOut', 0)
        #self._dbusmulti.add_path('/Energy/AcIn2ToInverter', 0)
        self._dbusmulti.add_path('/Energy/AcOutToAcIn1', 0)
        #self._dbusmulti.add_path('/Energy/AcOutToAcIn2', 0)
        self._dbusmulti.add_path('/Energy/InverterToAcIn1', 0)
        #self._dbusmulti.add_path('/Energy/InverterToAcIn2', 0)
        self._dbusmulti.add_path('/Energy/InverterToAcOut', 0)
        self._dbusmulti.add_path('/Energy/OutToInverter', 0)
        self._dbusmulti.add_path('/Energy/SolarToAcIn1', 0)
        #self._dbusmulti.add_path('/Energy/SolarToAcIn2', 0)
        self._dbusmulti.add_path('/Energy/SolarToAcOut', 0)
        self._dbusmulti.add_path('/Energy/SolarToBattery', 0)
        self._dbusmulti.add_path('/History/Daily/0/Yield', 0)
        self._dbusmulti.add_path('/History/Daily/0/MaxPower', 0)
        self._dbusmulti.add_path('/History/Daily/0/Pv/0/Yield', 0)
        self._dbusmulti.add_path('/History/Daily/0/Pv/0/MaxPower', 0)
        self._dbusmulti.add_path('/Pv/0/V', 0)
        self._dbusmulti.add_path('/Pv/0/P', 0)
        self._dbusmulti.add_path('/Temperature', 123)

        self._dbusmulti.add_path('/Alarms/LowSoc', 0)
        self._dbusmulti.add_path('/Alarms/HighDcVoltage', 0)
        self._dbusmulti.add_path('/Alarms/LowDcVoltage', 0)
        self._dbusmulti.add_path('/Alarms/LineFail', 0)
        self._dbusmulti.add_path('/Alarms/GridLost', 0)
        self._dbusmulti.add_path('/Alarms/Connection', 0)
           
        # Create paths for 'vebus'
        '''self._dbusvebus.add_path('/Ac/ActiveIn/L1/F', 0)
        self._dbusvebus.add_path('/Ac/ActiveIn/L1/I', 0)
        self._dbusvebus.add_path('/Ac/ActiveIn/L1/V', 0)
        self._dbusvebus.add_path('/Ac/ActiveIn/L1/P', 0)
        self._dbusvebus.add_path('/Ac/ActiveIn/L1/S', 0)
        self._dbusvebus.add_path('/Ac/ActiveIn/P', 0)
        self._dbusvebus.add_path('/Ac/ActiveIn/S', 0)
        self._dbusvebus.add_path('/Ac/ActiveIn/ActiveInput', 0)

        self._dbusvebus.add_path('/Ac/In/1/CurrentLimit', 0, writeable=True, onchangecallback=self._handlechangedvalue)
        self._dbusvebus.add_path('/Ac/In/1/CurrentLimitIsAdjustable', 1)
        self._dbusvebus.add_path('/Ac/In/2/CurrentLimit', 0, writeable=True, onchangecallback=self._handlechangedvalue)
        self._dbusvebus.add_path('/Ac/In/2/CurrentLimitIsAdjustable', 1)
        self._dbusvebus.add_path('/Settings/SystemSetup/AcInput1', 1)
        self._dbusvebus.add_path('/Settings/SystemSetup/AcInput2', 1)
        
        self._dbusvebus.add_path('/Mode', 0, writeable=True, onchangecallback=self._handlechangedvalue)
        self._dbusvebus.add_path('/State', 0)
        #self._dbusvebus.add_path('/Ac/In/1/L1/V', 0, writeable=False, onchangecallback=self._handlechangedvalue)'''

        GLib.timeout_add(4000, self._update)
    
    def setupDefaultPaths(self, service, connection, deviceinstance, productname):
        # Create the management objects, as specified in the ccgx dbus-api document
        service.add_path('/Mgmt/ProcessName', __file__)
        service.add_path('/Mgmt/ProcessVersion', 'version f{VERSION}, and running on Python ' + platform.python_version())
        service.add_path('/Mgmt/Connection', connection)

        # Create the mandatory objects
        service.add_path('/DeviceInstance', deviceinstance)
        service.add_path('/ProductId', self._invData[0].get('serial_number', 0))
        service.add_path('/ProductName', productname)
        service.add_path('/FirmwareVersion', self._invData[1].get('main_cpu_firmware_version', 0))
        service.add_path('/HardwareVersion', 0)
        service.add_path('/Connected', 1)

        # Create the paths for modifying the system manually
        service.add_path('/Settings/Reset', None, writeable=True, onchangecallback=self._handlechangedvalue)
        service.add_path('/Settings/Charger', None, writeable=True, onchangecallback=self._handlechangedvalue)
        service.add_path('/Settings/Output', None, writeable=True, onchangecallback=self._handlechangedvalue)

    def _update(self):
        logging.info("{} starting".format(datetime.datetime.now().time()))
        raw = runInverterCommand('QPIGS#QMOD#QPIWS')
        data, mode, warnings = raw
        logging.info(raw)
        with self._dbusmulti as s:
            # 1=Charger Only;2=Inverter Only;3=On;4=Off -> Control from outside
            if 'error' in data and 'short' in data['error']:
                s['/State'] = 0
                s['/Alarms/Connection'] = 2
            
            # 0=Off;1=Low Power;2=Fault;3=Bulk;4=Absorption;5=Float;6=Storage;7=Equalize;8=Passthru;9=Inverting;10=Power assist;11=Power supply;252=External control
            invMode = mode.get('device_mode', None)
            if invMode == 'Battery':
                s['/State'] = 9 # Inverting
            elif invMode == 'Line':
                if data.get('is_charging_on', 0) == 1:
                    s['/State'] = 3 # Passthru + Charging? = Bulk
                else:    
                    s['/State'] = 8 # Passthru
            elif invMode == 'Standby':
                s['/State'] = data.get('is_charging_on', 0) * 6 # Standby = 0 -> OFF, Stanby + Charging = 6 -> "Storage" Storing power
            else:
                s['/State'] = 0 # OFF

            # For my installation specific case: 
            # - When the load is off the output is unkonwn, the AC1/OUT are connected directly, and inverter is bypassed
            if data.get('is_load_on', 0) == 0:
                data['ac_output_active_power'] = data['ac_output_aparent_power'] = None          

            # Normal operation, read data
            s['/Dc/0/Voltage'] = data.get('battery_voltage', None)
            s['/Dc/0/Current'] = data.get('battery_discharge_current', None)

            s['/Ac/Out/L1/V'] = data.get('ac_output_voltage', None)
            s['/Ac/Out/L1/F'] = data.get('ac_output_frequency', None)
            s['/Ac/Out/L1/P'] = data.get('ac_output_active_power', None)
            s['/Ac/Out/L1/S'] = data.get('ac_output_aparent_power', None)

            # Charger input, same as AC1 but separate line data
            s['/Ac/In/1/L1/V'] = s['/Ac/In/2/L1/V'] = data.get('ac_input_voltage', None)
            s['/Ac/In/1/L1/F'] = s['/Ac/In/2/L1/F'] = data.get('ac_input_frequency', None)

            # It does not give us power of AC in, we need to compute it from the current state + Output power + Charging on + Current
            s['/Ac/In/1/L1/P'] = 0 if invMode == 'Battery' else s['/Ac/Out/L1/P']
            s['/Ac/In/2/L1/P'] = data.get('is_charging_on', 0) * 17 * data.get('battery_voltage', 0)

            # Compute the currents as well?
            # s['/Ac/Out/L1/I'] = s['/Ac/Out/L1/P'] / s['/Ac/Out/L1/V']
            # s['/Ac/In/1/L1/I'] = s['/Ac/In/1/L1/P'] / s['/Ac/In/1/L1/V']
            # s['/Ac/In/2/L1/I'] = s['/Ac/In/2/L1/P'] / s['/Ac/In/2/L1/V']

            # Select which output is more "active" to show (0 -> Active1, 1 -> Active2)
            s['/Ac/ActiveIn/ActiveInput'] = 0 + ((s['/Ac/In/2/L1/P'] or 0) > (s['/Ac/In/1/L1/P'] or 0))

            # Update some Alarms
            s['/Alarms/Connection'] = 0
            s['/Alarms/HighTemperature'] = warnings.get('over_temperature_fault', '1')
            s['/Alarms/Overload'] = warnings.get('overload_fault', '1')
            s['/Alarms/HighVoltage'] = warnings.get('bus_over_fault', '1')
            s['/Alarms/LowVoltage'] = warnings.get('bus_under_fault', '1')
            s['/Alarms/HighVoltageAcOut'] = warnings.get('inverter_voltage_too_high_fault', '1')
            s['/Alarms/LowVoltageAcOut'] = warnings.get('inverter_voltage_too_low_fault', '1')
            s['/Alarms/HighDcVoltage'] = warnings.get('battery_voltage_to_high_fault', '1')
            s['/Alarms/LowDcVoltage'] = warnings.get('battery_low_alarm_warning', '1')
            s['/Alarms/LineFail'] =  warnings.get('line_fail_warning', '1')

        logging.info("{} done".format(datetime.datetime.now().time()))
        return True

    def _handlechangedvalue(self, path, value):
        logging.info("someone else updated %s to %s" % (path, value))
        if path == '/Settings/Reset':
            logging.info("Restarting!")
            mainloop.quit()
        if path == '/Ac/In/2/CurrentLimit':
            logging.info("setting max utility charging current to = {} ({})".format(value, setMaxUtilityChargingCurrent(value)))
        if path == '/Mode': # 1=Charger Only;2=Inverter Only;3=On;4=Off(?)
            if value == 1:
                logging.info("setting mode to 'Charger Only'(Charger=Util & Output=Util->solar) ({},{})".format(setChargerPriority(0), setOutputSource(0)))
            elif value == 2:
                logging.info("setting mode to 'Inverter Only'(Charger=Solar & Output=SBU) ({},{})".format(setChargerPriority(3), setOutputSource(2)))
            elif value == 3:
                logging.info("setting mode to 'ON=Charge+Invert'(Charger=Util & Output=SBU) ({},{})".format(setChargerPriority(0), setOutputSource(2)))
            elif value == 4:
                logging.info("setting mode to 'OFF'(Charger=Solar & Output=Util->solar) ({},{})".format(setChargerPriority(3), setOutputSource(0)))
            else:
                logging.info("setting mode not understood ({})".format(value))
        if path == '/Settings/Charger':
            if value == 0:
                logging.info("setting charger priority to utility first ({})".format(setChargerPriority(value)))
            elif value == 1:
                logging.info("setting charger priority to solar first ({})".format(setChargerPriority(value)))
            elif value == 2:
                logging.info("setting charger priority to solar and utility ({})".format(setChargerPriority(value)))
            else:
                logging.info("setting charger priority to only solar ({})".format(setChargerPriority(3)))
        if path == '/Settings/Output':
            if value == 0:
                logging.info("setting output Utility->Solar priority ({})".format(setOutputSource(value)))
            elif value == 1:
                logging.info("setting output solar->Utility priority ({})".format(setOutputSource(value)))
            else:
                logging.info("setting output SBU priority ({})".format(setOutputSource(2)))
        
        return True # accept the change

def main():
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument("--baudrate","-b", default=2400, type=int)
    parser.add_argument("--serial","-s", required=True, type=str)
    global args
    args = parser.parse_args()

    from dbus.mainloop.glib import DBusGMainLoop
    # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
    DBusGMainLoop(set_as_default=True)

    mppservice = DbusMppSolarService(tty=args.serial.strip("/dev/"), deviceinstance=0)

    logging.info('Created service & connected to dbus, switching over to GLib.MainLoop() (= event based)')

    global mainloop
    mainloop = GLib.MainLoop()
    mainloop.run()


if __name__ == "__main__":
    main()