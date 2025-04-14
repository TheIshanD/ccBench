import paramiko
import time
import os
import yaml
import concurrent.futures
import socket
import argparse

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Setup ccBench dataset collection on remote servers")
parser.add_argument("--after-reboot", action="store_true", help="Only run post-reboot commands")
args = parser.parse_args()

# Load configuration from YAML file
CONFIG_FILE = "config.yaml"

with open(CONFIG_FILE, "r") as file:
    config = yaml.safe_load(file)

servers = config["servers"]
username = "ishandas"

def run_remote_commands(server, commands):
    """ SSH into the server and execute the given commands """
    print(f"Connecting to {server}...")
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        client.connect(server, username=username)
        for cmd in commands:
            print(f"Running on {server}: {cmd}")
            stdin, stdout, stderr = client.exec_command(cmd)
            time.sleep(2)  # Allow time for command execution
            print(stdout.read().decode())
            print(stderr.read().decode())

            if "reboot" in cmd:
                print(f"Reboot command issued for {server}. Disconnecting...")
                client.close()
                return  # Stop execution since the server will go down
    finally:
        client.close()

def wait_for_server(server, timeout=500, interval=10):
    """ Wait until the server is fully booted and SSH is accessible """
    print(f"Waiting for {server} to reboot and become available via SSH...")
    start_time = time.time()

    while time.time() - start_time < timeout:
        # Check if SSH (port 22) is open
        try:
            sock = socket.create_connection((server, 22), timeout=5)
            sock.close()
            print(f"{server} is now fully online with SSH available!")
            return True
        except (socket.timeout, ConnectionRefusedError):
            pass  # SSH is not available yet, keep waiting
        
        time.sleep(interval)
    
    print(f"Timeout: {server} did not come back online within {timeout} seconds.")
    return False


def setup_server(server_config):
    """ Run full setup process for a single server in parallel """
    server = server_config["hostname"]

    commands_before_reboot = [
        "sudo DEBIAN_FRONTEND=noninteractive apt-get update -y",
        "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y build-essential git debhelper autotools-dev dh-autoreconf iptables protobuf-compiler libprotobuf-dev pkg-config libssl-dev dnsmasq-base ssl-cert libxcb-present-dev libcairo2-dev libpango1.0-dev iproute2 apache2-dev apache2-bin gnuplot iproute2 apache2-api-20120211 libwww-perl",
        "sudo chown -R ishandas /mydata/",
    
        "cd ~ && git clone https://github.com/Janecjy/ccBench.git",
        "cd ~/ccBench && git submodule update --init --recursive",
        
        "cd ~/ccBench && git clone https://github.com/ravinet/mahimahi",
        "cd ~/ccBench/mahimahi && patch -p1 < ../patches/mahimahi.core.v2.2.patch",
        "cd ~/ccBench/mahimahi && patch -p1 < ../patches/mahimahi.extra.aqm.v1.5.patch",
        "cd ~/ccBench/mahimahi && ./autogen.sh && ./configure && make",
        "cd ~/ccBench/mahimahi && sudo make install",
        "sudo sysctl -w net.ipv4.ip_forward=1",
        
        "mkdir -p ~/venv",
        "sudo apt install -y python3-pip",
        "sudo pip3 install -U virtualenv",
        "virtualenv ~/venv -p python3",
        
        "source ~/venv/bin/activate && pip install --upgrade pip",
        "source ~/venv/bin/activate && pip install gym tensorflow==1.14 sysv_ipc torch",
        
        "cd ~ && git clone https://github.com/soheil-ab/sage.git",
        "cd ~/sage/linux-patch && sudo dpkg -i linux-image-4.19.112-0062_4.19.112-0062-10.00.Custom_amd64.deb",
        "cd ~/sage/linux-patch && sudo dpkg -i linux-headers-4.19.112-0062_4.19.112-0062-10.00.Custom_amd64.deb",
        
        "sudo reboot"
    ]

    commands_after_reboot = [
        "ssh-keyscan -H github.com >> ~/.ssh/known_hosts",
        # Ensure Pantheon-modified is installed
        "cd ~/ccBench/ && git reset --hard && git fetch && git checkout dataset-collection && git pull",
        "cd ~/ccBench/pantheon-modified/third_party/pantheon-tunnel/ && chmod +x autogen.sh",
        "cd ~/ccBench/pantheon-modified/tools/ && chmod +x install_deps.sh && ./install_deps.sh",
        "cd ~/ccBench/pantheon-modified/ && chmod +x src/experiments/setup.py",
        "cd ~/ccBench/pantheon-modified/src/wrappers/ && chmod +x *.py",
        "cd ~/ccBench/pantheon-modified/ && src/experiments/setup.py --install-deps --all",
        "cd ~/ccBench/pantheon-modified/src/experiments/ && chmod +x *.sh && chmod +x *.py",
        "cd ~/ccBench/pantheon-modified/third_party/tcpdatagen/ && chmod +x *.sh && ./build.sh",
        "cd ~ && git clone https://github.com/Janecjy/Genet.git || (cd Genet && git pull)",
    ]

    # Run commands before reboot
    if not args.after_reboot:
        run_remote_commands(server, commands_before_reboot)

    # Wait for the server to come back online
    if wait_for_server(server):
        # Run commands after reboot
        run_remote_commands(server, commands_after_reboot)
    else:
        print(f"Skipping post-reboot setup for {server} due to timeout.")

    print(f"Setup completed for {server}.")

# Run setup on all servers in parallel
with concurrent.futures.ThreadPoolExecutor(max_workers=len(servers)) as executor:
    futures = {executor.submit(setup_server, server_config): server_config["hostname"] for server_config in servers}
    
    for future in concurrent.futures.as_completed(futures):
        server = futures[future]
        try:
            future.result()
        except Exception as e:
            print(f"Error setting up {server}: {e}")

print("Setup completed on all servers.")
