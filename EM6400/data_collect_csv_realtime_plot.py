import minimalmodbus
import time
import struct
import datetime
import os
import json
import webbrowser
import paste.urlparser
import gevent
from gevent_zeromq import zmq
from geventwebsocket.handler import WebSocketHandler

from ctypes import *
threshold_time=900
global start_time
start_time=int(time.time())
global now
now=datetime.datetime.now()
global start_date
start_day=now.day
global start_month
start_month=now.month
global count
count=0
global f

def convert(s):
	return struct.unpack("<f",struct.pack("<I",s))[0]
    
def main():
	'''Set up zmq context and greenlets for all the servers, then launch the web
	browser and run the data producer'''
	context = zmq.Context()
    
    

	# zeromq: tcp to inproc gateway
	gevent.spawn(zmq_server, context)
	# websocket server: copies inproc zmq messages to websocket
	ws_server = gevent.pywsgi.WSGIServer(
        ('', 9999), WebSocketApp(context),
        handler_class=WebSocketHandler)
    # http server: serves up static files
	http_server = gevent.pywsgi.WSGIServer(
        ('', 8000),
        paste.urlparser.StaticURLParser(os.path.dirname(__file__)))
	# Start the server greenlets
	http_server.start()
	ws_server.start()
	# Open a couple of webbrowsers
	#webbrowser.open('http://localhost:8000/graph.html')
    #webbrowser.open('http://localhost:8000/graph.html')
    # Kick off the producer
    
	instrument = minimalmodbus.Instrument('/dev/ttyUSB0', 1)
	instrument.serial.baudrate = 19200   # Baud
	#instrument.debug = True
	




	global f
	if not os.path.exists('/root/data/'+str(start_day)+"_"+str(start_month)):
		os.makedirs('/root/data/'+str(start_day)+"_"+str(start_month))
	f=open("/root/data/"+str(start_day)+"_"+str(start_month)+"/0.csv","wa")
	#count=0
	zmq_producer(context,instrument)

def zmq_server(context):
   	'''Funnel messages coming from the external tcp socket to an inproc socket'''
	sock_incoming = context.socket(zmq.SUB)
	sock_outgoing = context.socket(zmq.PUB)
   	sock_incoming.bind('tcp://*:5000')
   	sock_outgoing.bind('inproc://queue')
   	sock_incoming.setsockopt(zmq.SUBSCRIBE, "")
   	while True:
   		msg = sock_incoming.recv()
        sock_outgoing.send(msg)

class WebSocketApp(object):
    '''Funnel messages coming from an inproc zmq socket to the websocket'''

    def __init__(self, context):
        self.context = context

    def __call__(self, environ, start_response):
        ws = environ['wsgi.websocket']
        sock = self.context.socket(zmq.SUB)
        sock.setsockopt(zmq.SUBSCRIBE, "")
        sock.connect('inproc://queue')
        while True:
            msg = sock.recv()
            ws.send(msg)

def zmq_producer(context,instrument):
    '''Produce a nice time series sine wave'''
    socket = context.socket(zmq.PUB)
    socket.connect('tcp://127.0.0.1:5000')

    while True:
		now_time=int(time.time())
		now=datetime.datetime.now()
		now_day=now.day
		now_month=now.month
		global start_time
		global start_day
		global count
		global f
		if ((now_time-start_time) > threshold_time) or (now_day>start_day):
			if now_day>start_day:
				count=-1
			count=count+1
			start_time=now_time
			start_day=now_day
			start_month=now_month
			f.close()
			if not os.path.exists('/root/data/'+str(start_day)+"_"+str(start_month)):
				os.makedirs('/root/data/'+str(start_day)+"_"+str(start_month))
			f=open("/root/data/"+str(start_day)+"_"+str(start_month)+"/"+str(count)+".csv","wa")

		else:
			try:
				readings_array = instrument.read_registers(3900,80)
				row=str(now_time)+","
				for i in range(0,len(readings_array)-1,2):
					a=(readings_array[i+1]<<16) +readings_array[i]
					row=row+str(convert(a))+","
				row=	row[:-1]+"\n"
				
				f.write(row)
				x = time.time() * 1000+19800000
				y=float(row.split(",")[2])
				socket.send(json.dumps(dict(x=x, y=y)))
				gevent.sleep(0.5)		
			except Exception as e:
				print e
				print time.time() 
				instrument = minimalmodbus.Instrument('/dev/ttyUSB0', 1)		

	
if __name__ == '__main__':
	main()

	

	

