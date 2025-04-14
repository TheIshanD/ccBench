import os
import numpy as np

# Constants
BYTES_PER_PKT = 1500.0  # Packet size in bytes
BITS_IN_BYTE = 8.0  # Bits per byte
MILLISECONDS_IN_SECOND = 1000  # Number of milliseconds in a second

def convert_mahimahi_to_bandwidth(trace_file, output_file):
    """Convert a Mahimahi trace file to a time-bandwidth trace file."""
    print(f"Processing {trace_file} -> {output_file}")
    
    with open(trace_file, 'r') as mf:
        packet_times = []
        for line in mf:
            try:
                packet_times.append(int(line.strip()))
            except ValueError:
                continue  # Ignore lines that cannot be converted into an integer
            
    # Compute bandwidth per millisecond
    min_time = min(packet_times)
    max_time = max(packet_times)
    trace_duration = max_time - min_time + 1

    bandwidth_trace = np.zeros(trace_duration, dtype=int)

    for t in packet_times:
        bandwidth_trace[t - min_time] += 1  # Count packets per millisecond

    # Convert to Mbps
    with open(output_file, 'w') as out_f:
        for i in range(trace_duration):
            bandwidth_mbps = (bandwidth_trace[i] * BYTES_PER_PKT * BITS_IN_BYTE * MILLISECONDS_IN_SECOND) / 1e6
            out_f.write(f"{i} {bandwidth_mbps:.6f}\n")  # Time in ms, Bandwidth in Mbps

    print(f"Converted {trace_file} -> {output_file}")

# Directory for Mahimahi traces
TRACE_DIR = "/home/ishandas/Desktop/ccBench/traces"
OUTPUT_DIR = "/home/ishandas/Desktop/ccBench/traces_bw"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# Process all Mahimahi trace files in the directory
for trace_file in os.listdir(TRACE_DIR):
    input_path = os.path.join(TRACE_DIR, trace_file)
    output_path = os.path.join(OUTPUT_DIR, f"{trace_file}_bw")
    
    convert_mahimahi_to_bandwidth(input_path, output_path)
