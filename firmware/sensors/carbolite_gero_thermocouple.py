"""
Definition of GDSP thermocouple read (left instance)
"""

# Import the BaseSensor class
from sensor import BaseSensor

# Import the umodbus library and supporting libraries
from lib.umodbus.tcp import TCP as ModbusTCPMaster

# Common variables
MODBUS_PORT = 502
MODBUS_SLAVE_ID = 255
MODBUS_REGISTER_READ_ADDRESS = 1
MODBUS_REGISTER_WRITE_ADDRESS = 2
MODBUS_REGISTER_COUNT = 1

IP_ADDRS = {
    "main": "192.168.111.222",
    "left": "192.168.111.224",
    "right": "192.168.111.225"
}

# ------------------------------------------------------------------------------
# Helper functions


def read_temperature(host):
    try:
        register_value = host.read_holding_registers(
            slave_addr=MODBUS_SLAVE_ID,
            starting_addr=MODBUS_REGISTER_READ_ADDRESS,
            register_qty=MODBUS_REGISTER_COUNT,
        )
        print(register_value[0])
        return float(register_value[0])
    except Exception as e:
        print(f'Error reading! \n\t {e}')
        return None


def write_temperature(host, setpoint):
    try:
        result = host.write_single_register(
            slave_addr=MODBUS_SLAVE_ID,
            register_address=MODBUS_REGISTER_WRITE_ADDRESS,
            register_value=int(setpoint)
        )
        print(f'Result of writing {setpoint}: {result}')
    except Exception as e:
        print(f'Error writing! \n\t {e}')
        pass


@BaseSensor.register_sensor("temp_left")
class TempLeft(BaseSensor):

    def __init__(self):
        try:
            print(MODBUS_PORT)
            print(IP_ADDRS["left"])
            self.host = ModbusTCPMaster(
                slave_ip=IP_ADDRS["left"],
                slave_port=MODBUS_PORT
            )
            print('managed to register host for left')
        except Exception as e:
            print(f'Error initializing ModbusTCPMaster for temp_left!\n{e}')
            pass

    def go_to_setpoint(self, setpoint):
        print(f'Setting left temperature to {setpoint}')
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
        try:
            self.host = ModbusTCPMaster(
                slave_ip=IP_ADDRS["main"],
                slave_port=MODBUS_PORT
            )
        except Exception as e:
            print(f'Error initializing ModbusTCPMaster for temp_main!\n{e}')
            pass

    def go_to_setpoint(self, setpoint):
        print(f'Setting main temperature to {setpoint}')
        write_temperature(self.host, setpoint*10)

    def set_config(self, config):
        pass

    def get_measurement(self, state):
        measurement = read_temperature(self.host) / 10
        state.measurement = measurement
        return measurement


@BaseSensor.register_sensor("temp_right")
class TempRight(BaseSensor):

    def __init__(self):
        try:
            self.host = ModbusTCPMaster(
                slave_ip=IP_ADDRS["right"],
                slave_port=MODBUS_PORT
            )
        except Exception as e:
            print(f'Error initializing ModbusTCPMaster for temp_right!\n{e}')
            pass

    def go_to_setpoint(self, setpoint):
        print(f'Setting right temperature to {setpoint}')
        write_temperature(self.host, setpoint)

    def set_config(self, config):
        pass

    def get_measurement(self, state):
        measurement = read_temperature(self.host)
        state.measurement = measurement
        return measurement


if __name__ == "__main__":
    host = ModbusTCPMaster(
        slave_ip=IP_ADDRS["left"],
        slave_port=MODBUS_PORT
    )
    read_temperature(host, None)
