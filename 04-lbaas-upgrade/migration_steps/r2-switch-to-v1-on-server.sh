#!/bin/bash

sudo cp -n /etc/neutron/neutron.conf.lbaasv1 /etc/neutron/neutron.conf
sudo cp -n /etc/neutron/neutron_lbaas.conf.lbaasv1 /etc/neutron/neutron_lbaas.conf
sudo cp -n /etc/neutron/lbaas_agent.ini.lbaasv1 /etc/neutron/lbaas_agent.ini

sudo systemctl restart neutron-server.service
