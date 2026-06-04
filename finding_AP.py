"""
Script to find Access Points connected to switches.

Version: 1.0.0
Author: Jakub Slama
"""

import paramiko
import time
import re
from typing import List, Dict, Tuple
import sys
import csv
import os

# Common access-point vendor/model keywords (case-insensitive regexes)
access_points = [
    # =========================================================================
    # CISCO SYSTEMS (Last 10+ Years: Aironet & Catalyst Series)
    # =========================================================================
    # Catalyst 9100 Series (Wi-Fi 6 / 6E / 7 - Modern Enterprise)
    "C9105AXI-E", "C9105AXW-E",
    "C9115AXI-E", "C9115AXE-E",
    "C9120AXI-E", "C9120AXE-E", "C9120AXP-E",
    "C9124AXI-E", "C9124AXE-E", "C9124AXD-E",  # Outdoor
    "C9130AXI-E", "C9130AXE-E",
    "C9136I-E", "C9136E-E",                    # Wi-Fi 6E
    "C9162I-E", "C9164I-E", "C9166I-E",        # Cisco Catalyst / Meraki Hybrid
    "CW9166D1-E",                              # Directional Antenna
    "CW9176I-E", "CW9176E-E",                  # Wi-Fi 7 / Catalyst Ultra

    # Aironet Series (Wi-Fi 5 / 802.11ac Wave 1 & 2 - Legacy Enterprise)
    "AIR-AP1810W-E-K9", "AIR-AP1815I-E-K9", "AIR-AP1815W-E-K9", "AIR-AP1832I-E-K9",
    "AIR-AP1852I-E-K9", "AIR-AP1852E-E-K9",
    "AIR-CAP2702I-E-K9", "AIR-CAP2702E-E-K9",
    "AIR-AP2802I-E-K9", "AIR-AP2802E-E-K9",
    "AIR-CAP3702I-E-K9", "AIR-CAP3702E-E-K9",
    "AIR-AP3802I-E-K9", "AIR-AP3802E-E-K9", "AIR-AP3802P-E-K9",
    "AIR-AP4800-E-K9",
    "AIR-CAP1702I-E-K9", "AIR-AP1562I-E-K9",   # Outdoor legacy

    # Cisco Meraki (Cloud-Managed)
    "MR33", "MR36", "MR42", "MR44", "MR45", "MR46", "MR52", "MR53", "MR56",
    "MR70", "MR74", "MR76", "MR84", "MR86",    # Outdoor Meraki
    "MR57", "MR78", "MR28", "GR10", "GR60",    # Wi-Fi 6E / Go Series

    # Cisco Small Business (WAP Series)
    "WAP121", "WAP150", "WAP321", "WAP371", "WAP551", "WAP561", "WAP571", "WAP581",

    # =========================================================================
    # ARUBA NETWORKS / HPE
    # =========================================================================
    # Wi-Fi 5 & Wi-Fi 6 / 6E / 7 Campus APs
    "AP-205", "AP-215", "AP-225", "AP-303", "AP-305", "AP-315", "AP-325", "AP-335",
    "AP-505", "AP-515", "AP-535", "AP-555",
    "AP-615", "AP-635", "AP-655",              # Wi-Fi 6E
    "AP-735", "AP-755",                        # Wi-Fi 7
    "IAP-205-RW", "IAP-315-RW", "IAP-325-RW",  # Instant AP (No controller needed)

    # =========================================================================
    # UBIQUITI UNIFI
    # =========================================================================
    "UAP-AC-LITE", "UAP-AC-LR", "UAP-AC-PRO", "UAP-AC-EDU", "UAP-AC-HD", "UAP-AC-SHD",
    "U6-Lite", "U6-LongRange", "U6-Pro", "U6-Enterprise", "U6-Mesh",
    "U7-Pro", "U7-Pro-Wall", "U7-Outdoor",     # Wi-Fi 7

    # =========================================================================
    # RUCKUS WIRELESS (COMMSCOPE)
    # =========================================================================
    "ZoneFlex R310", "ZoneFlex R510", "ZoneFlex R610", "ZoneFlex R710", "ZoneFlex R720",
    "R350", "R550", "R650", "R750", "R850",    # Wi-Fi 6
    "R760", "R770",                            # Wi-Fi 6E / Wi-Fi 7
    "T310", "T750",                            # Outdoor

    # =========================================================================
    # TP-LINK (Omada Business Series)
    # =========================================================================
    "EAP225", "EAP245", "EAP265-HD",
    "EAP610", "EAP620-HD", "EAP650", "EAP660-HD", "EAP670",
    "EAP690E-HD",                              # Wi-Fi 6E
    "EAP773", "EAP783",                        # Wi-Fi 7

    # =========================================================================
    # EXTREME NETWORKS / AEROHIVE
    # =========================================================================
    "AP122", "AP130", "AP230", "AP250",        # Legacy Aerohive
    "AP305C", "AP410C", "AP510C", "AP650X",    # ExtremeCloud IQ
    "AP4000", "AP5010",                        # Wi-Fi 6E

    # =========================================================================
    # NETGEAR (Insight / ProSafe Business)
    # =========================================================================
    "WAC510", "WAC540", "WAC720", "WAC730",
    "WAX214", "WAX610", "WAX620", "WAX630",    # Wi-Fi 6 Insight
    "WAX630E",                                 # Wi-Fi 6E

    # =========================================================================
    # FORTINET (FortiAP)
    # =========================================================================
    "FAP-221E", "FAP-321E", "FAP-421E",
    "FAP-231F", "FAP-431F", "FAP-831F",        # Wi-Fi 6
    "FAP-431G", "FAP-433G"                     # Wi-Fi 6E / 7
]


