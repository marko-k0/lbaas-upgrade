#!/bin/bash

sudo mysql neutron << 'EOF'
# update ports device_owner
update ports set device_owner = 'neutron:LOADBALANCER' where device_owner = 'neutron:LOADBALANCERV2';

# update lbaas_loadbalanceragentbinding (lbaas agent v2 in use)
update lbaas_loadbalanceragentbindings lbab inner join agents a on (lbab.agent_id = a.id) set lbab.agent_id = IFNULL((select id from agents where `binary` = 'neutron-lbaas-agent' and host = a.host), lbab.agent_id);
EOF
