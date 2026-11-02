#!/bin/bash -eux
python3 -m grpc_tools.protoc -Izpui_lib.helpers.grpc_files=helpers/grpc_files --python_out=../ --grpclib_python_out=../ helpers/grpc_files/zpui_api.proto