def is_access_point(ap: Dict) -> bool:
    """Return True if the discovered neighbor matches a known AP model and has an IP.

    Matching is case-insensitive and checks whether any `access_points` entry
    appears as a substring in the `ap_name` or `ap_type` fields. Requires a valid IPv4.
    """
    if not ap:
        return False

    name = (ap.get('ap_name') or '')
    atype = (ap.get('ap_type') or '')
    ip = (ap.get('ap_ip') or '').strip()

    # Require a valid IPv4
    if not re.match(r'^\d+\.\d+\.\d+\.\d+$', ip):
        return False

    text = f"{name} {atype}".lower()

    for model in access_points:
        if not model:
            continue
        try:
            if model.lower() in text:
                return True
        except Exception:
            continue

    return False

def parse_interface_output(output: str) -> Dict[str, Dict]:
    """
    Parse 'show interfaces' output and extract relevant information.
    
    Args:
        output: Raw output from show interfaces command
    
    Returns:
        Dictionary of interfaces with their status and counters
    """
    interfaces = {}
    current_interface = None
    
    lines = output.split('\n')
    
    for line in lines:
        line = line.strip()
        
        # Match interface header - more flexible pattern
        interface_match = re.match(r'^(\S+?(?:Ethernet|Gi|Fa|Te|Et)\S*)\s+is\s+(.+?),\s+line\s+protocol\s+is\s+(\w+)', line, re.IGNORECASE)
        if interface_match:
            interface_name = interface_match.group(1)
            admin_status = interface_match.group(2).strip()
            protocol_status = interface_match.group(3).strip()
            
            # Only track physical interfaces
            if any(x in interface_name for x in ['Ethernet', 'Gi', 'Fa', 'Te', 'Et']) and \
               not any(x in interface_name for x in ['Vlan', 'Loopback', 'Port-channel', 'Null']):
                current_interface = interface_name
                interfaces[current_interface] = {
                    'admin_status': admin_status,
                    'protocol_status': protocol_status,
                    'input_packets': 0,
                    'output_packets': 0,
                    'input_errors': 0,
                    'output_errors': 0
                }
                continue
        
        # Parse packet counters only if we have a current interface
        if current_interface and current_interface in interfaces:
            # Match input packets
            input_match = re.search(r'(\d+)\s+packets\s+input', line, re.IGNORECASE)
            if input_match:
                interfaces[current_interface]['input_packets'] = int(input_match.group(1))
            
            # Match output packets
            output_match = re.search(r'(\d+)\s+packets\s+output', line, re.IGNORECASE)
            if output_match:
                interfaces[current_interface]['output_packets'] = int(output_match.group(1))
            
            # Match input errors
            input_error_match = re.search(r'(\d+)\s+input\s+errors', line, re.IGNORECASE)
            if input_error_match:
                interfaces[current_interface]['input_errors'] = int(input_error_match.group(1))
            
            # Match output errors
            output_error_match = re.search(r'(\d+)\s+output\s+errors', line, re.IGNORECASE)
            if output_error_match:
                interfaces[current_interface]['output_errors'] = int(output_error_match.group(1))
    
    return interfaces

