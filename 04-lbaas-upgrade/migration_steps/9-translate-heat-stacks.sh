#!/bin/bash

sudo python ../lbaas_upgrade.py

sudo mysql heat << 'EOF'
update raw_template set files = REPLACE(files, 'OS::Neutron::PoolMember', 'OS::Neutron::LBaaS::PoolMember');
update raw_template set files = REPLACE(files, 'pool_id', 'pool');
EOF

echo "Start heat api if everything went well!"
echo "systemctl -M heat_newton start openstack-heat-api"
