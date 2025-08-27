from lib.umodbus.tcp import TCP as ModbusTCPMaster

# valid network connections shall be made here

# RTU Host/Master setup
slave_tcp_port = 502            # port to send request on
IP_ADDRS = {
    "main": "192.168.111.222",
    "left": "192.168.111.224",
    "right": "192.168.111.225"
}  # IP address of client, to be adjusted
for side, slave_ip in IP_ADDRS.items():
    print(f"{side}: {slave_ip}")

    host = ModbusTCPMaster(
        slave_ip=slave_ip,
        slave_port=slave_tcp_port,
        # timeout=5.0               # optional, timeout in seconds, default 5.0
    )

    temp = host.read_holding_registers(
        slave_addr=255,
        starting_addr=1,
        register_qty=1
    )[0]

    print('Status of {}: {}'.format(side, temp))
