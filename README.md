# MAC Address Table Retrieval Tool

This project is a Python tool for retrieving MAC address tables from network switches via SSH. It reads switch information and credentials from specified files, connects to each switch, and fetches the MAC address tables.

## Features

- Reads switch groups and their credentials from a file.
- Reads switch IP addresses from another file.
- Prompts the user to enter login credentials for each switch group.
- Connects to each switch via SSH to retrieve the MAC address table.
- Merges the MAC address tables from all switches into a single table.
- Saves the merged MAC address table to a file.

## Requirements

- Python 3.x
- `paramiko` library
- `pandas` library

## Usage
1. Prepare the switch groups file switch_groups.txt with the following tab-separated format:

group\thint
1\tHint for group 1
2\tHint for group 2

2. Prepare the switch IPs file switch_ips.txt with the following tab-separated format:

ip\tswt\tgroup
192.168.1.1\tswitch1\t1
192.168.1.2\tswitch2\t2

3. Run the script:
python address_finder.py
The script will prompt for login credentials for each switch group.

4. The MAC address tables will be retrieved and merged, and the result will be saved to a timestamped file.
