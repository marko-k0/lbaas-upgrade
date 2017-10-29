#!/bin/bash

fecho () {
  set +x
  termwidth="$(tput cols)"
  padding="$(printf '%0.1s' ={1..500})"
  printf '%*.*s %s %*.*s\n' 0 "$(((termwidth-2-${#1})/2))" "$padding" "$1" 0 "$(((termwidth-1-${#1})/2))" "$padding"
  set -x
}

script_dir=$(dirname "$0")

# perform the migration
fecho "Performing LBaaS v1 to v2 DB data migration"
cp $script_dir/haproxy_proxies.j2.patch /usr/lib/python2.7/site-packages/neutron_lbaas/services/loadbalancer/drivers/haproxy/templates
cp $script_dir/4aff599b9845_lbaas_v1_to_v2_migration.py /usr/lib/python2.7/site-packages/neutron_lbaas/db/migration/alembic_migrations/versions/liberty/expand/
# copy alembic migration file and change head revision
sed -i 's/3345facd0452/4aff599b9845/g' /usr/lib/python2.7/site-packages/neutron_lbaas/db/migration/alembic_migrations/versions/HEADS
neutron-db-manage --subproject neutron-lbaas upgrade head

# set lbaas to v2 from v1
pushd .
cd /etc/neutron

fecho "Backing up neutron config files"
cp -f neutron.conf neutron.conf.lbaasv1
cp -f neutron_lbaas.conf neutron_lbaas.conf.lbaasv1
cp -f lbaas_agent.ini lbaas_agent.ini.lbaasv1

fecho "Enabling LBaaS v2"
crudini --set neutron.conf DEFAULT service_plugins router,neutron_lbaas.services.loadbalancer.plugin.LoadBalancerPluginv2
crudini --set neutron_lbaas.conf service_providers service_provider LOADBALANCERV2:Haproxy:neutron_lbaas.drivers.haproxy.plugin_driver.HaproxyOnHostPluginDriver:default
crudini --set lbaas_agent.ini DEFAULT device_driver neutron_lbaas.drivers.haproxy.namespace_driver.HaproxyNSDriver

# bug 1600326
fecho "Patching haproxy_proxies.j2 template file"
cd /usr/lib/python2.7/site-packages/neutron_lbaas/services/loadbalancer/drivers/haproxy/templates
patch < haproxy_proxies.j2.patch

fecho "Backing up LBaaS v1 database tables"
mysqldump --no-create-info --no-create-db --extended-insert --single-transaction --complete-insert --insert-ignore \
        neutron members poolmonitorassociations poolstatisticss pools poolloadbalanceragentbindings vips | gzip > neutron-lbaas-v1-pre-upgrade-backup.sql.gz

LBAAS_HOSTS=$(mysql neutron -sNe 'select host from agents where `binary` = "neutron-lbaas-agent" and TIMESTAMPDIFF(SECOND, heartbeat_timestamp, NOw()) < 300')

# disable/stop all lbaas v1 agents and enable/start lbaas v2 agents so they register
fecho "Disabling LBaaS v1 agents and enabling LBaaS v2 agents"
for lbaas_host in $LBAAS_HOSTS; do
  echo " * host: $lbaas_host"
  ssh -o StrictHostKeyChecking=no -o ConnectTimeout=2 -q $lbaas_host \ '
  cd /etc/neutron

  cp -f neutron.conf neutron.conf.lbaasv1
  cp -f neutron_lbaas.conf neutron_lbaas.conf.lbaasv1
  cp -f lbaas_agent.ini lbaas_agent.ini.lbaasv1

  crudini --set neutron.conf DEFAULT service_plugins router,neutron_lbaas.services.loadbalancer.plugin.LoadBalancerPluginv2
  crudini --set neutron_lbaas.conf service_providers service_provider LOADBALANCERV2:Haproxy:neutron_lbaas.drivers.haproxy.plugin_driver.HaproxyOnHostPluginDriver:default
  crudini --set lbaas_agent.ini DEFAULT device_driver neutron_lbaas.drivers.haproxy.namespace_driver.HaproxyNSDriver

  systemctl disable neutron-lbaas-agent; systemctl stop neutron-lbaas-agent; systemctl enable neutron-lbaasv2-agent
  '
  test $? -eq 0 || echo "Could not connect to $lbaas_host!!!"