def identify_unused_ports(interfaces: Dict[str, Dict], traffic_threshold: int = 100) -> List[str]:
    """
    Identify unused ports based on status and counters.
    
    Args:
        interfaces: Dictionary of interface data
        traffic_threshold: Minimum packet count to consider port as used
    
    Returns:
        List of unused interface names
    """
    unused_ports = []
    
    for interface, data in interfaces.items():
        # Port is unused if line protocol is down AND traffic is below threshold
        protocol_down = data['protocol_status'].lower() == 'down'
        low_traffic = (data['input_packets'] < traffic_threshold and 
                      data['output_packets'] < traffic_threshold)
        
        # Only consider ports that are administratively up
        if data['admin_status'].lower() != 'administratively':
            if protocol_down and low_traffic:
                unused_ports.append(interface)
    
    return unused_ports

def execute_multiple_commands(ssh_client, commands: List[str]) -> Dict[str, str]:
    """
    Execute multiple commands in a single shell session.
    
    Args:
        ssh_client: Active SSH client connection
        commands: List of commands to execute
    
    Returns:
        Dictionary mapping command to its output
    """
    shell = None
    results = {}
    
    try:
        shell = ssh_client.invoke_shell()
        shell.settimeout(30)
        time.sleep(1.5)
        
        # Clear initial output
        time.sleep(1)
        while shell.recv_ready():
            try:
                shell.recv(65535).decode('utf-8', errors='ignore')
            except:
                pass
            time.sleep(0.1)
        
        # Disable paging
        shell.send("terminal length 0\n")
        time.sleep(0.5)
        while shell.recv_ready():
            try:
                shell.recv(65535)
            except:
                pass
        
        # Execute each command
        for command in commands:
            print(f"  Executing: {command}")
            
            # Clear any previous output
            while shell.recv_ready():
                try:
                    shell.recv(65535)
                except:
                    pass
            
            # Send command
            shell.send(command + "\n")
            
            # Wait based on command type
            if "show interfaces" in command and "brief" not in command:
                wait_time = 4.0
            else:
                wait_time = 2.0
            
            time.sleep(wait_time)
            
            # Collect output
            output = ""
            no_data_count = 0
            
            for _ in range(30):
                if shell.recv_ready():
                    try:
                        chunk = shell.recv(65535).decode('utf-8', errors='ignore')
                        output += chunk
                        no_data_count = 0
                        time.sleep(0.2)
                    except Exception as e:
                        print(f"    Warning: Error receiving data: {str(e)}")
                        break
                else:
                    no_data_count += 1
                    if len(output) > 0 and no_data_count > 3:
                        break
                    time.sleep(0.3)
            
            results[command] = output
            print(f"    Received {len(output)} characters")
        
        if shell:
            shell.close()
            
        return results
        
    except Exception as e:
        print(f"    Exception in execute_multiple_commands: {str(e)}")
        import traceback
        print(f"    Traceback: {traceback.format_exc()}")
        if shell:
            try:
                shell.close()
            except:
                pass
        raise

