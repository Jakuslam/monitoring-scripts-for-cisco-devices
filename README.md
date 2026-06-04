# Switch Discovery Scripts

This repository contains two Python scripts for Cisco switch discovery and analysis:

- `finding_AP.py` - discovers Access Points connected to switches using CDP/LLDP and exports them to `discovered_aps.csv`.
- `find_unused_ports.py` - scans switches for unused physical ports based on interface status and traffic counters, exporting results to `unused_ports.csv`.

## Requirements

- Python 3.8+
- `paramiko` library for SSH connectivity

Install dependencies with:

```bash
pip install paramiko
```

## Common setup

Both scripts use a CSV file containing devices to connect to. The default file is `devices.csv` and it must include headers and values like:

```csv
ip,username,password
192.168.1.10,admin,SecretPass
192.168.1.11,admin,SecretPass
```

If you want to use a different file name, pass it as the first command-line argument.

## finding_AP.py

### Purpose

Discover Access Points connected to switches by collecting CDP/LLDP neighbor detail information and filtering known AP models.

### Usage

```bash
python finding_AP.py [devices.csv]
```

### Output

- `discovered_aps.csv` - unique AP neighbor entries with columns:
  - `Switch hostname`
  - `Switch IP address`
  - `Port AP`
  - `Type AP`
  - `AP IP address`

### Notes

- The script parses `show cdp neighbors detail` and `show lldp neighbors detail` output.
- Access points are detected by matching known vendor/model strings against neighbor names and descriptions.

## find_unused_ports.py

### Purpose

Scan Cisco switches for unused physical ports by evaluating interface status and packet counters.

### Usage

```bash
python find_unused_ports.py [devices.csv]
```

### Output

- `unused_ports.csv` - lists switch IP addresses and unused port names.

### Notes

- The script runs the following commands on each switch:
  - `show running-config | include hostname`
  - `show interfaces`
  - `show ip interface brief`
- Ports are considered unused when the line protocol is down, traffic is below the defined threshold (`100` packets by default), and the interface is not administratively shut.

## File summary

- `finding_AP.py` - AP discovery using CDP/LLDP neighbor details.
- `find_unused_ports.py` - unused port scanning using interface status and packet counters.
- `devices.csv` - example device list used as input.
- `discovered_aps.csv` - generated output from AP discovery.
- `unused_ports.csv` - generated output from unused ports scanning.

## Troubleshooting

- If you see `Error: paramiko library is required`, install `paramiko` and retry.
- Ensure each CSV row has valid `ip`, `username`, and `password` values.
- Use device credentials that permit SSH access and show command execution on Cisco switches.
