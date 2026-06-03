import time
import requests

from src.instrument import BaseInstrument

# Configuration Parameters
VERBOSE = True
SCAN_COUNT = 1
SCAN_INTERVAL = 9023  # ms between scans
DEFAULT_DWELL = 32  # ms dwell time
AMU = 50
TARGET_IP_ADDR = "192.168.1.100"

CAPTURE_FILE = f"test_scan.msd"


class MMSP:

    def __init__(self, target_ip, port=80):
        self.base_url = f"http://{target_ip}:{port}"
        self.session = requests.Session()
        self.session.timeout = 10
        print(self.session.get(self.base_url))
        print(f"Connected to {self.base_url}")

    def send(self, request, verbose=None):
        if verbose is None:
            verbose = VERBOSE

        url = f"{self.base_url}{request}"
        if verbose:
            print("Request:", url)

        try:
            resp = self.session.get(url)
            resp.raise_for_status()
        except requests.RequestException as e:
            print("Request failed:", e)
            return (None, str(e))

        if not verbose:
            print("Request:", url)
        print("HTTP Status:", resp.status_code)
        print("Response:", resp.text)
        # return (resp.status_code, resp.text)

        try:
            resp_rtn = resp.json()
        except ValueError:
            resp_rtn = resp.text

        if verbose:
            print(resp_rtn)

        return (resp.status_code, resp_rtn)

    def configure(self):
        print("Taking control...")
        self.send("/mmsp/communication/control/set?force")
        self.send("/mmsp/scanSetup/set?scanstop=1")

        print("Configuring ion source and detector...")
        self.send("/mmsp/instrumentIonSource/emissionCurrent/set?2000")
        self.send("/mmsp/instrumentIonSource/electronEnergy/set?70")
        self.send("/mmsp/instrumentIonSource/anode/set?250")
        self.send("/mmsp/instrumentIonSource/focus/set?25")
        self.send("/mmsp/instrumentIonSource/ionEnergyGlobal/set?8000")

        self.send("/mmsp/generalControl/setEmission?On")
        self.send("/mmsp/generalControl/setEM?On")
        self.send("/mmsp/instrumentDetector/emVoltage/set?841")

        print("Setting up sweep channel (0–50 amu, 5 points/amu, dwell=32)...")
        chan = 1
        self.send(f"/mmsp/scanSetup/set?@channel={chan}&channelMode=Sweep")
        self.send(f"/mmsp/scanSetup/set?@channel={chan}&enabled=True")
        self.send(f"/mmsp/scanSetup/set?@channel={chan}&startMass=0")
        self.send(f"/mmsp/scanSetup/set?@channel={chan}&stopMass={AMU}")
        self.send(f"/mmsp/scanSetup/set?@channel={chan}&ppamu=1")
        self.send(f"/mmsp/scanSetup/set?@channel={chan}&dwell={DEFAULT_DWELL}")

        print("Applying acquisition settings...")
        self.send(f"/mmsp/scanSetup/set?startchannel=1&stopchannel=1")
        self.send(f"/mmsp/scanSetup/set?scanCount={SCAN_COUNT}")
        self.send(f"/mmsp/scanSetup/set?scanInterval={SCAN_INTERVAL}")
        self.send(f"/mmsp/scanSetup/dwellGlobal/set?{DEFAULT_DWELL}")
        self.send(f"/mmsp/scanSetup/CaptureFileName/set?{CAPTURE_FILE}")

    def dump_scans(self):
        last_report = -1
        while True:
            time.sleep(1)
            http_code, resp = self.send("/mmsp/measurement/nextScan/get")
            if not isinstance(resp, dict) or "data" not in resp:
                continue
            data = resp["data"]
            system_status = data["systemStatus"]
            current_scan = data["currentScan"]
            scan_num = data["scannum"]
            scan_values = data["values"]

            if scan_values is not None:
                # Print live scan data (real time data for InfluxDB)
                print(scan_num, scan_values)
                return scan_values, scan_num

            if (system_status & 0x2) == 0:
                if current_scan == scan_num:
                    break

    def wait_for_scans(self):
        last_report = -1
        while True:
            time.sleep(1)
            http_code, resp = self.send("/mmsp/scanInfo/get?currentScan&scanning")
            if not isinstance(resp, dict) or "data" not in resp:
                continue
            current_scan = resp["data"]["currentScan"]
            scanning = resp["data"]["scanning"]
            if not scanning:
                print("\rAll Done, finished scanning")
                break
            elif current_scan != last_report:
                msg = "Scan %d/%d" % (current_scan, SCAN_COUNT)
                print("\r\t%-20s" % msg, end="")
                last_report = current_scan

    def run_and_get_scan(self):
        print("Starting Scan...")
        self.send("/mmsp/scanSetup/set?scanstart=1")
        print("Waiting for scans to complete...")
        self.wait_for_scans()
        print("Scan complete.")
        print("Downloading scans...")
        scan_values = self.dump_scans()[0]

        # --- Correct negative noise ---
        print("Correcting negative noise...")
        print("Original scan values (0–50 AMU):")
        print(scan_values)
        scan_values = [max(0, x) for x in scan_values]
        print("Corrected scan values (0–50 AMU, negative values zeroed):")
        print(scan_values)

        # --- Map to integer AMUs only ---
        points_per_amu = (len(scan_values) - 1) // AMU
        integer_amu_values = scan_values[::points_per_amu]

        # Ensure we have exactly AMU+1 points (0–50)
        if len(integer_amu_values) != AMU + 1:
            # Sometimes rounding can cause off-by-one
            integer_amu_values = integer_amu_values[: AMU + 1]

        # --- Convert to dictionary ---
        scan_dict = {i: val for i, val in enumerate(integer_amu_values)}

        print("Scan dictionary (0–50 AMU, negative values zeroed):")
        print(scan_dict)

        return scan_dict


class MassSpec(BaseInstrument):

    def __init__(self):
        self.mmsp = None
        self._device_address = TARGET_IP_ADDR
        return

    def initialise(self, state):
        self._device_address = state.config.get("DEVICE_ADDRESS", TARGET_IP_ADDR)
        self.mmsp = MMSP(self._device_address)

    def set_config(self, config):
        if self.mmsp is None:
            return
        self.mmsp.configure()
        return

    def get_measurement(self, state):
        """Get the measurement

        Returns:
            float: A random temperature value for testing purposes
        """
        scan = self.mmsp.run_and_get_scan()

        state.measurement = scan
        return state.measurement
