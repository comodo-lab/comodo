from __future__ import print_function
import sys, os
import time
import pprint
import json
import http.client
import re
from datetime import datetime

from sensor import BaseSensor

# Configuration Parameters
VERBOSE = False
SCAN_COUNT = 5
SCAN_INTERVAL = 9023  # ms between scans
DEFAULT_DWELL = 32  # ms dwell time
AMU = 50
TARGET_IP_ADDR = "192.168.1.100"


class MMSP:
    def __init__(self, target_ip, port=80):
        self.conn = http.client.HTTPConnection("%s:%d" % (target_ip, port), timeout=10)

    def send(self, request, verbose=None):
        if verbose is None:
            verbose = VERBOSE

        if verbose:
            print("Request: %s" % request)

        self.conn.request("GET", request)
        resp = self.conn.getresponse()
        http_status = resp.status

        if http_status != 200:
            if not verbose:
                print("Request: %s" % request)

            print("HTTP Status:", http_status)
            print("Response:", resp)
            return (http_status, resp.read())

        resp_txt = resp.read()
        try:
            resp_rtn = json.loads(resp_txt)
        except:
            resp_rtn = resp_txt
        if verbose:
            self._printResponse(resp_rtn)

        return (http_status, resp_rtn)

    def _printResponse(self, resp):
        if not isinstance(resp, dict):
            print("Response:", resp)
            return

        data = resp.get("data", None)
        conditions = resp.get("conditions")
        status = resp.get("name", None)
        if data is None:
            print("Response:")
            for key, value in list(resp.items()):
                print((" - %s:" % (key), value))
        else:
            outstr = pprint.pformat(data, 2)
            print(("Response: [%s]" % status, outstr))
        print("")


###############################################################################
# Scan Setup
###############################################################################
def configure_instrument(mmsp):
    print("Taking control...")
    mmsp.send("/mmsp/communication/control/set?force")
    mmsp.send("/mmsp/scanSetup/set?scanstop=1")

    print("Configuring ion source and detector...")
    mmsp.send("/mmsp/sensorIonSource/emissionCurrent/set?2000")
    mmsp.send("/mmsp/sensorIonSource/electronEnergy/set?70")
    mmsp.send("/mmsp/sensorIonSource/anode/set?250")
    mmsp.send("/mmsp/sensorIonSource/focus/set?25")
    mmsp.send("/mmsp/sensorIonSource/ionEnergyGlobal/set?8000")

    mmsp.send("/mmsp/generalControl/setEmission?On")
    mmsp.send("/mmsp/generalControl/setEM?On")
    mmsp.send("/mmsp/sensorDetector/emVoltage/set?841")

    print("Setting up sweep channel (0–50 amu, 5 points/amu, dwell=32)...")
    chan = 1
    mmsp.send(f"/mmsp/scanSetup/set?@channel={chan}&channelMode=Sweep")
    mmsp.send(f"/mmsp/scanSetup/set?@channel={chan}&enabled=True")
    mmsp.send(f"/mmsp/scanSetup/set?@channel={chan}&startMass=0")
    mmsp.send(f"/mmsp/scanSetup/set?@channel={chan}&stopMass={AMU}")
    mmsp.send(f"/mmsp/scanSetup/set?@channel={chan}&ppamu=5")
    mmsp.send(f"/mmsp/scanSetup/set?@channel={chan}&dwell={DEFAULT_DWELL}")

    print("Applying acquisition settings...")
    mmsp.send(f"/mmsp/scanSetup/set?startchannel=1&stopchannel=1")
    mmsp.send(f"/mmsp/scanSetup/set?scanCount={SCAN_COUNT}")
    mmsp.send(f"/mmsp/scanSetup/set?scanInterval={SCAN_INTERVAL}")
    mmsp.send(f"/mmsp/scanSetup/dwellGlobal/set?{DEFAULT_DWELL}")
    mmsp.send(f"/mmsp/scanSetup/CaptureFileName/set?{CAPTURE_FILE}")

    print("Starting Scan...")
    mmsp.send("/mmsp/scanSetup/set?scanstart=1")


def dump_scan(mmsp):
    http_code, resp = mmsp.send("/mmsp/measurement/nextScan/get")
    data = resp["data"]
    system_status = data["systemStatus"]
    current_scan = data["currentScan"]
    scan_num = data["scannum"]
    scan_values = data["values"]

    if scan_values is not None:
        # Print live scan data (real time data for InfluxDB)
        print(scan_num, scan_values)
        return scan_values


@BaseSensor.register_sensor("mass_spec")
class MassSpec(BaseSensor):

    def __init__(self):
        self.mmsp = MMSP(TARGET_IP_ADDR)
        return

    def set_config(self, config):
        configure_instrument(self.mmsp)
        return

    def get_measurement(self, state):
        """Get the measurement

        Returns:
            float: A random temperature value for testing purposes
        """
        scan = dump_scans(mmsp)

        state.measurement = scan
        return state.measurement

    def go_to_setpoint(self, setpoint):
        """Go to the setpoint
        Args:
            setpoint: float: The setpoint
        Returns:
            None
        """
        self.setpoint = setpoint

    def set_config(self, config):
        pass
