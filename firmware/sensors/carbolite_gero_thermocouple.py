"""
Definition of GDPS Carbolite Gero Furnace
"""

# Import the BaseSensor class
from sensor import BaseSensor

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


@BaseSensor.register_sensor("temp_left")
class TempLeft(BaseSensor):

    def __init__(self):
        self.host = None

    def intialise(self):
        try:
            print(MODBUS_PORT)
            print(IP_ADDRS["left"])
            self.host = ModbusTcpClient(host=IP_ADDRS["left"], port=MODBUS_PORT)
            print("managed to register host for left")
        except Exception as e:
            print(f"Error initializing ModbusTcpClient for temp_left!\n{e}")
            pass

    def go_to_setpoint(self, setpoint):
        # print(f'Setting left temperature to {setpoint}')
        write_temperature(self.host, setpoint)

    def set_config(self, config):
        pass

    def get_measurement(self, state):
        measurement = read_temperature(self.host)
        state.measurement = measurement
        return measurement


@BaseSensor.register_sensor("temp_main")
class TempMain(BaseSensor):

    def __init__(self):
        self.host = None

    def initialise(self):
        try:
            self.host = ModbusTcpClient(host=IP_ADDRS["main"], port=MODBUS_PORT)
        except Exception as e:
            print(f"Error initializing ModbusTcpClient for temp_main!\n{e}")
            pass

    def go_to_setpoint(self, setpoint):
        # print(f'Setting main temperature to {setpoint}')
        write_temperature(self.host, setpoint * 10)

    def set_config(self, config):
        pass

    def get_measurement(self, state):
        measurement = read_temperature(self.host) / 10
        state.measurement = measurement
        return measurement


@BaseSensor.register_sensor("temp_right")
class TempRight(BaseSensor):

    def __init__(self):
        self.host = None
    
    def initialise(self):
        try:
            self.host = ModbusTcpClient(host=IP_ADDRS["right"], port=MODBUS_PORT)
        except Exception as e:
            print(f"Error initializing ModbusTcpClient for temp_right!\n{e}")
            pass

    def go_to_setpoint(self, setpoint):
        # print(f'Setting right temperature to {setpoint}')
        write_temperature(self.host, setpoint)

    def set_config(self, config):
        pass

    def get_measurement(self, state):
        measurement = read_temperature(self.host)
        state.measurement = measurement
        return measurement
