import paramiko
import yaml
import concurrent.futures
import argparse
import time
import os
import subprocess

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Manage ccbench traces on remote nodes")
parser.add_argument("--collect", action="store_true", help="SCP zipped traces to target path")
parser.add_argument("--target-path", type=str, default="mll:/datastor1/ishandas/ccbench-zips", help="Path to collect zipped traces")
args = parser.parse_args()

# Load server configuration
CONFIG_FILE = "config.yaml"
with open(CONFIG_FILE, "r") as file:
    config = yaml.safe_load(file)

servers = config["servers"]
username = "ishandas"
trace_dir = "/mydata/ccbench-traces"
zip_path = "/mydata/ccbench-traces.zip"
tmux_session = "ziptrace"


def check_traces_and_launch_zip(server, idx):
    hostname = server["hostname"]
    print(f"[{hostname}] Connecting to check traces and launch zip in tmux...")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        client.connect(hostname, username=username)

        total_cmd = f"ls {trace_dir} | wc -l"
        real_cmd = f"ls {trace_dir} | grep real | wc -l"

        stdin, stdout, _ = client.exec_command(total_cmd)
        total_count = stdout.read().decode().strip()

        stdin, stdout, _ = client.exec_command(real_cmd)
        real_count = stdout.read().decode().strip()

        print(f"[{hostname}] Trace file count: TOTAL={total_count}, REAL={real_count}")

        if args.collect:
            # Wait a bit in case zip just started (you may want to poll in production)
            print(f"[{hostname}] Waiting for possible zip file to appear...")
            time.sleep(3)

            # Try to check zip file size
            stdin, stdout, stderr = client.exec_command(f"du -h {zip_path} | cut -f1")
            size_output = stdout.read().decode().strip()
            print(f"[{hostname}] Zip size: {size_output or 'Not ready yet'}")

            local_dest = f"{args.target_path}/ccbench-traces-node{idx}.zip"
            remote_file = f"{username}@{hostname}:{zip_path}"
            scp_cmd = [
                "scp",
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null", 
                remote_file, 
                local_dest]

            print(f"[{hostname}] Attempting SCP to {local_dest}")
            try:
                subprocess.run(scp_cmd, check=True)
                print(f"[{hostname}] SCP complete")
            except subprocess.CalledProcessError:
                print(f"[{hostname}] SCP failed: Zip might not be ready yet")
        else:
            tmux_commands = [
                f"tmux kill-session -t {tmux_session} || true",
                f"tmux new-session -d -s {tmux_session}",
                f"tmux send-keys -t {tmux_session} 'cd /mydata' C-m",
                f"tmux send-keys -t {tmux_session} 'zip -rq ccbench-traces.zip ccbench-traces' C-m"
            ]

            for cmd in tmux_commands:
                print(f"[{hostname}] TMUX: {cmd}")
                client.exec_command(cmd)
                time.sleep(0.3)
                
            print(f"[{hostname}] Zip command launched in tmux.")

    except Exception as e:
        print(f"[{hostname}] ERROR: {e}")
    finally:
        client.close()


if __name__ == "__main__":
    # with concurrent.futures.ThreadPoolExecutor(max_workers=len(servers)) as executor:
    #     futures = {
    #         executor.submit(check_traces_and_launch_zip, server, idx): server["hostname"]
    #         for idx, server in enumerate(servers)
    #     }
    #     for future in concurrent.futures.as_completed(futures):
    #         hostname = futures[future]
    #         try:
    #             future.result()
    #         except Exception as e:
    #             print(f"[{hostname}] FAILED: {e}")
                
    for idx, server in enumerate(servers):
        check_traces_and_launch_zip(server, idx)

    print("All trace operations completed.")
