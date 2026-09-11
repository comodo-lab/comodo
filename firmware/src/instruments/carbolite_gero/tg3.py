"""
Definition of GDPS Carbolite Gero Furnace
"""

# System imports
from typing import ClassVar

# Instrument specific imports
from pymodbus.client import ModbusTcpClient

# Local imports
from src.instrument import BaseInstrument

# ======================================================================================
# Instrument Class
# --------------------------------------------------------------------------------------


class Instrument(BaseInstrument):
    available_variables: ClassVar[dict[str, dict]] = {
        "temperature": {
            "sensor": 1,
            "actuator": 2,
        },
    }

    def initialise(self):
        if self.config["SIMULATE"]:
            self.client = None
        else:
            self.client = ModbusTcpClient(host=self.config["ADDRESS"], port=MODBUS_PORT)

    def simulate(self, variable):
        return self._default_sim(variable)

    def get_measurement(self, variable):
        return read_register(self.client, self.available_variables[variable]["sensor"])

    def go_to_setpoint(self, variable, setpoint):
        write_register(
            self.client, self.available_variables[variable]["actuator"], setpoint
        )


# ======================================================================================

# ======================================================================================
# TG3 configuration and helper functions
# --------------------------------------------------------------------------------------
MODBUS_PORT = 502
MODBUS_REGISTER_COUNT = 1


# --------------------------------------------------------------------------------------
# Helper functions
# --------------------------------------------------------------------------------------
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


# ======================================================================================
