"""
Definition of GDPS Carbolite Gero Furnace
"""

# Import the BaseInstrument class
from src.instrument import BaseInstrument

# Import the umodbus library and supporting libraries
from pymodbus.client import ModbusTcpClient

# Common variables
MODBUS_PORT = 502
MODBUS_REGISTER_READ_ADDRESS = 1
MODBUS_REGISTER_WRITE_ADDRESS = 2
MODBUS_REGISTER_COUNT = 1

# ------------------------------------------------------------------------------
# Helper functions


def read_temperature(host):
    try:
        register_value = host.read_input_registers(
            address=MODBUS_REGISTER_READ_ADDRESS, count=MODBUS_REGISTER_COUNT
        )
        if not register_value.isError():
            result = register_value.registers
        else:
            raise ValueError(f"Error reading register: {register_value}")
        return float(result[0])
    except Exception as e:
        print(f"Error reading! \n\t {e}")
        return None


def write_temperature(host, setpoint):
    try:
        result = host.write_register(
            address=MODBUS_REGISTER_WRITE_ADDRESS, value=int(setpoint)
        )
    except Exception as e:
        print(f"Error writing! \n\t {e}")
        pass


class Instrument(BaseInstrument):
    def __init__(self):
        self.clients = None

    def initialise(self, state):
        try:
            self.clients = ModbusTcpClient(host=state.config["DEVICE_ADDRESS"],
                                           port=MODBUS_PORT)
        except Exception as e:
            print(f"Error initializing ModbusTcpClient!\n{e}")

    def simulate_initialise(self, state):
        pass

    def go_to_setpoint(self, state):
        setpoint = state.status["setpoint"]
        write_temperature(self.clients, setpoint)

    def simulate_go_to_setpoint(self, state):
        pass

    def set_config(self, config):
        pass

    def get_measurement(self, state):
        value = read_temperature(self.clients)
        state.measurement = value

        measurement = {"temperature": value}
        return measurement

    def simulate_get_measurement(self, state):
        # Simple simulation: move simulated temperature towards setpoint
        # Linearly if heating, exponentially if cooling
        current_temp = state.measurement
        target_temp = state.status["setpoint"]

        if target_temp is None:
            return {"temperature": current_temp}
        elif current_temp < target_temp:
            current_temp += min(1.0, target_temp - current_temp)
        elif current_temp > target_temp:
            current_temp -= (current_temp - target_temp) * 0.1

        state.measurement = current_temp
        measurement = {"temperature": current_temp}
        return measurement