def connect_to_switch(switch_ip: str, username: str, password: str) -> paramiko.SSHClient:
    """
    Establish SSH connection to a Cisco switch.
    
    Args:
        switch_ip: IP address or hostname of the switch
        username: SSH username
        password: SSH password
    
    Returns:
        Connected SSH client or None on failure
    """
    try:
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        ssh_client.connect(
            hostname=switch_ip,
            username=username,
            password=password,
            timeout=10,
            look_for_keys=False,
            allow_agent=False
        )
        
        time.sleep(1)
        
        return ssh_client
    
    except paramiko.AuthenticationException:
        print(f"Authentication failed for {switch_ip}")
        return None
    except paramiko.SSHException as e:
        print(f"SSH error connecting to {switch_ip}: {str(e)}")
        return None
    except Exception as e:
        print(f"Error connecting to {switch_ip}: {str(e)}")
        return None

def save_results_csv(results: List[Dict], output_path: str):
    # Expecting `results` to be a list of AP dicts with keys:
    # 'switch_ip', 'switch_hostname', 'ap_name', 'ap_port', 'ap_type', 'ap_ip'
    unique = []
    seen = set()

    for ap in results:
        # Only keep entries that look like Access Points
        if not is_access_point(ap):
            continue

        # Use IP as primary dedupe key, fallback to name+port
        name = ap.get('ap_name') or ''
        port = ap.get('ap_port') or ''
        key = ap.get('ap_ip') or (name + '|' + port)
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        unique.append(ap)

    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        # Columns: Switch hostname, Switch IP address, Port AP, Type AP, AP IPaddress
        writer.writerow(['Switch hostname', 'Switch IP address', 'Port AP', 'Type AP', 'AP IP address'])

        for ap in unique:
            hostname = ap.get('switch_hostname', '')
            switch_ip = ap.get('switch_ip', '')
            writer.writerow([
                hostname,
                switch_ip,
                ap.get('ap_port', ''),
                ap.get('ap_type', ''),
                ap.get('ap_ip', '')
            ])

    print(f"\nAP results saved to: {output_path}")


