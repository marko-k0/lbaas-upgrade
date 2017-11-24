#!/bin/bash

ansible -i "$LBAAS_HOSTS" all -b -K -m script -a ansible-signal-v1-haproxy.sh
