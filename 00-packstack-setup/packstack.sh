#!/bin/bash

set -x

yum update -y
yum install -y vim git tmux wget curl patch tree ansible

cp -f CentOS-OpenStack-liberty.repo /etc/yum.repos.d/

yum install -y openstack-packstack
yum install -y centos-release-qemu-ev
yum install -y qemu-kvm-ev
yum install -y libvirt mariadb-server

packstack --allinone --provision-demo=n --os-neutron-ovs-bridge-mappings=extnet:br-ex --os-neutron-ovs-bridge-interfaces=br-ex:eth0 --os-neutron-ml2-type-drivers=vxlan,flat \
	--os-neutron-lbaas-install=y --nagios-install=n --os-heat-install=y --os-swift-install=n --default-password=password

yum install -y python-croniter
systemctl restart openstack-heat-*

#yum install -y htop iperf

source ~/keystonerc_admin
neutron net-create public --provider:network_type flat --provider:physical_network extnet  --router:external
ip a add dev br-ex 192.168.122.1
neutron subnet-create --name public_subnet --enable_dhcp=True --allocation-pool=start=192.168.122.10,end=192.168.122.20 --gateway=192.168.122.1 public 192.168.122.0/24
curl http://download.cirros-cloud.net/0.3.4/cirros-0.3.4-x86_64-disk.img | glance image-create --name='cirros' --visibility=public --container-format=bare --disk-format=qcow2
neutron router-create router1
neutron router-gateway-set router1 public
neutron net-create private
neutron subnet-create --name private_subnet private 192.168.100.0/24
neutron router-interface-add router1 private_subnet
