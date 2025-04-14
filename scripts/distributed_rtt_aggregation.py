import paramiko
import yaml
import concurrent.futures
import argparse
import time
import os
import subprocess

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Launch or collect dataset from remote nodes")
parser.add_argument("--collect", action="store_true", help="Collect dataset files via scp")
parser.add_argument("--target-path", type=str, default="mll:/datastor1/ishandas/datasets", help="Remote path to store collected files")
args = parser.parse_args()

# Load server configuration
CONFIG_FILE = "config.yaml"
with open(CONFIG_FILE, "r") as file:
    config = yaml.safe_load(file)

servers = config["servers"]
username = "ishandas"
dataset_path_synthetic = "/mydata/ccbench-dataset/6col-rtt-20_synthetic.p"
dataset_path_real = "/mydata/ccbench-dataset/6col-rtt-20_real.p"

def scp_datasetgen_script(server):
    hostname = server["hostname"]
    local_path = "/Users/ishandas/Desktop/ccBench/pantheon-modified/src/experiments/palantir_datasetgen_rtt.py"
    remote_path = f"{username}@{hostname}:~/ccBench/pantheon-modified/src/experiments/"

    print(f"Copying {local_path} to {remote_path} ...")
    scp_cmd = f"scp {local_path} {remote_path}"
    status = os.system(scp_cmd)

    if status != 0:
        print(f"Failed to copy to {hostname}")
    else:
        print(f"Successfully copied to {hostname}")


def run_remote_datasetgen(server):
    scp_datasetgen_script(server)
    hostname = server["hostname"]
    print(f"Starting dataset generation on {hostname}")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        client.connect(hostname, username=username)

        commands = [
            "tmux kill-session -t datasetgen || true",
            "mkdir -p /mydata/ccbench-dataset",
            "rm -rf /mydata/ccbench-dataset/*",
            "tmux new-session -d -s datasetgen",
            "tmux send-keys -t datasetgen 'cd ~/ccBench' C-m",
            "tmux send-keys -t datasetgen 'source ~/venv/bin/activate' C-m",
            "tmux send-keys -t datasetgen 'cd ~/ccBench/pantheon-modified/src/experiments' C-m",
            "tmux send-keys -t datasetgen 'python palantir_datasetgen_rtt.py' C-m"
        ]

        for cmd in commands:
            print(f"[{hostname}] $ {cmd}")
            stdin, stdout, stderr = client.exec_command(cmd)
            time.sleep(0.5)

            out = stdout.read().decode().strip()
            err = stderr.read().decode().strip()
            if out:
                print(f"[{hostname}] STDOUT:\n{out}")
            if err:
                print(f"[{hostname}] STDERR:\n{err}")

    except Exception as e:
        print(f"Error on {hostname}: {e}")
    finally:
        client.close()


def collect_dataset_from_node(server, idx):
    hostname = server["hostname"]
    remote_synthetic_file = f"{username}@{hostname}:{dataset_path_synthetic}"
    dest_file = f"{args.target_path}/6col-rtt-20_synthetic-node{idx}.p"
    scp_cmd_synthetic = ["scp", "-3", remote_synthetic_file, dest_file]
    remote_real_file = f"{username}@{hostname}:{dataset_path_real}"
    dest_file_real = f"{args.target_path}/6col-rtt-20_real-node{idx}.p"
    scp_cmd_real = ["scp", "-3", remote_real_file, dest_file_real]

    print(f"[Node {idx} - {hostname}] Collecting dataset to {dest_file}")
    try:
        subprocess.run(scp_cmd_synthetic, check=True)
        subprocess.run(scp_cmd_real, check=True)
        print(f"[Node {idx}] Dataset collected successfully.")
    except subprocess.CalledProcessError as e:
        print(f"[Node {idx}] Failed to collect dataset: {e}")


if __name__ == "__main__":
    if args.collect:
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(servers)) as executor:
            futures = {
                executor.submit(collect_dataset_from_node, server, idx): server["hostname"]
                for idx, server in enumerate(servers)
            }
            for future in concurrent.futures.as_completed(futures):
                hostname = futures[future]
                try:
                    future.result()
                except Exception as e:
                    print(f"Failed to collect from {hostname}: {e}")
        print("Dataset collection complete.")
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(servers)) as executor:
            futures = {
                executor.submit(run_remote_datasetgen, server): server["hostname"]
                for server in servers
            }
            for future in concurrent.futures.as_completed(futures):
                hostname = futures[future]
                try:
                    future.result()
                except Exception as e:
                    print(f"Failed to run on {hostname}: {e}")

        print("Dataset generation launched on all servers.")
