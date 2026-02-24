# OAI 5G URLLC Network Evaluation
## Overview

This repository provides the experimental framework used for the evaluation of Ultra-Reliable Low-Latency Communication (URLLC) performance in a fully virtualized 5G Standalone (SA) architecture based on OpenAirInterface (OAI).

The objective of this project is to compare different 5G User Plane Function (UPF) implementations under URLLC-oriented traffic conditions. Three packet processing paradigms are evaluated:

- SPGWU (Linux kernel-based implementation)
- VPP/DPDK (user-space polling architecture)
- eBPF/XDP (in-kernel programmable data plane)

All experiments are conducted in a Docker-based environment using OAI 5G Core and UERANSIM for gNB and UE emulation.

The repository includes deployment scripts, configuration files, traffic generation procedures, and performance measurement tools used in the associated academic report.

---

## Prerequisites

### System Requirements

All components run on a single host machine.

- Operating System: Ubuntu 22.04 LTS
- CPU: Multi-core x86_64 processor (tested on Intel Core i7-11700K)
- RAM: Minimum 16 GB (32 GB recommended)
- Docker & Docker Compose
- Python 3 (for result parsing and graph generation)

### Software Components

- OpenAirInterface 5G Core (containerized deployment)
- UERANSIM (gNB and UE simulation)
- iperf3 (traffic generation)
- Standard Linux networking utilities (ping, iproute2)

---

## Architecture

The experimental setup consists of:

- Simulated UE (UERANSIM)
- Simulated gNB (UERANSIM)
- OAI 5G Core Network (AMF, SMF, UPF, NRF, UDM, AUSF)
- Interchangeable UPF implementations
- External Data Network (DN)
- Fully virtualized Docker networking environment

No physical radio hardware or external 5G modem is required.

---

## Scope and Limitations

This framework is intended for controlled comparative evaluation of software-based UPF implementations. 

All experiments are conducted in a virtualized single-host environment without hardware offloading (e.g., SR-IOV, RSS, checksum offloading). Therefore, results should be interpreted within the constraints of software-only packet processing.

### Docker Installation

Update:
```
sudo apt-get update
```
Install Docker:
```
sudo apt install docker.io docker-compose-plugin
```
Enable & start Docker with the following commands:
```
sudo systemctl enable docker
```

```
sudo systemctl start docker
```

### Docker Compose Installation:

Download Docker Compose from its official GitHub repository
```
sudo curl -L "https://github.com/docker/compose/releases/download/v2.0.1/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
```
Apply executable permissions to the binary:
```
sudo chmod +x /usr/local/bin/docker-compose
```

## System Optimizations
The following optimizations were applied to improve packet processing stability in a virtualized single-host environment.

- Enable Governor CPU and adjust network buffers:
```
for ((i=0;i<$(nproc);i++)); do sudo cpufreq-set -c $i -r -g performance; done
sudo sysctl -w net.core.wmem_max=62500000
sudo sysctl -w net.core.rmem_max=62500000
sudo sysctl -w net.core.wmem_default=62500000
sudo sysctl -w net.core.rmem_default=62500000
sudo ethtool -G enp1s0f0 tx 4096 rx 4096
```

Docker Resource Considerations

All 5G components (UE, gNB, Core Network) run on a single host machine.
Ensure that:

No heavy background applications are running

CPU isolation or task pinning may be used if required

Sufficient RAM is available



## UPF Solutions Evaluation

This framework enables the deployment and comparative evaluation of three different UPF implementations:

- SPGWU (Kernel-based, interrupt-driven model)
- VPP/DPDK (User-space polling architecture)
- eBPF/XDP (In-kernel programmable data plane)

Each UPF deployment includes:

- A dedicated Core Network configuration
- A corresponding UERANSIM deployment (gNB + UE)
- Deployment and teardown scripts for reproducibility

To ensure fair comparison, only one UPF implementation is active at a time.  
The entire Core Network stack is redeployed before switching to another UPF in order to avoid configuration persistence or interference.

---

### SPGWU-UPF

The OpenAirInterface `oai-spgwu-tiny` implementation is a kernel-based UPF relying on the traditional Linux networking stack.  
It follows an interrupt-driven packet processing model and represents the baseline architecture in this study.

#### Deployment

Deploy the 5G Core Network with SPGWU:

```bash
bash scripts/deploy-spgwu-based-core.sh
```

Deploy the simulated RAN (UERANSIM):

```bash
bash scripts/deploy-ueransim-spgwu.sh
```

After execution, verify that:

All containers are running and healthy:
```bash
docker ps
```

The UE has successfully established a PDU session (check for uesimtun0 interface):
```bash
docker logs ue
```
Teardown

To stop and remove the deployment:
```bash
bash scripts/destroy-spgwu-based-core.sh
bash scripts/destroy-spgwu-ueransim.sh
```

### VPP-UPF (DPDK-Based Architecture)

The VPP-based UPF relies on the Vector Packet Processing (VPP) framework combined with DPDK (Data Plane Development Kit).  
Unlike traditional interrupt-driven packet processing, VPP follows a **poll-mode architecture**, where CPU cores continuously poll network queues instead of reacting to hardware interrupts.

This model provides several advantages:

