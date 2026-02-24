DN_IP=192.168.70.135
for L in 64 128 256 512 1024 1400; do
  for B in 50M 100M 200M 500M 1G; do
    docker exec -i oai-ext-dn sh -lc 'iperf3 -s -1' >/dev/null 2>&1 &
    sleep 1
    timeout 47 docker exec -i ue ping -i 0.2 $DN_IP > "logs/spgwu/ping_l${L}_b${B}.txt" & #ping en parallele 
    PING_PID=$!
    #conso CPU
    (sleep 10 && docker stats --no-stream --format "{{.CPUPerc}};{{.MemUsage}}" oai-spgwu >> "logs/spgwu/dockerstats_oai-spgwu_l${L}_b${B}.txt"
     sleep 15 && docker stats --no-stream --format "{{.CPUPerc}};{{.MemUsage}}" oai-spgwu >> "logs/spgwu/dockerstats_oai-spgwu_l${L}_b${B}.txt"
     sleep 15 && docker stats --no-stream --format "{{.CPUPerc}};{{.MemUsage}}" oai-spgwu >> "logs/spgwu/dockerstats_oai-spgwu_l${L}_b${B}.txt") &
    STATS_PID=$!
    docker exec -it ue sh -lc "iperf3 -c $DN_IP -u -t 45 -l $L -b $B --get-server-output" \
      | tee "logs/spgwu/iperf_l${L}_b${B}.txt"
    wait $PING_PID $STATS_PID
    sleep 2
  done
done

