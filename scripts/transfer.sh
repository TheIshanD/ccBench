#!/bin/bash

# Load node configuration from config.yaml
CONFIG_FILE="config.yaml"

# Parse the original nodes from the config file
echo "Reading original nodes from $CONFIG_FILE..."
original_nodes=($(yq e '.servers[].hostname' $CONFIG_FILE))

# Define new nodes manually in an array (assuming order matches original nodes)
new_nodes=(
  "clnode178.clemson.cloudlab.us"
  "clnode134.clemson.cloudlab.us"
  "clnode174.clemson.cloudlab.us"
  "clnode173.clemson.cloudlab.us"
  "clnode160.clemson.cloudlab.us"
  "clnode162.clemson.cloudlab.us"
  "clnode140.clemson.cloudlab.us"
  "clnode167.clemson.cloudlab.us"
  "clnode146.clemson.cloudlab.us"
  "clnode136.clemson.cloudlab.us"
)

# Ensure local node has the SSH key access
LOCAL_NODE="ishandas@$(hostname)"

# Check if we should only perform the second part (transfer after zip completion)
TRANSFER_ONLY=false
if [[ "$1" == "transfer" ]]; then
    TRANSFER_ONLY=true
fi

for i in "${!original_nodes[@]}"; do
    old_node=${original_nodes[$i]}
    new_node=${new_nodes[$i]}
    
    echo "Processing transfer from $old_node to $new_node..."
    
    if [ "$TRANSFER_ONLY" = false ]; then
        # Start the zip process inside a tmux session on the old node
        ssh ishandas@$old_node "tmux new-session -d -s zip_session 'zip -r /mydata/traces-1.zip /mydata/ccbench-traces/'"
        echo "Started zip process in tmux on $old_node. Run script again with 'transfer' argument after completion."
    else

        # Set ownership on the new node
        ssh ishandas@$new_node "sudo chown -R ishandas /mydata/"
        
        # Use scp -3 to transfer the archive from old node to new node via the local machine
        echo "Transferring /mydata/traces-1.zip from $old_node to $new_node..."
        scp -3 ishandas@$old_node:/mydata/traces-1.zip ishandas@$new_node:/mydata/
        
        
        
        echo "Transfer completed from $old_node to $new_node."
    fi

done

echo "Process completed successfully."
