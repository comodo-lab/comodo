"""
ESI HP1410B Pressure Transmitter

Custom ASCII protocol over RS-485 serial.
Reads pressure and temperature values.

Protocol:
  - Master sends: #<serial>:<command>[:<arg1>]\r\n
  - Slave responds: $<serial>:<command>[:<field>:<value>]\r\n
  - Use #0:ID to discover an unknown single device on the bus
"""

from src.instrument import BaseInstrument

import serial

BAUDRATE = 57600
BYTESIZE = serial.EIGHTBITS
PARITY = serial.PARITY_NONE
STOPBITS = serial.STOPBITS_ONE
TIMEOUT = 1  # seconds

START_MASTER = "#"
START_SLAVE = "$"
DIVIDER = ":"
END = "\r\n"


# ------------------------------------------------------------------------------
# Protocol helpers


def send(ser, serial_no, command, parameters=None):
    serial_str = f"{serial_no}{DIVIDER}" if serial_no is not None else ""
    arguments = f"{DIVIDER}{DIVIDER.join(parameters)}" if parameters else ""
    msg = f"{START_MASTER}{serial_str}{command}{arguments}{END}"
    ser.write(msg.encode())
    print(f"> {msg.strip()}")


def receive(ser):
    line = ser.readline()
    if not line:
        print("Empty response received")
        return None

    response = line.decode().strip()
    print(f"< {response}")
    return response


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


# ------------------------------------------------------------------------------
# Instrument Class


class Instrument(BaseInstrument):
    available_variables = {
        "pressure": {"sensor": "RP", "unit": "Bar"},
        "temperature": {"sensor": "RT", "unit": "C"},
    }

    def __init__(self):
        self.ser = None
        self.serial_no = None
        self._simulated = {}

    def initialise(self, state):
        if state.config.get("SIMULATE"):
            self._simulated = {v: 0 for v in self.available_variables}
            return

        port = state.config["DEVICE_ADDRESS"]

        self.ser = serial.Serial(
            port=port,
            baudrate=BAUDRATE,
            bytesize=BYTESIZE,
            parity=PARITY,
            stopbits=STOPBITS,
            timeout=TIMEOUT,
        )

        # Auto-discover device serial number
        self.serial_no = read_id(self.ser)
        if not self.serial_no:
            raise ConnectionError(f"No ESI HP1410B found on {port}")

        print(f"Connected to ESI HP1410B (serial: {self.serial_no}) on {port}")

    def get_measurement(self, state, variable):
        if state.config.get("SIMULATE"):
            return self._default_sim(state, variable)

        var = self.available_variables[variable]
        value = read_value(self.ser, self.serial_no, var["sensor"], var["unit"])

        if value is None:
            raise RuntimeError(f"Failed to read {variable}")

        return value

    def set_config(self, config):
        pass
