#!/usr/bin/env python3

"""

connect to mqtt broker and subscribe to all topics. Connect to influxdb 2v, and submit each message as a measurement.

"""
import json
import sys
import threading
import datetime
import os
import queue
import subprocess
import time
import logging



logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)



process_started = datetime.datetime.utcnow()
hostname = subprocess.check_output(['hostname'], text=True).strip()



from secrets import secret


with open(os.environ['SECRETS_DIR'] + '/' + 'secrets.json') as fp:
	secrets = json.load(fp)
print(f"secrets={secrets}")


influxdb_configs = secrets['influx']
mqtt_configs = secrets['mqtt']


import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS, WriteApi


#if os.environ.get('DEBUG_AUTH'):
#	debug(f"""connecting to influxdb url={influxdb_config}""")
#else:
#	debug(f"""connecting to influxdb url={influxdb_config['url']}, token={influxdb_config['token'][:1]}..{influxdb_config['token'][-1:]}, {influxdb_config['org']=}, {influxdb_config['bucket']=}""")


messages_processed = 0

def uptime():
	return float((datetime.datetime.utcnow() - process_started).total_seconds())

def uptime_points(note):
	return [
		Point('server').
				tag("host", hostname).
				tag('note', note).
				tag("service", 'esphome_mqtt_to_influx2').
				tag("process_started", str(process_started.isoformat())).
				field("uptime", uptime()),
		Point('server').
				tag("host", hostname).
				tag('note', note).
				tag("service", 'esphome_mqtt_to_influx2').
				tag("process_started", str(process_started.isoformat())).
				field("unix_timestamp", time.time()),
		Point('server').
				tag("host", hostname).
				tag('note', note).
				tag("service", 'esphome_mqtt_to_influx2').
				tag("process_started", str(process_started.isoformat())).
				field("datetime", datetime.datetime.utcnow().isoformat())
	]




def make_influx_client(config):
	return InfluxDBClient(
		url=config['INFLUXDB_V2_URL'],
		token=config['INFLUXDB_V2_WRITE_TOKEN'],
		org=config['INFLUXDB_V2_ORG'],
		enable_gzip=True,
	)



for config in influxdb_configs:
	try:
		log.info(f"""connecting to influxdb url={config['INFLUXDB_V2_URL']}, token={config['INFLUXDB_V2_WRITE_TOKEN'][:1]}..{config['INFLUXDB_V2_WRITE_TOKEN'][-1:]}, {config['INFLUXDB_V2_ORG']=}, {config['INFLUXDB_V2_BUCKET']=}""")
		with make_influx_client(config) as synchronous_influx_client:
			log.info(f"""influxdb version: {synchronous_influx_client.health()}""")
			with synchronous_influx_client.write_api(write_options=SYNCHRONOUS) as write_api:
				write_api.write(
					bucket=config['INFLUXDB_V2_BUCKET'],
					org=config['INFLUXDB_V2_ORG'],
					record=uptime_points('start')[0]
				)
	except Exception as e:
		log.error(f"Failed to connect to influxdb: {e}")




outflux = queue.Queue(2000)


def outflux_loop(config):
	global messages_processed
	while True:
		try:
			with make_influx_client(config) as influx_client:
				write_api = WriteApi(influxdb_client=influx_client)
				log.debug(f'{write_api=}')
				while True:
					point = outflux.get()
					#log.debug(f'ooo {point=}')
					messages_processed += 1
					write_api.write(bucket=config['INFLUXDB_V2_BUCKET'], org=config['INFLUXDB_V2_ORG'], record=point)
		except Exception as e:
			log.critical(f"outflux_loop: {e}")
			#sys.exit(1)

for config in influxdb_configs:
	threading.Thread(target=outflux_loop, name='outflux', daemon=True, args=(config,)).start()




