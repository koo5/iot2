## intro
this works pretty well, but parses the topic from the start, so, you cannot use it if you use custom mqtt prefix in your esphome config. In a next iteration, i might make it parse the topic backwards instead, ie,  "state" or "debug" , field, optional control ("pump1"), category, host, optional prefix 

## development
```
 set -x INFLUXDB_V2_BUCKET iot2; ./purge_bucket.sh; ./debug_run.sh; ./purge_bucket.sh
```
