#!/bin/bash

uuids=$(ls /var/lib/neutron/lbaas/)
uuids=$(for uuid in $uuids; do ps aux | grep -q "/[v]ar/lib/neutron/lbaas/v2/$uuid" && echo $uuid; done)
pids=$(for uuid in $uuids; do ps aux | grep "/[v]ar/lib/neutron/lbaas/$uuid" | tr -s " " | cut -d " " -f 2; done);
for pid in $pids; do kill -s SIGTTOU -s SIGUSR1 $pid; echo "Sending SIGTTOU & SIGUSR1 to pid $pid"; done
