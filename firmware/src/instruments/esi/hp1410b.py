"""
ESI HP1410B Pressure Transmitter interface.

Custom ASCII protocol over RS-485 serial, reading pressure and temperature:
  - Master sends: #<serial>:<command>[:<arg1>]\\r\\n
  - Slave responds: $<serial>:<command>[:<field>:<value>]\\r\\n
  - #0:ID discovers the serial number of a single (unknown) device on the bus
"""

# System imports
from typing import ClassVar

# Instrument specific imports
import serial

# Local imports
from src.instrument import BaseInstrument


# ======================================================================================
# Instrument Class
# --------------------------------------------------------------------------------------
class Instrument(BaseInstrument):
    available_variables: ClassVar[dict[str, dict]] = {
        "pressure": {
            "sensor": "RP",
            "unit": "Bar",
        },
        "temperature": {
            "sensor": "RT",
            "unit": "C",
        },
    }

    def initialise(self):
        self.serial_no = None
        if self.config["SIMULATE"]:
            self.ser = None
        else:
            self.ser = serial.Serial(
                port=self.config["ADDRESS"],
                baudrate=BAUDRATE,
                bytesize=BYTESIZE,
                parity=PARITY,
                stopbits=STOPBITS,
                timeout=TIMEOUT,
            )

    def simulate(self, variable):
        return self.default_sim(variable)

    def get_measurement(self, variable):
        try:
            # Discovers the device's serial number on the first measurement (or until it is found)
            if self.serial_no is None:
                self.serial_no = read_id(self.ser)
                if self.serial_no is None:
                    print(f"No ESI HP1410B found on {self.config['ADDRESS']}")
                    return None
                print(
                    f"Connected to ESI HP1410B (serial: {self.serial_no}) on {self.config['ADDRESS']}"
                )
            sensor = self.available_variables[variable]
            return read_value(
                self.ser, self.serial_no, sensor["sensor"], sensor["unit"]
            )
        except (serial.SerialException, ValueError) as e:
            print(f"Error reading {variable}: {e}")
            return None

    def go_to_setpoint(self, variable, setpoint):
        # No actuators available
        pass


# ======================================================================================

# ======================================================================================
# HP1410B configuration and helper functions
# --------------------------------------------------------------------------------------
BAUDRATE = 57600
BYTESIZE = serial.EIGHTBITS
PARITY = serial.PARITY_NONE
STOPBITS = serial.STOPBITS_ONE
TIMEOUT = 1  # seconds

START_MASTER = "#"
START_SLAVE = "$"
DIVIDER = ":"
END = "\r\n"


# --------------------------------------------------------------------------------------
# Helper functions
# --------------------------------------------------------------------------------------
def send(ser, serial_no, command, parameters=None):
    serial_str = f"{serial_no}{DIVIDER}" if serial_no is not None else ""
    arguments = f"{DIVIDER}{DIVIDER.join(parameters)}" if parameters else ""
    msg = f"{START_MASTER}{serial_str}{command}{arguments}{END}"
    ser.write(msg.encode())


def receive(ser):
    line = ser.readline()
    if not line:
        return None
    return line.decode().strip()


def read_id(ser):
    send(ser, 0, "ID", [])
    response = receive(ser)

    if not response:
        print("No response received to ID command")
        return None

    parts = response.split(DIVIDER)
    if len(parts) != 2:
        print("Incorrect response to ID command")
        return None

    device_id = parts[0].lstrip(START_SLAVE)
    return device_id


def read_value(ser, serial_no, command, unit):
    send(ser, serial_no, command, [unit])
    response = receive(ser)

    if not response:
        print(f"No response received to {command} command")
        return None

    parts = response.split(DIVIDER)
    if len(parts) != 4:
        print(f"Incorrect response to {command} command")
        return None

    value = float(parts[3])
    return value


# ======================================================================================
