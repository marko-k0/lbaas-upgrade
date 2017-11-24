#!/bin/bash

sudo cp -f /etc/neutron/neutron.conf.lbaasv1 /etc/neutron/neutron.conf 
sudo cp -f /etc/neutron/neutron_lbaas.conf.lbaasv1 /etc/neutron/neutron_lbaas.conf 
sudo cp -f /etc/neutron/lbaas_agent.ini.lbaasv1 /etc/neutron/lbaas_agent.ini 

sudo systemctl disable neutron-lbaasv2-agent
sudo systemctl stop neutron-lbaasv2-agent
sudo systemctl enable neutron-lbaas-agent