def scan_switches(switches: List[Dict], traffic_threshold: int = 100) -> List[Dict]:
    """
    Scan multiple switches for unused ports.
    
    Args:
        switches: List of switch IP addresses or hostnames
        username: SSH username
        password: SSH password
        traffic_threshold: Minimum packet count to consider port as used
    
    Returns:
        List of dictionaries containing results for each switch
    """
    # Return list of discovered APs across all switches
    ap_results: List[Dict] = []

    # helper parsers
    def parse_cdp_neighbors_detail(output: str) -> List[Dict]:
        entries = []
        if not output:
            return entries

        # Split blocks starting with 'Device ID:'
        blocks = re.split(r'(?m)^Device ID:\s*', output)
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            # The first token in this block is the device id line content
            lines = block.splitlines()
            ap_name = lines[0].strip()

            ip_match = re.search(r'IP address:\s*(\d+\.\d+\.\d+\.\d+)', block)
            interface_match = re.search(r'Interface:\s*(\S+),\s*Port ID \([^\)]+\):\s*(\S+)', block)
            platform_match = re.search(r'Platform:\s*([^,\n]+)', block)

            ap_ip = ip_match.group(1) if ip_match else ''
            ap_port = interface_match.group(1) if interface_match else ''
            ap_type = platform_match.group(1).strip() if platform_match else ''

            entries.append({'ap_name': ap_name, 'ap_ip': ap_ip, 'ap_port': ap_port, 'ap_type': ap_type})
        return entries

    def parse_lldp_neighbors_detail(output: str) -> List[Dict]:
        entries = []
        if not output:
            return entries

        # Look for 'System Name:' occurrences and treat nearby lines as a block
        for m in re.finditer(r'System Name:\s*(.+)', output):
            start = m.start()
            # find a blank line after start to limit block
            next_blank = output.find('\n\n', start)
            block = output[start:next_blank] if next_blank != -1 else output[start:]

            ap_name = m.group(1).strip()
            ip_match = re.search(r'(?:Management address:|IP address:)\s*(\d+\.\d+\.\d+\.\d+)', block)
            # Local port is the interface on the switch where the neighbor is seen
            local_match = re.search(r'Local Port:\s*(\S+)', block)
            # Remote (port id) often shows the neighbor's port
            portid_match = re.search(r'Port id:\s*(\S+)', block)
            desc_match = re.search(r'System Description:\s*(.+)', block)

            ap_ip = ip_match.group(1) if ip_match else ''
            ap_port = local_match.group(1) if local_match else (portid_match.group(1) if portid_match else '')
            ap_type = desc_match.group(1).strip() if desc_match else ''

            entries.append({'ap_name': ap_name, 'ap_ip': ap_ip, 'ap_port': ap_port, 'ap_type': ap_type})

        # Fallback: try to parse blocks that mention 'Local Port' without 'System Name'
        if not entries:
            blocks = re.split(r'(?m)^-+\n', output)
            for block in blocks:
                local_match = re.search(r'Local Port:\s*(\S+)', block)
                portid_match = re.search(r'Port id:\s*(\S+)', block)
                ip_match = re.search(r'(?:Management address:|IP address:)\s*(\d+\.\d+\.\d+\.\d+)', block)
                name_match = re.search(r'System Name:\s*(.+)', block)
                desc_match = re.search(r'System Description:\s*(.+)', block)
                if name_match or ip_match:
                    entries.append({
                        'ap_name': (name_match.group(1).strip() if name_match else ''),
                        'ap_ip': ip_match.group(1) if ip_match else '',
                        'ap_port': local_match.group(1) if local_match else (portid_match.group(1) if portid_match else ''),
                        'ap_type': (desc_match.group(1).strip() if desc_match else '')
                    })

        return entries

    for device in switches:
        switch = device.get('ip')
        dev_user = device.get('username')
        dev_pass = device.get('password')

        print(f"\nConnecting to {switch}...")

        ssh_client = connect_to_switch(switch, dev_user, dev_pass)

        if not ssh_client:
            print(f"  Connection failed for {switch}")
            continue

        try:
            # Execute CDP and LLDP detail commands to discover neighbors
            commands = [
                "show running-config | include hostname",
                "show cdp neighbors detail",
                "show lldp neighbors detail"
            ]

            print(f"Executing discovery commands on {switch}...")
            command_results = execute_multiple_commands(ssh_client, commands)

            # Parse hostname from the switch configuration output.
            hostname_output = command_results.get("show running-config | include hostname", "")
            hostname = switch
            
            # Try to extract hostname from the prompt line (format: hostname>)
            # The prompt appears in the output like "SW-Vinicni-3NP>"
            prompt_match = re.search(r'(\S+)>', hostname_output)
            if prompt_match:
                candidate = prompt_match.group(1).strip()
                if candidate and candidate not in ['show', '%', '^']:
                    hostname = candidate
                    print(f"    DEBUG: Found hostname from prompt: '{hostname}'")
            else:
                print(f"    DEBUG: No hostname found, using IP: '{switch}'")

            cdp_output = command_results.get('show cdp neighbors detail', '')
            lldp_output = command_results.get('show lldp neighbors detail', '')

            cdp_entries = parse_cdp_neighbors_detail(cdp_output)
            lldp_entries = parse_lldp_neighbors_detail(lldp_output)

            # Merge entries and add switch context
            for e in cdp_entries + lldp_entries:
                ap_results.append({
                    'switch_ip': switch,
                    'switch_hostname': hostname,
                    'ap_name': e.get('ap_name', ''),
                    'ap_port': e.get('ap_port', ''),
                    'ap_type': e.get('ap_type', ''),
                    'ap_ip': e.get('ap_ip', '')
                })

        except Exception as e:
            import traceback
            print(f"Error during discovery on {switch}: {str(e)}")
            print(traceback.format_exc())
        finally:
            try:
                ssh_client.close()
            except:
                pass
    
    return ap_results

