#!/bin/bash

systemctl -M heat_newton start openstack-heat-api

mysql neutron << 'EOF'
# delete lbaas v1 records (ports can't be deleted due to vips port_id constraint)
delete from members;
delete from poolmonitorassociations;
delete from poolstatisticss;
delete from pools;
delete from poolloadbalanceragentbindings;
delete from vips;
EOF
