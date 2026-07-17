"""
Eurotherm 3204 Temperature Controller
"""

# Import the BaseInstrument class
from src.instrument import BaseInstrument

from pymodbus.client import ModbusRtuClient
import serial

SLAVE_ADDRESS = 1

MODBUS_REGISTER_COUNT = 1
BAUDRATE = 9600
BYTESIZE = serial.EIGHTBITS
PARITY = serial.PARITY_NONE
STOPBITS = serial.STOPBITS_ONE
TIMEOUT = 1  # seconds


# ------------------------------------------------------------------------------
# Helper functions


def read_register(client, slave, register):
    try:
        result = client.read_holding_registers(
            address=register, count=MODBUS_REGISTER_COUNT, slave=slave
        )
        if result.isError():
            raise ValueError(f"Error reading register: {result}")
        return float(result.registers[0])
    except Exception as e:
        print(f"Error reading register {register}: {e}")
        return None


def write_register(client, slave, register, value):
    try:
        result = client.write_register(
            address=register, value=int(value), slave=slave
        )
        if result.isError():
            raise ValueError(f"Error writing register: {result}")
    except Exception as e:
        print(f"Error writing register {register}: {e}")


# ------------------------------------------------------------------------------
# Instrument Class


class Instrument(BaseInstrument):
    available_variables = {
        "temperature": {"sensor": 0, "actuator": 1},
    }

    def __init__(self):
        self.client = None
        self.slave = None
        self._simulated = {}

    def initialise(self, state):
        if state.config.get("SIMULATE"):
            self._simulated = {"temperature": 0}
            return

        port = state.config["DEVICE_ADDRESS"]
        self.slave = SLAVE_ADDRESS

        self.client = ModbusRtuClient(
            port=port,
            baudrate=BAUDRATE,
            bytesize=BYTESIZE,
            parity=PARITY,
            stopbits=STOPBITS,
            timeout=TIMEOUT,
        )

        if not self.client.connect():
            raise ConnectionError(f"Failed to connect to Modbus RTU on {port}")

        print(f"Connected to Eurotherm 3204 on {port} (slave {self.slave})")

    def go_to_setpoint(self, state, variable):
        target = state.status["setpoints"][variable]
        if state.config.get("SIMULATE"):
            self._simulated[variable] = target
            return

        register = self.available_variables[variable]["actuator"]
        write_register(self.client, self.slave, register, target)

    def get_measurement(self, state, variable):
        if state.config.get("SIMULATE"):
            return self._default_sim(state, variable)

        register = self.available_variables[variable]["sensor"]
        value = read_register(self.client, self.slave, register)
        if value is None:
            raise RuntimeError(f"Failed to read {variable} from register {register}")
        return value

    def set_config(self, config):
        pass
