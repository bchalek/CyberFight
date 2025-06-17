#!/bin/bash
# sudo apt install inotify-tools

PCAP_DIR="/opt/logs/pcaps"
CSV_DIR="/opt/logs/tcpdump"
PCAP_PREFIX="eth2_dump"

# Create necessary directories
mkdir -p "$PCAP_DIR" "$CSV_DIR"

# Start tshark in background to dump rotating pcaps
tshark -i eth2 -b duration:120 -b files:10 -w "$PCAP_DIR/$PCAP_PREFIX" &
TSHARK_PID=$!

# Require inotifywait to monitor file changes
command -v inotifywait >/dev/null 2>&1 || {
    echo >&2 "inotifywait is required but not installed. Install 'inotify-tools' first."; exit 1;
}

# Monitor pcap dir and convert new files to CSV
inotifywait -m -e close_write --format '%w%f' "$PCAP_DIR" | while read NEWFILE; do
        echo $NEWFILE
        BASENAME=$(basename "$NEWFILE" .pcap)
        CSVFILE="$CSV_DIR/${BASENAME}.csv"
        echo "src_ip,dst_ip,src_port,dst_port,hex_payload,info" > "$CSVFILE"

        tshark -r "$NEWFILE" -T fields \
          -e ip.src \
          -e ip.dst \
          -e tcp.srcport \
          -e tcp.dstport \
          -e data.data \
          -e _ws.col.Info \
          -E separator=, -E quote=d -E header=n \
          >> "$CSVFILE"

        # Keep only last 10 CSVs
        ls -1t "$CSV_DIR"/*.csv | tail -n +11 | xargs -r rm --
done &

# Wait for tshark to finish (likely only when stopped)
wait $TSHARK_PID
