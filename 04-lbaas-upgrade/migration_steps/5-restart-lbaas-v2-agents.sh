#!/bin/bash

ansible -i "$LBAAS_HOSTS" all -b -K -m systemd -a "name=neutron-lbaasv2-agent state=restarted"

echo "Waiting for $LBAAS_HOSTS_COUNT v2 agents to be registered..."
LBAASV2_HOSTS_COUNT=0

while [ "$LBAAS_HOSTS_COUNT" -ne "$LBAASV2_HOSTS_COUNT" ];
do
  sleep 3
  LBAASV2_HOSTS_COUNT=$(mysql neutron -sNe 'select count(*) from agents where `binary` = "neutron-lbaasv2-agent"')
  echo "Registered $LBAASV2_HOSTS_COUNT v2 agents so far..."
done
