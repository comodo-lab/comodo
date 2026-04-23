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


def read_temperature(host, scale=1.0):
    if host is None:
        return None
    try:
        if not host.connected:
            host.connect()
        register_value = host.read_input_registers(
            address=MODBUS_REGISTER_READ_ADDRESS, count=MODBUS_REGISTER_COUNT
        )
        if not register_value.isError():
            result = register_value.registers
        else:
            raise ValueError(f"Error reading register: {register_value}")
        # Scale the reading (e.g. divide by 10.0 for 0.1 degree units)
        return float(result[0]) / scale
    except Exception as e:
        print(f"Error reading! \n\t {e}")
        return None


def write_temperature(host, setpoint, scale=1.0):
    if host is None:
        return
    try:
        if not host.connected:
            host.connect()
        # Scale the setpoint (e.g. multiply by 10 for 0.1 degree units)
        result = host.write_register(
            address=MODBUS_REGISTER_WRITE_ADDRESS, value=int(setpoint * scale)
        )
    except Exception as e:
        print(f"Error writing! \n\t {e}")
        pass


class Instrument(BaseInstrument):
    def __init__(self):
        self.clients = None
        self.scale = 1.0

    def initialise(self, state):
        try:
            addr = state.config["DEVICE_ADDRESS"]
            # Load scale from environment or state config
            self.scale = float(state.config.get("TEMPERATURE_SCALE", 1.0))
            print(f"Initializing ModbusTcpClient for {state.config['INSTRUMENT_ID']} at {addr} with scale {self.scale}")
            self.clients = ModbusTcpClient(host=addr,
                                           port=MODBUS_PORT)
            if self.clients.connect():
                print(f"ModbusTcpClient connected to {addr}")
            else:
                print(f"WARNING: ModbusTcpClient failed to connect to {addr}")
        except Exception as e:
            print(f"Error initializing ModbusTcpClient!\n{e}")
            self.clients = None

    def simulate_initialise(self, state):
        pass

    def go_to_setpoint(self, state):
        setpoint = state.status["setpoint"]
        write_temperature(self.clients, setpoint, scale=self.scale)

    def simulate_go_to_setpoint(self, state):
        pass

    def set_config(self, config):
        pass

    def get_measurement(self, state):
        value = read_temperature(self.clients, scale=self.scale)
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
