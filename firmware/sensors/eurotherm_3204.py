# Import the BaseSensor class
from sensor import BaseSensor

# Import the umodbus library and supporting libraries
from umodbus.serial import Serial as ModbusRTUMaster
from machine import Pin,UART

@BaseSensor.register_sensor("temperature")
class Eurotherm3204(BaseSensor):
    host = None

    # Eurotherm Modbus Address
    slave_addr = 2
    
    def __init__(self):
        # Uart configuration
        uart_id = 0
        rtu_pins = (Pin(0), Pin(1))

        # ModbusRTUMaster instance
        self.host = ModbusRTUMaster(
            pins=rtu_pins,
            baudrate=9600,
            data_bits=8,
            stop_bits=1,
            parity=None,
            uart_id=uart_id
        )

    
    def get_measurement(self, state):
        # Read the temperature
        try:
            register_value = self.host.read_holding_registers(
                slave_addr=self.slave_addr, 
                starting_addr=1, # Temperature register
                register_qty=1)  # Read one register
            state.measurement = register_value[0] 
        except Exception as e:
            print(f'Error reading hreg! \n\t {e}')
            pass
    
        return state.measurement

    def go_to_setpoint(self, setpoint):
        pass

    def set_config(self, config):
        pass

    