def read_devices_from_csv(file_path: str) -> List[Dict[str, str]]:
    """
    Read devices from a CSV file. Expected columns: ip, username, password

    Args:
        file_path: Path to CSV file

    Returns:
        List of dicts with keys 'ip', 'username', 'password'
    """
    devices = []
    try:
        with open(file_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                ip = (row.get('ip') or row.get('IP') or '').strip()
                username = (row.get('username') or row.get('Username') or '').strip()
                password = (row.get('password') or row.get('Password') or '').strip()

                if not ip:
                    print(f"Skipping row with missing IP: {row}")
                    continue

                devices.append({
                    'ip': ip,
                    'username': username,
                    'password': password
                })
    except FileNotFoundError:
        print(f"CSV file not found: {file_path}")
    except Exception as e:
        print(f"Error reading CSV file {file_path}: {e}")

    return devices

def print_results(results: List[Dict], show_details: bool = False):
    """
    Print formatted results.
    
    Args:
        results: List of switch scan results
        show_details: Whether to show detailed packet counters
    """
    print("\n" + "="*80)
    print("UNUSED PORTS REPORT")
    print("="*80)
    
    for result in results:
        print(f"\nHostname: {result['hostname']} | IP Address: {result['ip_address']}")
        
        if 'error' in result:
            print(f"Error: {result['error']}")
        elif result['unused_ports']:
            print(f"Unused Ports ({len(result['unused_ports'])} out of {result.get('total_interfaces', 0)} total):")
            
            if show_details and 'unused_port_details' in result:
                # Show detailed view with counters
                for port_info in result['unused_port_details']:
                    print(f"  {port_info['interface']:<25} Status: {port_info['status']:<10} "
                          f"In: {port_info['input_packets']:>10} pkts, Out: {port_info['output_packets']:>10} pkts")
            else:
                # Simple list view
                ports = result['unused_ports']
                for i in range(0, len(ports), 4):
                    print("  " + ", ".join(ports[i:i+4]))
        else:
            print("Unused Ports: None found")
    
    print("\n" + "="*80)

def main():
    """
    Main function to run the script.
    """
    # CSV path can be provided as first CLI arg; default to 'devices.csv'
    csv_path = sys.argv[1] if len(sys.argv) > 1 else 'devices.csv'

    # Traffic threshold: ports with less than this many packets are considered unused
    traffic_threshold = 100

    # Show detailed packet counters in output
    show_details = True

    print(f"Loading devices from CSV: {csv_path}")
    devices = read_devices_from_csv(csv_path)
    if not devices:
        print("No devices to scan. Provide a CSV with columns: ip, username, password")
        return

    # Discover access points using CDP/LLDP
    print("Starting AP discovery on switches...")
    ap_results = scan_switches(devices, traffic_threshold)

    print(f"Discovered {len(ap_results)} AP neighbor entries (pre-dedup)")
    if ap_results:
        sample = ap_results[:5]
        for s in sample:
            print(f"  {s.get('switch_hostname','')} -> {s.get('ap_name','')} @ {s.get('ap_port','')} {s.get('ap_ip','')}")

    # Save discovered APs (unique) to CSV next to the script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, 'discovered_aps.csv')
    save_results_csv(ap_results, output_path)

if __name__ == "__main__":
    # Check if paramiko is installed
    try:
        import paramiko
    except ImportError:
        print("Error: paramiko library is required. Install it with: pip install paramiko")
        sys.exit(1)
    
    main()
