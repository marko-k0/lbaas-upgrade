#!/bin/bash

source ~/keystonerc_admin

set -x
script_dir=$(dirname "$0")

heat stack-create -f $script_dir/heat-lbaas-tcp.yaml test-tcp
heat stack-create -f $script_dir/heat-lbaas-http-1.yaml test-http-1
heat stack-create -f $script_dir/heat-lbaas-http-2.yaml test-http-2

