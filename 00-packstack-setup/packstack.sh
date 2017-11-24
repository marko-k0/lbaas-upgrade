#!/bin/bash

set -x

yum update -y
yum install -y vim git tmux wget curl patch tree ansible

cp -f CentOS-OpenStack-liberty.repo /etc/yum.repos.d/

yum install -y openstack-packstack
yum install -y centos-release-qemu-ev
yum install -y qemu-kvm-ev
yum install -y libvirt mariadb-server

packstack --allinone --os-neutron-lbaas-install=y --nagios-install=n --os-heat-install=y --os-swift-install=n --default-password=password

yum install -y python-croniter
systemctl restart openstack-heat-*
