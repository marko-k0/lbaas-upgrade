#!/bin/bash

ansible -i "$LBAAS_HOSTS" all -b -K -m systemd -a "name=neutron-lbaas-agent state=restarted"

