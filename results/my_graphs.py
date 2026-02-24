import os, re, math
import pandas as pd
import matplotlib.pyplot as plt

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPFS = ["spgwu", "ebpf_xdp", "dpdk"]
RATES = [10, 50, 100, 200, 500]
DIRS = ["ul", "dl"]
PING_SIZES = [64, 128, 256, 512, 1024, 1380]  
SCENARIOS = ["", "optimise"]  # baseline et optimisé

def path(upf, scenario, *parts):#permet de preciser le chemin des logs 
    if scenario:
        return os.path.join(BASE_DIR, upf, scenario, *parts)
    return os.path.join(BASE_DIR, upf, *parts)

def parse_iperf_file(path):
    """etant donné la difference des logs iperfs, il est necessiare de les formatter"""
    txt = open(path, "r", errors="ignore").read()

    bw_m = re.findall(r'(\d+\.?\d*)\s+Mbits/sec', txt)
    bw = float(bw_m[-1]) if bw_m else None
    loss_m = re.findall(r'(\d+)\s*/\s*(\d+)\s*\(([\d\.]+)%\)', txt)
    if loss_m:
        lost, total, pct = loss_m[-1]
        loss = float(pct)
        return bw, loss

    # si  % absent
    loss_m2 = re.findall(r'(\d+)\s*/\s*(\d+)', txt)
    loss = None
    if loss_m2:
        lost, total = map(int, loss_m2[-1])
        loss = (lost / total * 100) if total else 0.0
    return bw, loss

def parse_ping_file(path):#formatage log des pings
    
    txt = open(path, "r", errors="ignore").read()
    m = re.search(r'rtt min/avg/max/mdev = [\d\.]+/([\d\.]+)/[\d\.]+/([\d\.]+)', txt)
    if m:
        return float(m.group(1)), float(m.group(2))

    times = re.findall(r'time[=<]([\d\.]+)\s*ms', txt)
    if not times:
        return None, None

    vals = [float(x) for x in times]
    avg = sum(vals) / len(vals)
    var = sum((x - avg) ** 2 for x in vals) / len(vals)
    jitter = math.sqrt(var)
    return avg, jitter

def parse_cpu_file(path, upf):
    """ pour dpdk les logs cpu ont été obtenu grace à ps contrairement aux autres => grace à docker stats
    Retourne la moyenne de l'usage cpu durant l'execution.
    """
    txt = open(path, "r", errors="ignore").read().strip().splitlines()
    if not txt:
        return None

    # dpdk: timestamp cpu mem
    dpdk_vals = []
    for line in txt:
        parts = line.split()
        if len(parts) == 3 and parts[0].isdigit():
            try:
                dpdk_vals.append(float(parts[1]))
            except:
                pass
    if dpdk_vals:
        return sum(dpdk_vals) / len(dpdk_vals)

    # docker stats
    cpu_vals = []
    for line in txt:
        m = re.search(r'(\d+\.?\d*)\s*%', line)
        if m:
            cpu_vals.append(float(m.group(1)))
    if cpu_vals:
        return sum(cpu_vals) / len(cpu_vals)
    return None

def plot_lines(df, x, y, hue, title, xlabel, ylabel, out):
    plt.figure(figsize=(8,5))
    for key in sorted(df[hue].unique()):
        sub = df[df[hue] == key].sort_values(x)
        if sub.empty:
            continue
        plt.plot(sub[x], sub[y], marker="o", label=str(key))
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out, dpi=200)
    print("Saved:", out)

all_iperf = []
all_ping = []
all_cpu = []

for scenario in SCENARIOS:
    scen_label = "BASELINE" if scenario == "" else scenario.upper()

    # pour les données iperf
    for upf in UPFS:
        for d in DIRS:
            for r in RATES:
                f = path(upf, scenario, "udp", f"{d}_{r}m.txt")
                if not os.path.exists(f):
                    continue
                bw, loss = parse_iperf_file(f)
                if bw is None:
                    continue
                all_iperf.append({"SCENARIO": scen_label,"UPF": upf.upper(),"DIR": d.upper(),"TARGET": r,"MEASURED": bw,"LOSS": loss})

    # pings
    for upf in UPFS:
        for sz in PING_SIZES:
            f = path(upf, scenario, "ping", f"ping_ue_dn_{sz}.txt")
            if not os.path.exists(f):
                continue
            rtt, jit = parse_ping_file(f)
            if rtt is None:
                continue
            all_ping.append({"SCENARIO": scen_label,"UPF": upf.upper(),"SIZE": sz,"RTT": rtt,"JITTER": jit})

    # CPU
    for upf in UPFS:
        for d in DIRS:
            for r in RATES:
                f = path(upf, scenario, "cpu", f"{d}_{r}.txt")
                if not os.path.exists(f):
                    continue
                cpu = parse_cpu_file(f, upf)
                if cpu is None:
                    continue
                all_cpu.append({"SCENARIO": scen_label,"UPF": upf.upper(),"DIR": d.upper(),"TARGET": r,"CPU": cpu})

df_iperf = pd.DataFrame(all_iperf)
df_ping = pd.DataFrame(all_ping)
df_cpu = pd.DataFrame(all_cpu)

print("iperf points:", len(df_iperf))
print("ping points:", len(df_ping))
print("cpu points:", len(df_cpu))

# pour chaque scenario et direction (iperf)
for scen in df_iperf["SCENARIO"].unique():
    sub = df_iperf[df_iperf["SCENARIO"] == scen]
    for direction in ["DL", "UL"]:
        sdir = sub[sub["DIR"] == direction]
        if sdir.empty:
            continue
        plot_lines(sdir, "TARGET", "MEASURED", "UPF",f"{scen} - Throughput vs Target ({direction})","Offered load (Mbps)", "Measured throughput (Mbits/s)",f"throughput_{direction.lower()}_{scen.lower()}.png")
        plot_lines(sdir, "TARGET", "LOSS", "UPF",f"{scen} - UDP Loss vs Target ({direction})","Offered load (Mbps)", "Loss (%)",f"loss_{direction.lower()}_{scen.lower()}.png")

# RTT vs packet size (par scenario) 
for scen in df_ping["SCENARIO"].unique():
    sub = df_ping[df_ping["SCENARIO"] == scen]
    if sub.empty:
        continue
    plot_lines(sub, "SIZE", "RTT", "UPF",f"{scen} - RTT vs Packet size (UE→DN)","ICMP payload size (bytes)", "RTT avg (ms)",f"rtt_vs_size_{scen.lower()}.png")
    plot_lines(sub, "SIZE", "JITTER", "UPF",f"{scen} - Jitter vs Packet size (UE→DN)","ICMP payload size (bytes)", "Jitter (ms)",f"jitter_vs_size_{scen.lower()}.png"
    )

# CPU vs load 
if not df_cpu.empty:
    for scen in df_cpu["SCENARIO"].unique():
        sub = df_cpu[df_cpu["SCENARIO"] == scen]
        for direction in ["DL", "UL"]:
            sdir = sub[sub["DIR"] == direction]
            if sdir.empty:
                continue
            plot_lines(sdir, "TARGET", "CPU", "UPF",f"{scen} - CPU vs Target ({direction})","Offered load (Mbps)", "CPU (%)",f"cpu_{direction.lower()}_{scen.lower()}.png")

plt.show()