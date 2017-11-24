#!/bin/bash

ansible -i "$LBAAS_HOSTS" all -b -K -m script -a ansible-signal-v2-haproxy.sh
