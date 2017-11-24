#!/bin/bash

source ~/keystonerc_admin
script_dir=$(dirname "$0")

set -x

NETWORK=private
NETWORK_PUB=public
KEYNAME=test-key

neutron net-update --shared=True $NETWORK

test -f ~/.ssh/id_rsa || ssh-keygen -t rsa -N "" -f ~/.ssh/id_rsa
nova keypair-add --pub-key ~/.ssh/id_rsa.pub $KEYNAME

PROJ_ID=$(openstack project show -f value -c id admin)
openstack quota set --volumes -1 --cores -1 --ram -1 --secgroups -1 --floating-ips -1 --instances -1 $PROJ_ID

for name in allow_everything
do
  neutron security-group-create $name
  neutron security-group-rule-create $name --protocol tcp
  neutron security-group-rule-create $name --protocol udp
  neutron security-group-rule-create $name --protocol icmp
done

heat stack-create -f $script_dir/heat-lbaas-http.yaml test-http-1
heat stack-create -f $script_dir/heat-lbaas-http.yaml test-http-2
