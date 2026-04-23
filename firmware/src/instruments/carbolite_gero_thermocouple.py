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
        # Scale the reading (divide raw value by scale to get degrees)
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
        # Scale the setpoint (multiply degrees by scale to get raw value)
        result = host.write_register(
            address=MODBUS_REGISTER_WRITE_ADDRESS, value=int(setpoint * scale)
        )
    except Exception as e:
        print(f"Error writing! \n\t {e}")
        pass


class Instrument(BaseInstrument):
    def __init__(self):
        self.clients = None
        self.read_scale = 1.0
        self.write_scale = 1.0

    def initialise(self, state):
        try:
            addr = state.config["DEVICE_ADDRESS"]
            inst_id = state.config.get("INSTRUMENT_ID", "")
            
            # Default scale: 10.0 for centre, 1.0 for everything else
            default_scale = 10.0 if inst_id == "furnace_centre" else 1.0
            
            # Support both a single scale or independent read/write scales from env
            base_scale = state.config.get("TEMPERATURE_SCALE")
            if base_scale is None:
                base_scale = default_scale
            else:
                base_scale = float(base_scale)

            read_scale = state.config.get("TEMPERATURE_READ_SCALE")
            self.read_scale = float(read_scale) if read_scale is not None else base_scale

            write_scale = state.config.get("TEMPERATURE_WRITE_SCALE")
            self.write_scale = float(write_scale) if write_scale is not None else base_scale
            
            print(f"Initializing ModbusTcpClient for {inst_id} at {addr}")
            print(f"  Final Scales -> Read: {self.read_scale}, Write: {self.write_scale}")
            
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
        write_temperature(self.clients, setpoint, scale=self.write_scale)

    def simulate_go_to_setpoint(self, state):
        pass

    def set_config(self, config):
        pass

    def get_measurement(self, state):
        value = read_temperature(self.clients, scale=self.read_scale)
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

        tolerance = (state.status.get("config") or {}).get("tolerance", 1)
        if abs(current_temp - target_temp) < tolerance:
            state.client.publish(
                f"instrument/{state.config['INSTRUMENT_ID']}/setpoint_reached", "true"
            )

        measurement = {"temperature": current_temp}
        return measurement