#
# def uptime_loop():
# 	try:
# 		sleep_secs = 1
# 		while True:
# 			time.sleep(sleep_secs)
# 			for point in uptime_points('outflux_thread_writer_batched'):
# 				outflux.put(point, block=False)
# 	except Exception as e:
# 		debug(f"loop: {e}")
# 		sys.exit(1)
#
#
# def uptime_loop2():
# 	try:
# 		with make_influx_client() as influx_client:
# 			write_api2 = WriteApi(influxdb_client=influx_client, write_options=SYNCHRONOUS)
# 			sleep_secs = 1
# 			while True:
# 				time.sleep(sleep_secs)
# 				for point in uptime_points('synchronous_writer'):
# 					write_api2.write(bucket=influxdb_config['bucket'], org=influxdb_config['org'], record=point)
# 	except Exception as e:
# 		debug(f"loop: {e}")
# 		sys.exit(1)
#
#
# for config in influxdb_configs:
# 	threading.Thread(target=uptime_loop, name='esphome_mqtt_to_influx2_uptime', daemon=True, args=(config,)).start()
# 	threading.Thread(target=uptime_loop2, name='esphome_mqtt_to_influx2_uptime2', daemon=True, args=(config,)).start()






# MQTT callbacks

def on_connect(client, userdata, flags, rc, properties=None):
	log.info(f""""Connected to MQTT server: {userdata['HOST']}, {flags=}, {rc=}, {properties=}""")
	
	# hack. this isn't a configuration, but a runtime state. 
	userdata['seen_topics'] = {}
	
	for topic in userdata.get('TOPICS', ['#']):
		client.subscribe(topic, qos=1)


seen = {}

def on_message(client, userdata, msg):

	ts = datetime.datetime.utcnow()
	topic = msg.topic

	try:
		payload = msg.payload.decode()
	except Exception as e:
		log.debug(e)
		return

	log.debug(f"on_message: {topic} : {payload.__repr__()}")

	seen = userdata['seen_topics']
	if not topic in seen:
		seen[topic] = payload
		log.info(f'skipping first message to avoid old stored value: {topic} : {payload.__repr__()}')
		return

	point = esphome_to_influx(topic, payload)
	if point is None:
		log.debug('ignored.')
		return

	point.time(ts)

	#log.debug(f'point={str(point)}')

	try:
		outflux.put(point, block=False)
	except:
		log.warning(f"nope")

	qs = outflux.qsize()
	if qs > 20:
		log.warning(f"outflux queue length: {qs}")



def esphome_to_influx(topic, payload):

	topic = topic.split('/')

	def t(idx):
		try:
			return topic[idx]
		except IndexError:
			return None

	if topic[-1] not in ['debug', 'state']:
		return

	if topic[-1] == 'state':
		topic = topic[:-1]

	topic = list(map(fix_field, topic))

	try:
		payload = float(payload)
	except ValueError:
		pass

	host = t(0)
	category = t(1)
	component = None
	property = t(2) if len(topic) > 2 else t(1)

	if len(topic) > 3:
		component = t(2)
		property = t(3)

	point = Point(category).field(property, payload)

	if host:
		point = point.tag("host", host)

	if component:
		point = point.tag("component", component)

	return point



def fix_field(field):
	if field.startswith('_'):
		field = 'X' + field[1:]
	return field


# if os.environ.get('DEBUG_AUTH'):
# 	debug(f"""Connecting to mqtt broker {mqtt_config=}""")
# else:
# 	debug(f"""Connecting to mqtt broker host={mqtt_config['host']}""")


for mqtt_config in mqtt_configs:
	
	mqtt_client = mqtt.Client(
		client_id='esphome_mqtt_to_influx2__on__'+hostname+'__'+str(os.getpid()),
		userdata=mqtt_config,
		protocol=mqtt.MQTTv5,
		callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
	
	#mqtt_client.enable_logger()
	
	mqtt_client.username_pw_set(mqtt_config['USER'], mqtt_config['PASS'])
	mqtt_client.on_connect = on_connect
	mqtt_client.on_message = on_message
	
	mqtt_client.connect(
		host=mqtt_config['HOST'],
		port=mqtt_config['PORT'],
		keepalive=mqtt_config.get('keepalive', 10)
	)
	
	threading.Thread(target=mqtt_client.loop_forever).start()



# @mqtt_client.log_callback()
# def on_log(client, userdata, level, buf):
# 	#debug(f"MQTT log: {level=}, {buf=}")
# 	pass


while True:
	time.sleep(10)
	log.info(f'{messages_processed=}')
	pass

