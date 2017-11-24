#!/bin/bash

fecho () {
  termwidth="$(tput cols)"
  padding="$(printf '%0.1s' ={1..500})"
  printf '%*.*s %s %*.*s\n' 0 "$(((termwidth-2-${#1})/2))" "$padding" "$1" 0 "$(((termwidth-1-${#1})/2))" "$padding"
}

cleanup () {
  kill -s SIGTERM $$
  exit 0
}

trap cleanup SIGINT SIGTERM

VERSION=""
[ "$1" == "v2" ] && VERSION="v2/"

#LBAAS_HOSTS=$(sudo mysql neutron -sNe 'select host from agents where `binary` = "neutron-lbaas-agent" and TIMESTAMPDIFF(SECOND, heartbeat_timestamp, NOw()) < 600' | awk 1 ORS=',')
#LBAAS_HOSTS=$(sudo mysql neutron -sNe 'select host from agents where `binary` = "neutron-lbaas-agent"' | awk 1 ORS=',')

while true; do
  if [ -z "$VERSION" ]; then
    fecho "Watching haproxyies from LBaaS v1"
  else
    fecho "Watching haproxyies from LBaaS v2"
  fi

  ansible -i "$LBAAS_HOSTS" all -m shell -a "ps aux | grep '/[v]ar/lib/neutron/lbaas/$VERSION\w*-\w*-\w*-\w*-\w*'"

  fecho "Sleeping 10 second"
  sleep 10
done

