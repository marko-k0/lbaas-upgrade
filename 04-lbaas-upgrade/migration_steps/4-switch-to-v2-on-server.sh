#!/bin/bash

sudo cp -n /etc/neutron/neutron.conf /etc/neutron/neutron.conf.lbaasv1
sudo cp -n /etc/neutron/neutron_lbaas.conf /etc/neutron/neutron_lbaas.conf.lbaasv1
sudo cp -n /etc/neutron/lbaas_agent.ini /etc/neutron/lbaas_agent.ini.lbaasv1

sudo crudini --set /etc/neutron/neutron.conf DEFAULT service_plugins router,neutron_lbaas.services.loadbalancer.plugin.LoadBalancerPluginv2
sudo crudini --set /etc/neutron/neutron_lbaas.conf service_providers service_provider LOADBALANCERV2:Haproxy:neutron_lbaas.drivers.haproxy.plugin_driver.HaproxyOnHostPluginDriver:default
sudo crudini --set /etc/neutron/lbaas_agent.ini DEFAULT device_driver neutron_lbaas.drivers.haproxy.namespace_driver.HaproxyNSDriver

sudo systemctl restart neutron-server.service
