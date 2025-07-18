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

def read_temperature():
    try:
        register_value = self.host.read_holding_registers(
            slave_addr=MODBUS_SLAVE_ID, 
            starting_addr=MODBUS_REGISTER_READ_ADDRESS, 
            register_qty=MODBUS_REGISTER_COUNT,
        )  
        state.measurement = register_value[0]
    except Exception as e:
        print(f'Error reading hreg! \n\t {e}')
        pass

def write_temperature(setpoint):
    try:
        result = self.host.write_single_register(
            slave_addr=MODBUS_SLAVE_ID,
            register_address=MODBUS_REGISTER_WRITE_ADDRESS,
            register_value=setpoint
        )           
    except Exception as e:
        print(f'Error reading hreg! \n\t {e}')
        pass
    

@BaseSensor.register_sensor("temp_left")
class TempLeft(BaseSensor):
    host = ModbusTCPMaster(
        slave_ip=IP_ADDRS["left"],
        slave_port=MODBUS_SLAVE_ID,
        timeout=5.0 # seconds
    )

    def __init__(self):
        return

    def go_to_setpoint(self, setpoint):
        write_temperature(setpoint)

    def set_config(self, config):
        pass

    def get_measurement(self, state):
        read_temperature()
    

@BaseSensor.register_sensor("temp_main")
class TempMain(BaseSensor):
    host = ModbusTCPMaster(
        slave_ip=IP_ADDRS["main"],
        slave_port=MODBUS_SLAVE_ID,
        timeout=5.0 # seconds
    )

    def __init__(self):
        return

    def go_to_setpoint(self, setpoint):
        write_temperature(setpoint)

    def set_config(self, config):
        pass

    def get_measurement(self, state):
        read_temperature()


@BaseSensor.register_sensor("temp_right")
class TempRight(BaseSensor):
    host = ModbusTCPMaster(
        slave_ip=IP_ADDRS["right"],
        slave_port=MODBUS_SLAVE_ID,
        timeout=5.0 # seconds
    )

    def __init__(self):
        return

    def go_to_setpoint(self, setpoint):
        write_temperature(setpoint)

    def set_config(self, config):
        pass

    def get_measurement(self, state):
        read_temperature()
