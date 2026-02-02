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

IP_ADDRS = {
    "main": "192.168.111.222",
    "left": "192.168.111.224",
    "right": "192.168.111.225",
}

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
        self.clients = {}
        self.simulated_temperature = {"main": 25.0, "left": 25.0, "right": 25.0}
        self.simulated_setpoint = {"main": 25.0, "left": 25.0, "right": 25.0}

    def intialise(self):
        for name, ip in IP_ADDRS.items():
            try:
                self.clients[name] = ModbusTcpClient(host=ip, port=MODBUS_PORT)
            except Exception as e:
                print(f"Error initializing ModbusTcpClient for {name}!\n{e}")

    def go_to_setpoint(self, setpoint):
        print(f'Setting main temperature to {setpoint}')
        write_temperature(self.clients["main"], setpoint)
        write_temperature(self.clients["left"], setpoint-10)
        write_temperature(self.clients["right"], setpoint-10)

    def simulate_go_to_setpoint(self, setpoint):
        print(f"(Simulated) Setting main temperature to {setpoint}")
        self.simulated_setpoint["main"] = setpoint
        self.simulated_setpoint["left"] = setpoint - 10
        self.simulated_setpoint["right"] = setpoint - 10

    def set_config(self, config):
        pass

    def get_measurement(self, state):
        measurements = {}
        for name, client in self.clients.items():
            measurement = read_temperature(client)
            measurements[name] = measurement
        state.measurement = measurements
        return measurements

    def simulate_get_measurement(self, state):
        # Simple simulation: move simulated temperature towards setpoint
        # Linearly if heating, exponentially if cooling
        measurements = {}
        for name in self.simulated_temperature.keys():
            current_temp = self.simulated_temperature[name]
            target_temp = self.simulated_setpoint[name]
            print(f"(Simulated) Current temp for {name}: {current_temp}, Target: {target_temp}")
            if current_temp < target_temp:
                # Heating linearly
                print("(Simulated) Heating up")
                current_temp += min(1.0, target_temp - current_temp)
            elif current_temp > target_temp:
                # Cooling exponentially
                print("(Simulated) Cooling down")
                current_temp -= (current_temp - target_temp) * 0.1
            print(f"(Simulated) New temp for {name}: {current_temp}")
            self.simulated_temperature[name] = current_temp
            measurements[name] = current_temp

        state.measurement = measurements
        print(f"(Simulated) Measurements: {measurements}")
        return measurements
