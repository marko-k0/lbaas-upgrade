#!/bin/bash -x

setenforce 0

CONTAINER_NAME=heat_newton

yum -y --releasever=7 --nogpg --installroot=/var/lib/machines/$CONTAINER_NAME --disablerepo="*" --enablerepo=base install systemd passwd yum centos-release vim
yum -y --releasever=7 --nogpg --installroot=/var/lib/machines/$CONTAINER_NAME install vim lsof tmux tcpdump iproute iputils centos-release-openstack-newton
yum -y --releasever=7 --nogpg --installroot=/var/lib/machines/$CONTAINER_NAME install openstack-heat-*

rm -f /var/lib/machines/$CONTAINER_NAME/etc/machine-id
systemd-firstboot --root=/var/lib/machines/$CONTAINER_NAME --setup-machine-id

chroot /var/lib/machines/$CONTAINER_NAME /bin/bash -x <<'EOF'
echo 'pts/0' >> /etc/securetty
echo 'password' | passwd root --stdin
ln -s /usr/lib/systemd/system/openstack-heat-api.service /etc/systemd/system/multi-user.target.wants/openstack-heat-api.service
ln -s /usr/lib/systemd/system/openstack-heat-engine.service /etc/systemd/system/multi-user.target.wants/openstack-heat-engine.service
EOF

cp -f /etc/heat/heat.conf /var/lib/machines/$CONTAINER_NAME/etc/heat/heat.conf

script_dir=$(dirname "$0")
mkdir -p /etc/systemd/system/systemd-nspawn@$CONTAINER_NAME.service.d
cp $script_dir/override.conf /etc/systemd/system/systemd-nspawn@$CONTAINER_NAME.service.d/

mkdir -p /var/log/journal
systemctl stop openstack-heat-*
systemctl disable openstack-heat-api openstack-heat-engine
systemctl enable systemd-nspawn@$CONTAINER_NAME
systemctl start systemd-nspawn@$CONTAINER_NAME

nsenter --target=$(machinectl show --property Leader heat_newton | sed "s/^Leader=//") --mount --uts --ipc --net --pid heat-manage db_sync
systemctl -M heat_newton stop openstack-heat-api