- Reduced context-switch overhead
- Improved cache locality
- Batch (vectorized) packet processing
- Better scalability under high packet rates

VPP processes packets in batches using SIMD (Single Instruction, Multiple Data) instructions, enabling multiple packets to be handled per CPU cycle.  
DPDK allows direct user-space access to network interfaces, bypassing the traditional Linux kernel networking stack.

In this study, the VPP-UPF represents the **user-space polling paradigm**, serving as the high-performance reference architecture.

> Note: In our experimental setup, VPP runs inside a Docker container without SR-IOV or hardware offloading. Therefore, performance reflects software-only packet processing capabilities rather than near line-rate NIC acceleration.

---

#### Deployment

Deploy the 5G Core Network with VPP-UPF:

```bash
bash scripts/deploy-vpp-based-core.sh
```
* Deploy 5G RAN based on UERANSIM:
```
sudo bash scripts/deploy-ueransim-vpp.sh
```

When both commands are executed, your VPP-based deployment should be working properly. 

- You may check the status of your containers with:
```
sudo docker ps -a
```
-The UE has successfully established a PDU session (presence of uesimtun0)
```bash
docker logs ue
```

- You may check the logs of each core network function by executing the following command (generates .txt log files):
```
bash scripts/generate-logs-vpp.sh
```
- You can destroy the whole architecture by executing the following commands:
```
sudo bash scripts/destroy-vpp-based-core.sh
```
```
sudo bash scripts/destroy-vpp-ueransim.sh
```
### eBPF/XDP-UPF (In-Kernel Programmable Data Plane)

The eBPF-based UPF relies on eBPF (extended Berkeley Packet Filter) and XDP (eXpress Data Path) to process packets directly inside the Linux kernel.

Unlike traditional kernel-based forwarding (SPGWU) or user-space polling (VPP/DPDK), eBPF enables programmable packet processing at an earlier stage in the networking stack.  
With XDP, packets can be intercepted at the driver level before the creation of full kernel socket buffers (`sk_buff`), reducing processing overhead.

This architecture represents a **programmable in-kernel data plane**, combining flexibility and performance.

In this project, the UPF operates in **XDP Generic mode**:

- Packets are intercepted after partial traversal of the Linux networking stack.
- No hardware offloading or Native XDP driver support is used.
- Processing remains fully software-based.

Because Generic mode does not attach directly to the NIC driver, it introduces additional overhead compared to Native XDP. As a result, the observed performance reflects the limitations of in-kernel programmable processing in a virtualized environment.

> Performance may vary depending on CPU architecture, kernel version, and driver support.

---

#### Deployment

Deploy the 5G Core Network with eBPF/XDP-UPF:

```bash
bash scripts/deploy-ebpf-based-core.sh
```
* Deploy 5G RAN based on UERANSIM:
```
sudo bash scripts/deploy-ueransim-ebpf.sh
```

When both commands are executed, your EBPF-based deployment should be working properly. 

- You may check the status of your containers with:
```
sudo docker ps -a
docker logs ue
```
- You may check the logs of each core network function by executing the following command (generates .txt log files):
```
bash scripts/generate-logs-ebpf.sh
```
- You can destroy the whole architecture by executing the following commands:
```
sudo bash scripts/destroy-ebpf-based-core.sh
```
```
sudo bash scripts/destroy-ebpf-ueransim.sh

```
## RAN Configuration (UERANSIM-Based Simulation)

In this project, the Radio Access Network is fully simulated using UERANSIM.  
No physical gNB, USRP device, or real radio transmission is involved.

The simulated RAN consists of:

- A virtual gNB (UERANSIM container)
- A virtual UE (UERANSIM container)

The gNB communicates with the OAI 5G Core over standard N2 and N3 interfaces within a Docker network.

---

### UERANSIM Configuration

The configuration files are located in the `demo/` directory and include:

- `gnb.yaml`
- `ue.yaml`

Key parameters:

- PLMN (MCC/MNC)
- S-NSSAI (Slice configuration)
- SUPI/IMSI consistency with UDM database
- AMF IP address
- UE tunnel interface (uesimtun0)

---

### Important Notes

- Since no physical radio layer is used, parameters such as TDD periodicity, MIMO configuration, and frame structure are not applicable.
- Latency measurements therefore reflect:
  - Core Network processing
  - Container networking overhead
  - Software packet processing characteristics

They do not include physical-layer transmission delay.

---


 ## Traffic Generation and Measurement

All performance measurements were conducted using standard Linux networking tools.

### Latency Measurement

Round-Trip Time (RTT) was measured using ICMP echo requests:

```bash
docker exec -it ue ping -I uesimtun0 <DN_IP> -c 50
```
Traffic was explicitly bound to the UE tunnel interface (uesimtun0) to ensure full traversal of the 5G user plane (GTP-U encapsulation and decapsulation).

Throughput and Packet Loss

UDP traffic was generated using iperf3:

Uplink:
```bash
docker exec -it ue iperf3 -c <DN_IP> -u -b <rate> -t 30 -B <UE_TUN_IP>
```
Downlink: 
```bash
docker exec -it ue iperf3 -c <DN_IP> -u -b <rate> -t 30 -B <UE_TUN_IP>
```
