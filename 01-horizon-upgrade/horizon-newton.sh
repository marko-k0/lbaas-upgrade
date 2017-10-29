#!/bin/bash

setenforce 0

CONTAINER_NAME=horizon_newton

yum -y --releasever=7 --nogpg --installroot=/var/lib/machines/$CONTAINER_NAME --disablerepo="*" --enablerepo=base install systemd passwd yum centos-release vim
yum -y --releasever=7 --nogpg --installroot=/var/lib/machines/$CONTAINER_NAME install vim lsof tmux tcpdump iproute iputils httpd centos-release-openstack-newton
yum -y --releasever=7 --nogpg --installroot=/var/lib/machines/$CONTAINER_NAME install openstack-dashboard openstack-neutron-lbaas-ui

rm -f /var/lib/machines/$CONTAINER_NAME/etc/machine-id
systemd-firstboot --root=/var/lib/machines/$CONTAINER_NAME --setup-machine-id

chroot /var/lib/machines/$CONTAINER_NAME /bin/bash -x <<'EOF'
echo 'pts/0' >> /etc/securetty
sed -i "s/^Listen 80/Listen 8888/g" /etc/httpd/conf/*.conf
ln -s /usr/lib/systemd/system/httpd.service /etc/systemd/system/multi-user.target.wants/httpd.service
touch /var/log/horizon/horizon.log
chown apache:apache /var/log/horizon/horizon.log
echo 'password' | passwd root --stdin
EOF

cp -f /etc/openstack-dashboard/local_settings /var/lib/machines/$CONTAINER_NAME/etc/openstack-dashboard/local_settings

script_dir=$(dirname "$0")
mkdir -p /etc/systemd/system/systemd-nspawn@horizon_newton.service.d
cp $script_dir/override.conf /etc/systemd/system/systemd-nspawn@horizon_newton.service.d/

echo "Listen 81" >> /etc/httpd/conf/ports.conf
cp $script_dir/10-horizon_vhost.conf /etc/httpd/conf.d/

mkdir -p /var/log/journal
systemctl enable systemd-nspawn@horizon_newton
systemctl start systemd-nspawn@horizon_newton
systemctl restart httpd
