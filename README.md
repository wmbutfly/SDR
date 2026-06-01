# UDP Listener Tool

A simple Python tool for listening to UDP packets and displaying them in console or saving to pcap files for Wireshark analysis.

## Installation

```bash
pip install scapy
```

**Note:** On Windows, run as Administrator for packet capture permissions.

## Usage

### Console Mode (default)

```bash
python udp_listener.py
python udp_listener.py --ip 192.168.1.100 --port 8890
```

### PCAP Mode

```bash
python udp_listener.py --mode pcap --output capture.pcap
python udp_listener.py --mode pcap --output capture.pcap --ip 192.168.1.100 --port 8890
```

## Command Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--ip` | 192.168.1.100 | IP address to bind |
| `--port` | 8890 | Port to listen on |
| `--mode` | console | Output mode: `console` or `pcap` |
| `--output` | capture.pcap | Output pcap file path |

## Output Format (Console Mode)

```
[2024-01-15 10:30:45.123] 192.168.1.50:54321 -> 192.168.1.100:8890 | len=128 | 01 02 03 04...
```

## Requirements

- Python 3.6+
- scapy

## License

MIT