done

fecho "Restarting neutron-server"
systemctl restart neutron-server.service

fecho "Starting LBaaS v2 agents"
for lbaas_host in $LBAAS_HOSTS; do
  echo " * host: $lbaas_host"
  ssh -o StrictHostKeyChecking=no -o ConnectTimeout=2 -q $lbaas_host 'systemctl start neutron-lbaasv2-agent'
  test $? -eq 0 || echo "Could not connect to $lbaas_host!!!"
done

sleep 60 

# update loadbalancer agent bindings and loadbalancer's ports device owner
fecho "Updating port device owner and load balancer agent bindings"
mysql neutron << 'EOF'
# update ports device_owner
update ports set device_owner = 'neutron:LOADBALANCERV2' where device_owner = 'neutron:LOADBALANCER';

# update lbaas_loadbalanceragentbinding (lbaas agent v1 in use)
update lbaas_loadbalanceragentbindings lbab inner join agents a on (lbab.agent_id = a.id) set lbab.agent_id = (select id from agents where `binary` = 'neutron-lbaasv2-agent' and host = a.host);
EOF

# restart lbaas v2 agent to start haproxy within v2 agent
fecho "Restarting LBaaS v2 agents"
for lbaas_host in $LBAAS_HOSTS; do
  echo " * host: $lbaas_host"
  ssh -o StrictHostKeyChecking=no -o ConnectTimeout=2 -q $lbaas_host 'systemctl restart neutron-lbaasv2-agent' 
  test $? -eq 0 || echo "Could not connect to $lbaas_host!!!"
done

sleep 30

# send SIGTTOU and SIGUSR1 signals to haproxy process from lbaas v1 in case haproxy from lbaas v2 is running
fecho "Sending SIGTTOU and SIGUSR1 to haproxy process from LBaaS v1"
for lbaas_host in $LBAAS_HOSTS; do
  echo " * host: $lbaas_host"
  ssh -o StrictHostKeyChecking=no -o ConnectTimeout=2 $lbaas_host \ '
  uuids=$(ls /var/lib/neutron/lbaas/)
  uuids=$(for uuid in $uuids; do ps aux | grep -q "/[v]ar/lib/neutron/lbaas/v2/$uuid" && echo $uuid; done)
  pids=$(for uuid in $uuids; do ps aux | grep "/[v]ar/lib/neutron/lbaas/$uuid" | tr -s " " | cut -d " " -f 2; done);
  for pid in $pids; do kill -s SIGTTOU -s SIGUSR1 $pid; echo "Sending SIGTTOU & SIGUSR1 to pid $pid"; done
  ' 
  test $? -eq 0 || echo "Could not connect to $lbaas_host!!!"
done

popd

fecho "Backing up heat database"
mysqldump --no-create-info --no-create-db --extended-insert --single-transaction --complete-insert --insert-ignore \
        --ignore-table heat.migrate_version heat | gzip > heat-pre-upgrade-backup.sql.gz

# translate heat stacks to use lbaas v2 resources
fecho "Translating heat stacks"
python $script_dir/lbaas_upgrade.py

mysql heat << 'EOF'
update raw_template set files = REPLACE(files, 'OS::Neutron::PoolMember', 'OS::Neutron::LBaaS::PoolMember');
update raw_template set files = REPLACE(files, 'pool_id', 'pool');
EOF

systemctl -M heat_newton start openstack-heat-api

# remove this "alembic migration revision"
rm /usr/lib/python2.7/site-packages/neutron_lbaas/db/migration/alembic_migrations/versions/liberty/expand/4aff599b9845_lbaas_v1_to_v2_migration.py
sed -i 's/4aff599b9845/3345facd0452/g' /usr/lib/python2.7/site-packages/neutron_lbaas/db/migration/alembic_migrations/versions/HEADS
mysql neutron -e "update alembic_version_lbaas set version_num = '3345facd0452' where version_num = '4aff599b9845'"

