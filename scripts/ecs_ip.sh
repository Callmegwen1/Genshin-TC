#!/usr/bin/env bash
# Print the public IP of the running API task. Fargate tasks without a load balancer get a new IP on every
# deployment or restart, so look it up instead of hard-coding it.
#   bash scripts/ecs_ip.sh [cluster] [service]
set -euo pipefail
CLUSTER=${1:-gtc-cluster}
SERVICE=${2:-gtc-api}
TASK=$(aws ecs list-tasks --cluster "$CLUSTER" --service-name "$SERVICE" --desired-status RUNNING \
  --query 'taskArns[0]' --output text)
[ "$TASK" = "None" ] && { echo "no running task" >&2; exit 1; }
ENI=$(aws ecs describe-tasks --cluster "$CLUSTER" --tasks "$TASK" \
  --query "tasks[0].attachments[0].details[?name=='networkInterfaceId'].value" --output text)
aws ec2 describe-network-interfaces --network-interface-ids "$ENI" \
  --query 'NetworkInterfaces[0].Association.PublicIp' --output text
