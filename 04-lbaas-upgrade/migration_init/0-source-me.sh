#!/bin/bash

export LBAAS_HOSTS=$(sudo mysql neutron -sNe 'select host from agents where `binary` = "neutron-lbaas-agent" and TIMESTAMPDIFF(SECOND, heartbeat_timestamp, NOw()) < 300' | awk 1 ORS=',')
export LBAAS_HOSTS_COUNT=$(sudo mysql neutron -sNe 'select count(*) from agents where `binary` = "neutron-lbaas-agent" and TIMESTAMPDIFF(SECOND, heartbeat_timestamp, NOw()) < 300')
