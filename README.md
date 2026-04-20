# SDN Topology Change Detector

An SDN-based topology monitoring system built using **Mininet** and **Ryu OpenFlow Controller**.  
Detects switch/link events in real time, updates the topology map, displays changes, and logs all updates.

---

## Problem Statement

In traditional networks, topology changes (link failures, switch disconnections) are hard to detect and respond to in real time. This project implements an SDN solution where a centralized Ryu controller dynamically monitors the network topology. When any switch or link event occurs, the controller instantly detects it, updates its internal topology map, displays the change, and logs it with a timestamp.

---

## Project Structure

```
sdn-topology-detector/
├── controller/
│   └── topology_detector.py   # Ryu controller — detects topology events
├── topology/
│   └── topology.py            # Mininet topology — 3 switches, 4 hosts
├── logs/
│   └── topology_changes.log   # Auto-generated event log
└── README.md
```

---

## Network Topology

```
h1 - s1 - s2 - s3 - h4
h2 /       |
          h3
```

- 3 switches: s1, s2, s3
- 4 hosts: h1 (10.0.0.1), h2 (10.0.0.2), h3 (10.0.0.3), h4 (10.0.0.4)
- Controller: Ryu (OpenFlow 1.3) on port 6653

---

## Requirements

- Ubuntu 20.04 / 22.04
- Python 3.x
- Mininet
- Ryu SDN Framework
- Open vSwitch (OVS)

Install dependencies:
```bash
sudo apt update
sudo apt install mininet openvswitch-switch -y
pip install ryu
```

---

## Setup & Execution

### Step 1 — Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/sdn-topology-detector.git
cd sdn-topology-detector
```

### Step 2 — Terminal 1: Start Ryu Controller
```bash
ryu-manager controller/topology_detector.py --observe-links --ofp-tcp-listen-port 6653
```

Wait for:
```
=== Topology Detector Started ===
```

### Step 3 — Terminal 2: Start Mininet Topology
```bash
sudo python3 topology/topology.py
```

Wait for `mininet>` prompt.

---

## Testing Scenarios

### Scenario 1 — Normal Connectivity
```
mininet> pingall
```
Expected: `0% dropped (12/12 received)`

### Scenario 2 — Link Failure Detection
```
mininet> link s1 s2 down
mininet> h1 ping -c3 h3
```
Expected: Controller logs `[LINK DOWN]`, ping shows 100% packet loss.

### Scenario 3 — Link Recovery
```
mininet> link s1 s2 up
mininet> h1 ping -c3 h3
```
Expected: Controller logs `[LINK UP]`, ping resumes successfully.

### View Flow Tables
```
mininet> sh ovs-ofctl dump-flows s1
mininet> sh ovs-ofctl dump-flows s2
mininet> sh ovs-ofctl dump-flows s3
```

### Bandwidth Test
```
mininet> h2 iperf -s &
mininet> h1 iperf -c 10.0.0.2 -t 5
```

---

## Expected Output

### Ryu Controller (Terminal 1)
```
=== Topology Detector Started ===

[SWITCH UP] 1 ports=[1, 2, 3] (08:25:20)
[SWITCH UP] 2 ports=[1, 2, 3] (08:25:20)
[SWITCH UP] 3 ports=[1, 2] (08:25:20)

--- TOPOLOGY ---
Switches: [1, 2, 3]
Link: 1 <--> 2
Link: 2 <--> 1
Link: 2 <--> 3
Link: 3 <--> 2
----------------

[LINK DOWN] 1 <--> 2 (08:28:32)
--- TOPOLOGY ---
Switches: [1, 2, 3]
Link: 2 <--> 3
Link: 3 <--> 2
----------------

[LINK UP] 1 <--> 2 (08:30:10)
--- TOPOLOGY ---
Switches: [1, 2, 3]
Link: 1 <--> 2
Link: 2 <--> 1
Link: 2 <--> 3
Link: 3 <--> 2
----------------
```

### Log File
All events are saved to `logs/topology_changes.log` with timestamps.

---

## How It Works

| Event | Handler | Action |
|---|---|---|
| Switch connects | `EventSwitchEnter` | Add to topology map, log |
| Switch disconnects | `EventSwitchLeave` | Remove from map, prune links, log |
| Link comes up | `EventLinkAdd` | Update link map, log |
| Link goes down | `EventLinkDelete` | Remove link, log |
| Port state change | `EventOFPPortStatus` | Log port UP/DOWN |
| Unknown packet | `EventOFPPacketIn` | Learn MAC, install flow rule |

---

## SDN Concepts Demonstrated

- **OpenFlow 1.3** match-action flow rules
- **Table-miss rule** (priority=0) → sends unknown packets to controller
- **MAC learning** → controller learns host locations dynamically
- **Flow installation** → exact match rules installed per host pair
- **LLDP** → used by Ryu to discover and monitor links
- **Topology events** → real-time detection of network changes

---

## Evaluation Coverage

| Criteria | Implementation |
|---|---|
| Problem Understanding & Setup | Mininet + Ryu running with custom topology |
| SDN Logic & Flow Rule Implementation | OpenFlow match-action rules, MAC learning, table-miss |
| Functional Correctness | pingall, link down/up scenarios demonstrated |
| Performance Observation & Analysis | Flow tables, packet counts, iperf bandwidth test |
| Explanation & Validation | Logs, screenshots, topology map updates |
