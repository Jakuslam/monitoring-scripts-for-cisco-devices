#!/usr/bin/env python3
"""
Script to find unused ports on Cisco switches via SSH.
Identifies ports based on interface status and traffic counters.

Version: 1.5.0
Author: 
"""

import paramiko
import time
import re
from typing import List, Dict, Tuple
import sys
import csv
import os

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
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['ip_address', 'unused_ports'])

        for result in results:
            for port in result.get('unused_ports', []):
                writer.writerow([
                    result.get('ip_address', ''),
                    port
                ])

    print(f"\nResults saved to: {output_path}")


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
    results = []

    # `switches` is now a list of device dicts with keys: ip, username, password
    for device in switches:
        switch = device.get('ip')
        dev_user = device.get('username')
        dev_pass = device.get('password')

        print(f"\nConnecting to {switch}...")

        ssh_client = connect_to_switch(switch, dev_user, dev_pass)

        if not ssh_client:
            results.append({
                'hostname': switch,
                'ip_address': switch,
                'unused_ports': [],
                'unused_port_details': [],
                'error': 'Connection failed'
            })
            continue
        
        try:
            # Execute ALL commands in one session
            commands = [
                "show running-config | include hostname",
                "show interfaces",
                "show ip interface brief"
            ]
            
            print(f"Executing all commands in single session...")
            command_results = execute_multiple_commands(ssh_client, commands)
            
            # Parse hostname
            hostname_output = command_results.get("show running-config | include hostname", "")
            
            hostname = switch
            # Split by newlines and find the line that starts with "hostname"
            lines = hostname_output.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('hostname '):
                    # Extract the hostname value
                    parts = line.split()
                    if len(parts) >= 2:
                        hostname = parts[1]
                        break
            
            # Parse interface data
            interfaces_output = command_results.get("show interfaces", "")
            ip_brief_output = command_results.get("show ip interface brief", "")
            
            # Get IP address
            ip_address = "Unknown"
            if ip_brief_output:
                lines = ip_brief_output.split('\n')
                for line in lines:
                    if 'Vlan' in line or 'Management' in line:
                        ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                        if ip_match:
                            potential_ip = ip_match.group(1)
                            if not potential_ip.startswith('127.') and 'unassigned' not in line.lower():
                                ip_address = potential_ip
                                print(f"  Found IP address: {ip_address} - Hostname: {hostname}")
                                break
                
                if ip_address == "Unknown":
                    ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', ip_brief_output)
                    if ip_match:
                        ip_address = ip_match.group(1)
                        print(f"  Found IP address (fallback): {ip_address} - Hostname: {hostname}")
            
            # Parse interface data
            print(f"  Parsing interface data...")
            interfaces = parse_interface_output(interfaces_output)
            
            print(f"  Found {len(interfaces)} interfaces")
            
            if interfaces:
                sample_interfaces = list(interfaces.keys())[:3]
                print(f"  Sample interfaces: {', '.join(sample_interfaces)}")
            
            # Identify unused ports
            unused_ports = identify_unused_ports(interfaces, traffic_threshold)
            
            # Get detailed info for unused ports
            unused_port_details = []
            for port in unused_ports:
                if port in interfaces:
                    unused_port_details.append({
                        'interface': port,
                        'status': interfaces[port]['protocol_status'],
                        'input_packets': interfaces[port]['input_packets'],
                        'output_packets': interfaces[port]['output_packets']
                    })
            
            result = {
                'hostname': hostname,
                'ip_address': ip_address,
                'unused_ports': unused_ports,
                'unused_port_details': unused_port_details,
                'total_interfaces': len(interfaces)
            }
            
            results.append(result)
            print(f"Found {len(result['unused_ports'])} unused ports out of {result.get('total_interfaces', 0)} total interfaces")
            
        except Exception as e:
            import traceback
            print(f"Error during scan: {str(e)}")
            print(traceback.format_exc())
            results.append({
                'hostname': switch,
                'ip_address': switch,
                'unused_ports': [],
                'unused_port_details': [],
                'error': str(e)
            })
        finally:
            ssh_client.close()
    
    return results

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

    # Scan switches (per-device credentials)
    print("Starting switch scan...")
    print(f"Traffic threshold: {traffic_threshold} packets")
    results = scan_switches(devices, traffic_threshold)

    # Display results
    print_results(results, show_details)

    #save results to CSV
    # Display results
    #print_results(results, show_details)

    # Save to CSV next to the script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, 'unused_ports.csv')
    save_results_csv(results, output_path)

if __name__ == "__main__":
    # Check if paramiko is installed
    try:
        import paramiko
    except ImportError:
        print("Error: paramiko library is required. Install it with: pip install paramiko")
        sys.exit(1)
    
    main()
