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
        # print(f"Read is {result[0]}")
        return float(result[0])
    except Exception as e:
        print(f"Error reading! \n\t {e}")
        return None


def write_temperature(host, setpoint):
    try:
        result = host.write_register(
            address=MODBUS_REGISTER_WRITE_ADDRESS, value=int(setpoint)
        )
        # print(f'Result of writing {setpoint}: {result}')
    except Exception as e:
        print(f"Error writing! \n\t {e}")
        pass


class Instrument(BaseInstrument):
    def __init__(self):
        self.client = {}
        self.simulated_temperature = 20
        self.simulated_setpoint = 20

    def intialise(self, state):
        try:
            self.clients = ModbusTcpClient(host=state.config["DEVICE_ADDRESS"],
                                           port=MODBUS_PORT)
        except Exception as e:
            print(f"Error initializing ModbusTcpClient for {name}!\n{e}")

    def go_to_setpoint(self, setpoint):
        print(f'Setting temperature to {setpoint}')
        write_temperature(self.clients, setpoint)

    def simulate_go_to_setpoint(self, setpoint):
        print(f"(Simulated) Setting temperature to {setpoint}")
        self.simulated_setpoint = setpoint

    def set_config(self, config):
        pass

    def get_measurement(self, state):
        measurement = read_temperature(client)
        state.measurement = measurement
        return measurement

    def simulate_get_measurement(self, state):
        # Simple simulation: move simulated temperature towards setpoint
        # Linearly if heating, exponentially if cooling

        current_temp = self.simulated_temperature
        target_temp = self.simulated_setpoint
        print(f"(Simulated) Current temp: {current_temp}, Target: {target_temp}")
        if current_temp < target_temp:
            print("(Simulated) Heating up")
            current_temp += min(1.0, target_temp - current_temp)
        elif current_temp > target_temp:
            print("(Simulated) Cooling down")
            current_temp -= (current_temp - target_temp) * 0.1
        print(f"(Simulated) New temp for {name}: {current_temp}")

        self.simulated_temperature = current_temp
        state.measurement = current_temp
        return current_temp
