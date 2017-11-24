#!/bin/bash

test -z "$LBAAS_HOSTS" && echo "LBAAS_HOSTS env variable missing!" && exit

ansible -i "$LBAAS_HOSTS" all -b -K -m script -a ansible-switch-to-v1-agent.sh
