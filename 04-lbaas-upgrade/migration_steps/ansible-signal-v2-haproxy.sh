#!/bin/bash

uuids=$(ls /var/lib/neutron/lbaas/v2/)
uuids=$(for uuid in $uuids; do ps aux | grep -q "/[v]ar/lib/neutron/lbaas/$uuid" && echo $uuid; done)
pids=$(for uuid in $uuids; do ps aux | grep "/[v]ar/lib/neutron/lbaas/v2/$uuid" | tr -s " " | cut -d " " -f 2; done);
for pid in $pids; do kill -s SIGTTOU -s SIGUSR1 $pid; echo "Sending SIGTTOU & SIGUSR1 to pid $pid"; done
