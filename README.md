# dbus-mppsolar
DBus VenusOS driver for MPPSolar inverter or compatible one

# INSTRUCTIONS

- Clone GIT & submodules:
  -- git clone --recurse-submodules https://github.com/DarkZeros/dbus-mppsolar /data/etc/dbus-mppsolar
  -- Need velib_python for execution of the service
  -- Need mpp-solar to communicate with Inverter
  -- Install pip & then install mpp-solar package

- Symlink & install service
   ln -s /data/etc/dbus-mppsolar/service /opt/victronenergy/service-templates/dbus-mppsolar

- Add service to  /etc/venus/serial-starter.conf (and optionally modify the default list to run for all cases):
...
service mppsolar        dbus-mppsolar
alias   default         gps:vedirect:mppsolar 
...

- Or add udev rule to run the service only if you connect your mppsolar inverter:

/etc/udev/rules.d/serial-starter.rules

ACTION=="add", ENV{ID_BUS}=="usb", ATTRS{idVendor}=="067b", ATTRS{serial}=="ELARb11A920",          ENV{VE_SERVICE}="mppsolar"