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

### Recognizable Access Points

The script currently recognizes common AP models and families, including:

- Cisco Aironet: 700 / 700W, 1000, 1040, 1100, 1130 AG, 1140, 1200, 1230 AG, 1240 / 1240 AG, 1250, 1260, 1300 Bridge, 1400 Bridge, 1500 Lightweight Outdoor Mesh, 1520 Lightweight Outdoor Mesh, 1600, 1810, 1830, 1850, 2800, 3700, 3800, 4800
- Cisco Catalyst Wi-Fi APs: 9100 series, 9130, 9160, 9166, 9176
- Cisco Meraki: MR series (MR33, MR36, MR42, MR44, MR45, MR46, MR52, MR53, MR56, MR57, MR70, MR74, MR76, MR78, MR84, MR86), GR10, GR60
- Cisco Small Business: WAP121, WAP150, WAP321, WAP371, WAP551, WAP561, WAP571, WAP581, AP500
- Aruba / HPE: AP-205, AP-215, AP-225, AP-303, AP-305, AP-315, AP-325, AP-335, AP-505, AP-515, AP-535, AP-555, AP-615, AP-635, AP-655, AP-735, AP-755, IAP-205-RW, IAP-315-RW, IAP-325-RW
- Ubiquiti UniFi: UAP-AC-LITE, UAP-AC-LR, UAP-AC-PRO, UAP-AC-EDU, UAP-AC-HD, UAP-AC-SHD, U6-Lite, U6-LongRange, U6-Pro, U6-Enterprise, U6-Mesh, U7-Pro, U7-Pro-Wall, U7-Outdoor
- Ruckus / CommScope: ZoneFlex R310/R510/R610/R710/R720, R350/R550/R650/R750/R850, R760/R770, T310/T750
- TP-Link Omada: EAP225, EAP245, EAP265-HD, EAP610, EAP620-HD, EAP650, EAP660-HD, EAP670, EAP690E-HD, EAP773, EAP783
- Extreme Networks / Aerohive: AP122, AP130, AP230, AP250, AP305C, AP410C, AP510C, AP650X, AP4000, AP5010
- Netgear: WAC510, WAC540, WAC720, WAC730, WAX214, WAX610, WAX620, WAX630, WAX630E
- Fortinet FortiAP: FAP-221E, FAP-321E, FAP-421E, FAP-231F, FAP-431F, FAP-831F, FAP-431G, FAP-433G

The list is not exhaustive; the script matches these models by substring in neighbor names and descriptions.

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
