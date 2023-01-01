#!/usr/bin/env python3

"""
A class to put a simple service on the dbus, according to victron standards, with constantly updating
paths. See example usage below. It is used to generate dummy data for other processes that rely on the
dbus. See files in dbus_vebus_to_pvinverter/test and dbus_vrm/test for other usage examples.
To change a value while testing, without stopping your dummy script and changing its initial value, write
to the dummy data via the dbus. See example.
https://github.com/victronenergy/dbus_vebus_to_pvinverter/tree/master/test
"""
from gi.repository import GLib
import platform
import argparse
import logging
import sys
import os
import subprocess as sp
import json

# our own packages
sys.path.insert(1, os.path.join(os.path.dirname(__file__), 'velib_python'))
from vedbus import VeDbusService
# Should we import and call manually?
# sys.path.insert(1, os.path.join(os.path.dirname(__file__), 'mpp-solar'))

def getInverterData(command):
    global args
    output = sp.getoutput("mpp-solar -b {} -P pi30 -p {} -o json -c {}".format(args.baudrate, args.serial, command)).split('\n')
    return [json.loads(o) for o in output]

def isNaN(num):
    return num != num

class DbusMppSolarService(object):
    def __init__(self, servicename, deviceinstance, paths, productname='MPPSolar Inverter', connection='MPPSolar interface'):
        self._dbusservice = VeDbusService(servicename)
        self._paths = paths

        logging.debug("%s /DeviceInstance = %d" % (servicename, deviceinstance))

        # Create the management objects, as specified in the ccgx dbus-api document
        self._dbusservice.add_path('/Mgmt/ProcessName', __file__)
        self._dbusservice.add_path('/Mgmt/ProcessVersion', 'Unkown version, and running on Python ' + platform.python_version())
        self._dbusservice.add_path('/Mgmt/Connection', connection)

        # Create the mandatory objects
        invData = getInverterData('QID#QVFW')
        self._dbusservice.add_path('/DeviceInstance', deviceinstance)
        self._dbusservice.add_path('/ProductId', invData[0].get('serial_number', 0))
        self._dbusservice.add_path('/ProductName', productname)
        self._dbusservice.add_path('/FirmwareVersion', invData[1].get('main_cpu_firmware_version', 0))
        self._dbusservice.add_path('/HardwareVersion', 0)
        self._dbusservice.add_path('/Connected', 1)

        for path, settings in self._paths.items():
            self._dbusservice.add_path(
                path, settings['initial'], writeable=True, onchangecallback=self._handlechangedvalue)

        GLib.timeout_add(5000, self._update)

    def _update(self):
        raw = getInverterData('QPIGS#QMOD#QPIWS')
        data, mode, warnings = raw
        logging.info(raw)
        with self._dbusservice as s:
            if 'error' in data and 'short' in data['error']:
                s['/Mode'] = 4 # OFF
            else:
                s['/Mode'] = 3 # ON
            
            invMode = mode.get('device_mode', None)
            if invMode == 'Battery':
                s['/State'] = 9 # Inverting
            elif invMode == 'Line':
                s['/State'] = 8 # Passthru
            else:
                s['/State'] = 0 # OFF
            
            # 1=Charger Only;2=Inverter Only;3=On;4=Off
            # 0=Off;1=Low Power;2=Fault;3=Bulk;4=Absorption;5=Float;6=Storage;7=Equalize;8=Passthru;9=Inverting;10=Power assist;11=Power supply;252=External control

            # Normal operation, read data
            s['/Dc/0/Voltage'] = data.get('battery_voltage', None)
            s['/Dc/0/Current'] = data.get('battery_discharge_current', None)

            s['/Ac/Out/L1/V'] = data.get('ac_output_voltage', None)
            s['/Ac/Out/L1/F'] = data.get('ac_output_frequency', None)
            s['/Ac/Out/L1/P'] = data.get('ac_output_active_power', None)
            s['/Ac/Out/L1/S'] = data.get('ac_output_aparent_power', None)

            s['/Ac/In/1/L1/V'] = data.get('ac_input_voltage', None)
            s['/Ac/In/1/L1/F'] = data.get('ac_input_frequency', None)

            # It does not give us power of AC in, we need to compute it from the current state + Output power
            s['/Ac/In/1/L1/P'] = 0 if invMode == 'Battery' and s['/Mode'] == 3 else s['/Ac/Out/L1/P']

        return True

    def _handlechangedvalue(self, path, value):
        logging.debug("someone else updated %s to %s" % (path, value))
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

    output = DbusMppSolarService(
        servicename='com.victronenergy.multi.mppsolar.{}'.format(args.serial.strip("/dev/")),
        deviceinstance=0,
        paths={
            #'/Ac/In/Forward': {'initial': 0, 'update': 1},
            #'/Position': {'initial': 0, 'update': 0},
            #'/Nonupdatingvalue/UseForTestingWritesForExample': {'initial': None},
            #'/DbusInvalid': {'initial': None}

            # '/Ac/ActiveIn/L1/F': {'initial': -1},
            # '/Ac/ActiveIn/L1/I': {'initial': -1},
            # '/Ac/ActiveIn/L1/P': {'initial': -1},
            # #'/Ac/ActiveIn/L1/S': {'initial': -1},
            # '/Ac/ActiveIn/L1/V': {'initial': -1},

            # '/Ac/ActiveIn/P': {'initial': -1},
            # #'/Ac/ActiveIn/S': {'initial': -1},

            # '/Ac/Out/L1/F': {'initial': -1},
            # '/Ac/Out/L1/I': {'initial': -1},
            # '/Ac/Out/L1/P': {'initial': -1},
            # '/Ac/Out/L1/S': {'initial': -1},
            # '/Ac/Out/L1/V': {'initial': -1},

            # '/Ac/ActiveIn/ActiveInput': {'initial': 0},               #Active input: 0 = ACin-1, 1 = ACin-2, 240 is none (inverting).
            # '/Ac/ActiveIn/Connected': {'initial': 1},               #Active input: 0 = ACin-1, 1 = ACin-2, 240 is none (inverting).
            # '/Ac/State/IgnoreAcIn1': {'initial': 0},                # 0 = AcIn1 is not ignored; 1 = AcIn1 is being ignored (by assistant configuration).
            # '/Ac/In/1/Type': {'initial': 1},                        #0=Unused;1=Grid;2=Genset;3=Shore
            # '/Ac/In/1/CurrentLimit': {'initial': -1},
            # '/Ac/In/1/CurrentLimitIsAdjustable': {'initial': 0},
            # '/Ac/NumberOfPhases': {'initial': 1},
            # '/Settings/SystemSetup/AcInput1': {'initial': 1},         #Type of that input: 0 (Not used), 1 (Grid), 2(Generator), 3(Shore).
            # #'/Settings/SystemSetup/AcInput2': {'initial': 0},         #Type of that input: 0 (Not used), 1 (Grid), 2(Generator), 3(Shore).
            # '/Ac/PowerMeasurementType': {'initial': 0}, # Type of measurement, 0-4, more accurate is 4

            # '/Dc/0/Voltage': {'initial': -1},
            # '/Dc/0/Current': {'initial': -1},
            # '/Dc/0/Power': {'initial': -1},
            # '/Dc/0/Temperature': {'initial': -1},

            # '/Mode': {'initial': 4},                # 1=Charger Only;2=Inverter Only;3=On;4=Off
            # '/State': {'initial': 0},                #0=Off;1=Low Power;2=Fault;3=Bulk;4=Absorption;5=Float;6=Storage;7=Equalize;8=Passthru;9=Inverting;10=Power assist;11=Power supply;252=External control
            # '/ModeIsAdjustable': {'initial': 0},
            # '/VebusChargeState': {'initial': 0},
            # #'/VebusSetChargeState': {'initial': 0},

            # # For all alarms: 0=OK, 1=Warning, 2=Alarm
            # '/Alarms/HighDcCurrent': {'initial': 0},
            # '/Alarms/HighDcVoltage': {'initial': 0},
            # '/Alarms/LowBattery': {'initial': 0},
            # '/Alarms/PhaseRotation': {'initial': 0},
            # '/Alarms/Ripple': {'initial': 0},
            # '/Alarms/TemperatureSensor': {'initial': 0},
            # '/Alarms/L1/HighTemperature': {'initial': 0},
            # '/Alarms/L1/LowBattery': {'initial': 0},
            # '/Alarms/L1/Overload': {'initial': 0},
            # '/Alarms/L1/Ripple': {'initial': 0},

            # '/Leds/Mains': {'initial': 0},
            # '/Leds/Bulk': {'initial': 0},
            # '/Leds/Absorption': {'initial': 0},
            # '/Leds/Float': {'initial': 0},
            # '/Leds/Overload': {'initial': 0},
            # '/Leds/LowBattery': {'initial': 0},
            # '/Leds/Temperature': {'initial': 0},

            # # /Ac/ActiveIn/*                          <- The ActiveIn paths show the readings of the
            # #                                         current active input. Readings for the other,
            # #                                         AC input are, unfortunately, not available.
            # #                                         The hardware can only measure the data for the
            # #                                         active one (which can also be not connected - ie.
            # #                                         ac-ignored).
            # # /Ac/ActiveIn/L1/F                       <- Frequency
            # # /Ac/ActiveIn/L1/I                       <- Current
            # # /Ac/ActiveIn/L1/P                       <- Real power (or not, for very old devices, see
            # #                                         /Ac/PowerMeasurementType, further below).
            # # /Ac/ActiveIn/L1/S                       <- Note that all */S paths only change their
            # #                                         value. No update of the change is transmitted
            # #                                         in order to reduce D-Bus load. (and we don't
            # #                                         need nor use the /S paths anywhere).
            # # /Ac/ActiveIn/L1/V
            # # #/Ac/ActiveIn/Lx/*                       <- Same as L1

            # # /Ac/ActiveIn/P                          <- Total power.
            # # /Ac/ActiveIn/S                          <- Total apparent power (and see */S node above)

            # # #AC Output measurements:
            # # /Ac/Out/L*/*                            <- Same as ActiveIn, and also same */S paths
            # #                                         restriction as explained above.
            # #                                         There is only a measurement for the total output
            # #                                         power; ie AC out1 & AC out 2 are not independently
            # #                                         measured.

            # # #ActiveIn other paths:
            # # /Ac/ActiveIn/Connected                  <- 0 when inverting, 1 when connected to
            # #                                         an AC in. Path is not available when
            # #                                         VE.Bus is connected via VE.Can.
            # #                                         DEPRECATED in favor of /Ac/ActiveIn/ActiveInput

            # # /Ac/ActiveIn/ActiveInput                <- Active input: 0 = ACin-1, 1 = ACin-2,
            # #                                         240 is none (inverting).
            # #                                         Note open issue:
            # #                                         https://github.com/victronenergy/venus-private/issues/21
            # # /Ac/ActiveIn/CurrentLimit               <- DEPRECATED in favor of /Ac/In/[1 and 2] paths
            # # /Ac/ActiveIn/CurrentLimitIsAdjustable   <- DEPRECATED in favor of /Ac/In/[1 and 2] paths
            # #                                         0 when disabled in VEConfigure, or when
            # #                                         there is a VE.Bus BMS or DMC, etc.

            # # /Ac/In/1/CurrentLimit                   <- these are the new and current paths to control input
            # # /Ac/In/1/CurrentLimitIsAdjustable          current limits.
            # # /Ac/In/2/CurrentLimit
            # # /Ac/In/2/CurrentLimitIsAdjustable

            # # /Settings/SystemSetup/AcInput1          <- since approx v2.70 or v2.80, these paths exist and indicate the
            # # /Settings/SystemSetup/AcInput2             type of that input: 0 (Not used), 1 (Grid), 2(Generator), 3(Shore).

            # # /Ac/PowerMeasurementType                <- Indicates the type of power measurement used by the system. The
            # #                                         best one, 4, is the method used for all recent hardware and software
            # #                                         since 2018 or even earlier.
            # #                                         0 = Apparent power only -> under the /P paths, apparent power
            # #                                             is published.
            # #                                         1 = Real power, but only measured by phase masters, and not
            # #                                             synced in time. (And multiplied by number of units in
            # #                                             parallel)
            # #                                         2 = Real power, from all devices, but at different points in time
            # #                                         3 = Real power, at the same time snapshotted, but only by the
            # #                                             phase masters and then multiplied by number of units in
            # #                                             parallel.
            # #                                         4 = Real power, from all devices and at snaphotted at the same
            # #                                             moment.

            # # #Ac state information:
            # # /Ac/State/IgnoreAcIn1           0 = AcIn1 is not ignored; 1 = AcIn1 is being ignored (by assistant configuration).
            # # /Ac/State/SplitPhaseL2Passthru  0 = L1+L2 shorted together; 1 = L2 connected to external L2; Invalid = unused in this configuration
            # #                                 NOTE: Split Phase Passthru is available only in the 120V versions for the North American markets.

            # # #For all alarms: 0=OK; 1=Warning; 2=Alarm
            # # #Generic alarms:
            # # /Alarms/HighDcCurrent                   <- 0=OK; 2=High DC current condition in one or more Multis/Quattros
            # # /Alarms/HighDcVoltage                   <- 0= K; 2=High DC voltage
            # # /Alarms/LowBattery                       
            # # /Alarms/PhaseRotation                   <- 0=OK, 1=Warning when AC input phase rotation direction is wrong 
            # # /Alarms/Ripple
            # # /Alarms/TemperatureSensor               <- Battery temperature sensor alarm
            
            # # #Phase specific alarms:
            # # /Alarms/L1/HighTemperature              <- inverter/charger high temperature alarm
            # # /Alarms/L1/LowBattery
            # # /Alarms/L1/Overload
            # # /Alarms/L1/Ripple
            # # /Alarms/L2/*                            <- same
            # # /Alarms/L3/*                            <- same
                
            # # /Dc/0/Voltage                           <- Battery Voltage
            # # /Dc/0/Current                           <- Battery current in Ampere, positive when charging
            # # /Dc/0/Power                             <- Battery power in Watts, positive when charging
            # # /Dc/0/Temperature                       <- Battery temperature in degrees Celsius

            # # /Mode                                   <- Position of the switch.
            # #                                         1=Charger Only;2=Inverter Only;3=On;4=Off
            # #                                         Make sure to read CCGX manual, and limitations
            # #                                         of this switch, for example when using a VE.Bus BMS.
            # # /ModeIsAdjustable                       <- 0. Switch position cannot be controlled remotely (typically because a VE.Bus BMS is present).
            # #                                         1. Switch position can be controlled remotely
            # # /VebusChargeState                       <- 1. Bulk
            # #                                         2. Absorption
            # #                                         3. Float
            # #                                         4. Storage
            # #                                         5. Repeat absorption
            # #                                         6. Forced absorption
            # #                                         7. Equalise
            # #                                         8. Bulk stopped
            # # /VebusSetChargeState                    <- 1. Force to Equalise. 1 hour 1, 2 or 4 V above
            # #                                             absorption (12/24/48V). Charge current is limited
            # #                                             to 1/4 of normal value. Will be followed by a normal
            # #                                             24-hour float state.
            # #                                         2. Force to Absorption, for maximum absorption time.
            # #                                             Will be followed by a normal 24-hour float state.
            # #                                         3. Force to Float, for 24 hours. 
            # #                                         (from "Interfacing with VE.Bus products – MK2 Protocol" doc)

            # # #The new CurrentLimit paths, only available on VE.Bus 415 or later:
            # # /Ac/In/1/CurrentLimit                   <- R/W for input current limit.
            # # /Ac/In/1/CurrentLimit GetMin            <- not implemented!)
            # # /Ac/In/1/CurrentLimit GetMax
            # # /Ac/In/1/CurrentLimitIsAdjustable
            # # /Ac/In/2/*                              <- same


            # # #LEDs: 0 = Off, 1 = On, 2 = Blinking, 3 = Blinking inverted
            # # /Leds/Mains
            # # /Leds/Bulk
            # # /Leds/Absorption
            # # /Leds/Float
            # # /Leds/Inverter
            # # /Leds/Overload
            # # /Leds/LowBattery
            # # /Leds/Temperature

            # # #BMS: only contains valid data if a VE.Bus BMS is present
            # # /Bms/AllowToCharge     <- 0=No, 1=Yes
            # # /Bms/AllowToDischarge  <- 0=No, 1=Yes
            # # /Bms/BmsExpected       <- 0=No, 1=Yes
            # # /Bms/Error             <- 0=No, 1=Yes

            '/Ac/In/1/L1/V': {'initial': 0},
            #'/Ac/In/1/L2/V': {'initial': 10},
            #'/Ac/In/1/L3/V': {'initial': 10},
            '/Ac/In/1/L1/I': {'initial': 0},
            #'/Ac/In/1/L2/I': {'initial': 10},
            #'/Ac/In/1/L3/I': {'initial': 10},
            '/Ac/In/1/L1/P': {'initial': 0},
            #'/Ac/In/1/L2/P': {'initial': 0.1},
            #'/Ac/In/1/L3/P': {'initial': 0.1},
            '/Ac/In/1/L1/F': {'initial': 0},
            '/Ac/Out/L1/V': {'initial': 0},
            #'/Ac/Out/L2/V': {'initial': 10},
            #'/Ac/Out/L3/V': {'initial': 10},
            '/Ac/Out/L1/I': {'initial': 0},
            #'/Ac/Out/L2/I': {'initial': 10},
            #'/Ac/Out/L3/I': {'initial': 10},
            '/Ac/Out/L1/P': {'initial': 0},
            '/Ac/Out/L1/S': {'initial': 0},
            #'/Ac/Out/L2/P': {'initial': 0.1},
            #'/Ac/Out/L3/P': {'initial': 0.1},
            '/Ac/Out/L1/F': {'initial': 0},
            '/Ac/In/1/Type': {'initial': 1}, #0=Unused;1=Grid;2=Genset;3=Shore
            #'/Ac/In/2/Type': {'initial': 0}, #0=Unused;1=Grid;2=Genset;3=Shore
            '/Ac/In/1/CurrentLimit': {'initial': 10},
            #'/Ac/In/2/CurrentLimit': {'initial': 10},
            '/Ac/NumberOfPhases': {'initial': 1},
            '/Ac/ActiveIn/ActiveInput': {'initial': 0},
            '/Dc/0/Voltage': {'initial': 0},
            '/Dc/0/Current': {'initial': 0},
            #'/Dc/0/Temperature': {'initial': 10},
            #'/Soc': {'initial': 10},
            '/State': {'initial': 0}, #0=Off;1=Low Power;2=Fault;3=Bulk;4=Absorption;5=Float;6=Storage;7=Equalize;8=Passthru;9=Inverting;10=Power assist;11=Power supply;252=External control
            '/Mode': {'initial': 4}, #1=Charger Only;2=Inverter Only;3=On;4=Off
            '/Alarms/HighTemperature': {'initial': 0},
            '/Alarms/HighVoltage': {'initial': 0},
            '/Alarms/HighVoltageAcOut': {'initial': 0},
            '/Alarms/LowTemperature': {'initial': 0},
            '/Alarms/LowVoltage': {'initial': 0},
            '/Alarms/LowVoltageAcOut': {'initial': 0},
            '/Alarms/Overload': {'initial': 0},
            '/Alarms/Ripple': {'initial': 0},
            '/Yield/Power': {'initial': 0},
            '/Yield/User': {'initial': 0},
            #'/Relay/0/State': {'initial': 1},
            '/MppOperationMode': {'initial': 0}, #0=Off;1=Voltage/current limited;2=MPPT active;255=Not available
            '/Pv/V': {'initial': 0},
            '/ErrorCode': {'initial': 0},
            # '/Energy/AcIn1ToAcOut': {'initial': 0},
            # '/Energy/AcIn1ToInverter': {'initial': 0},
            # #'/Energy/AcIn2ToAcOut': {'initial': 0},
            # #'/Energy/AcIn2ToInverter': {'initial': 0},
            # '/Energy/AcOutToAcIn1': {'initial': 0},
            # #'/Energy/AcOutToAcIn2': {'initial': 0},
            # '/Energy/InverterToAcIn1': {'initial': 0},
            # #'/Energy/InverterToAcIn2': {'initial': 0},
            # '/Energy/InverterToAcOut': {'initial': 0},
            # '/Energy/OutToInverter': {'initial': 0},
            # '/Energy/SolarToAcIn1': {'initial': 0},
            # #'/Energy/SolarToAcIn2': {'initial': 0},
            # '/Energy/SolarToAcOut': {'initial': 0},
            # '/Energy/SolarToBattery': {'initial': 0},
            '/History/Daily/0/Yield': {'initial': 0},
            '/History/Daily/0/MaxPower': {'initial': 0},
            #'/History/Daily/1/Yield': {'initial': 10},
            #'/History/Daily/1/MaxPower': {'initial': 1},
            '/History/Daily/0/Pv/0/Yield': {'initial': 0},
            #'/History/Daily/0/Pv/1/Yield': {'initial': 10},
            #'/History/Daily/0/Pv/2/Yield': {'initial': 10},
            #'/History/Daily/0/Pv/3/Yield': {'initial': 10},
            #'/History/Daily/1/Pv/0/Yield': {'initial': 10},
            #'/History/Daily/1/Pv/1/Yield': {'initial': 10},
            #'/History/Daily/1/Pv/2/Yield': {'initial': 10},
            #'/History/Daily/1/Pv/3/Yield': {'initial': 10},
            '/History/Daily/0/Pv/0/MaxPower': {'initial': 0},
            #'/History/Daily/0/Pv/1/MaxPower': {'initial': 1},
            #'/History/Daily/0/Pv/2/MaxPower': {'initial': 1},
            #'/History/Daily/0/Pv/3/MaxPower': {'initial': 1},
            #'/History/Daily/1/Pv/0/MaxPower': {'initial': 1},
            #'/History/Daily/1/Pv/1/MaxPower': {'initial': 1},
            #'/History/Daily/1/Pv/2/MaxPower': {'initial': 1},
            #'/History/Daily/1/Pv/3/MaxPower': {'initial': 1},
            '/Pv/0/V': {'initial': 0},
            #'/Pv/1/V': {'initial': 10},
            #'/Pv/2/V': {'initial': 10},
            #'/Pv/3/V': {'initial': 10},
            '/Pv/0/P': {'initial': 0},
            #'/Pv/1/P': {'initial': 1},
            #'/Pv/2/P': {'initial': 1},
            #'/Pv/3/P': {'initial': 1},
            '/Alarms/LowSoc': {'initial': 0},
            '/Yield/User': {'initial': 0},
            '/Temperature': {'initial': 123}
        })

    logging.info('Connected to dbus, and switching over to GLib.MainLoop() (= event based)')
    mainloop = GLib.MainLoop()
    mainloop.run()


if __name__ == "__main__":
    main()