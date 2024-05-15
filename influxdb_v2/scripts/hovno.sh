#!/bin/bash


influx bucket create --org sfi --name machines
#docker exec -it iot2-influxdb-1 influx bucket create --org sfi --name machines