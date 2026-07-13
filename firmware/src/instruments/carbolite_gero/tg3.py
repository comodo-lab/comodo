"""
Definition of GDPS Carbolite Gero Furnace
"""

# Import the BaseInstrument class
from src.instrument import BaseInstrument

# Import the umodbus library and supporting libraries
from pymodbus.client import ModbusTcpClient

# Common variables
MODBUS_PORT = 502
MODBUS_REGISTER_COUNT = 1


# ------------------------------------------------------------------------------
# Helper functions


def read_register(host, register):
    try:
        register_value = host.read_input_registers(
            address=register, count=MODBUS_REGISTER_COUNT
        )
        if not register_value.isError():
            result = register_value.registers
        else:
            raise ValueError(f"Error reading register: {register_value}")
        return float(result[0])
    except Exception as e:
        print(f"Error reading! \n\t {e}")
        return None


def write_register(host, register, value):
    try:
        result = host.write_register(address=register, value=int(value))
    except Exception as e:
        print(f"Error writing! \n\t {e}")
        pass


# ------------------------------------------------------------------------------
# Instrument Class


class Instrument(BaseInstrument):
    available_variables = {
        "temperature": {"sensor": 1, "actuator": 2},
    }

    def __init__(self):
        self.client = None
        self._simulated = {}

    def initialise(self, state):
        if state.config.get("SIMULATE"):
            self._simulated = {"temperature": 0}
            return
        self.client = ModbusTcpClient(
            host=state.config["DEVICE_ADDRESS"], port=MODBUS_PORT
        )

    def go_to_setpoint(self, state, variable):
        target = state.status["setpoints"][variable]
        if state.config.get("SIMULATE"):
            self._simulated[variable] = target
            return
        write_register(
            self.client, self.available_variables[variable]["actuator"], target
        )

    def get_measurement(self, state, variable):
        if state.config.get("SIMULATE"):
            return self._default_sim(state, variable)
        return read_register(self.client, self.available_variables[variable]["sensor"])

    def set_config(self, config):
        pass
