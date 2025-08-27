# FASE Firmware

Test status:

[![Raspberry Pi](https://github.com/UoM-RIT-FASE/FASE-firmware/actions/workflows/rpi.yml/badge.svg)](https://github.com/UoM-RIT-FASE/FASE-firmware/actions/workflows/rpi.yml)

[![Raspberry Pi Pico](https://github.com/UoM-RIT-FASE/FASE-firmware/actions/workflows/rpi-pico.yml/badge.svg)](https://github.com/UoM-RIT-FASE/FASE-firmware/actions/workflows/rpi-pico.yml)

### Unit tests

To run unit tests:

```console
$ micropython -m lib.unittest
```

### Adding ip addresses to local pi

For carbolite gero need to hit the following endpoints:

- Left sensor: `http://192.168.111.224`
- Main sensor: `http://192.168.111.222`
- Right sensor: `http://192.168.111.225`

to do this in linux run

```bash
$ ip addr add 192.168.111.200/25 dev eth0
```
