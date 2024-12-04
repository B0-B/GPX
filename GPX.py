#!/usr/bin/python3
from http.server import SimpleHTTPRequestHandler
import json
import os
import socket
import socketserver
from typing import Callable
import GPUtil
from time import sleep, time_ns, perf_counter_ns
from threading import Thread, Event
from pathlib import Path

# Resolve all paths.
__root__ = Path(__file__).resolve().parent
__static__ = __root__.joinpath('static')

class GPX:

    '''
    GPU monitoring utility which exposes GPU information in a web UI.
    '''

    # globally accessible object
    device_map = dict()
    smoothing = 0.3

    def __init__(self, sample_rate: str|None=10, max_aggregation_length: int=1000) -> None:

        # Read kwargs.
        self.sample_rate = sample_rate
        self.max_aggregation_length = max_aggregation_length

        # Device management.
        self.device_count: int
        
        # Monitoring parameters.
        self.read_latency: int
        self.monitoring_active = False

        # Initialize devices and device map
        self.init_devices()
        self.calibrate()

    def init_devices (self) -> None:
        
        # Get all found GPU pointers.
        device_list = GPUtil.getGPUs()
        self.device_count = len(device_list)

        # Iterate through all pointer devices and initialize cache for each.
        for device in device_list:
            
            id = int(device.id)

            # Init entry in device map
            GPX.device_map[id] = dict() # device entry
            GPX.device_map[id]['id'] = id
            GPX.device_map[id]['name'] = device.name
            GPX.device_map[id]['memory'] = device.memoryTotal
            GPX.device_map[id]['driver'] = device.driver
            GPX.device_map[id]['engine_usage_timeseries'] = [0 for _ in range(self.max_aggregation_length)]
            GPX.device_map[id]['memory_usage_timeseries'] = [0 for _ in range(self.max_aggregation_length)]

    def read_all (self) -> None:

        '''
        Reads all device states and updates the device map.
        '''

        # Make new reading.
        device_list = GPUtil.getGPUs()

        # Append values.
        for device in device_list:
            
            # Extract values
            id = device.id
            gpu_utilization  = round(device.load * 100, 1)
            vram_utilization = round(device.memoryUtil * 100, 1)

            # Apply exponential smoothing
            if GPX.smoothing:
                gpu_utilization = (1-GPX.smoothing) * gpu_utilization + GPX.smoothing * GPX.device_map[id]['engine_usage_timeseries'][-1]
                vram_utilization = (1-GPX.smoothing) * vram_utilization + GPX.smoothing * GPX.device_map[id]['memory_usage_timeseries'][-1]

            # append to timeseries cache
            GPX.device_map[id]['engine_usage_timeseries'].append(gpu_utilization)
            GPX.device_map[id]['memory_usage_timeseries'].append(vram_utilization)

            # trim the timeseries cache to allowed length to prevent overflows
            if len(GPX.device_map[id]['engine_usage_timeseries']) >= self.max_aggregation_length:
                GPX.device_map[id]['engine_usage_timeseries'] = GPX.device_map[id]['engine_usage_timeseries'][-self.max_aggregation_length:]
                GPX.device_map[id]['memory_usage_timeseries'] = GPX.device_map[id]['memory_usage_timeseries'][-self.max_aggregation_length:]

    def show_all (self) -> None:

        '''
        Shows the GPU and vRAM utilization for all devices in the console.
        '''

        os.system('cls' if os.name=='nt' else 'clear')

        for id, device in GPX.device_map.items():

            print(f"id: {id}   GPU: {device['engine_usage_timeseries'][-1]}%   vRAM: {device['memory_usage_timeseries'][-1]}%")

    def calibrate (self) -> None:

        start = perf_counter_ns()
        self.read_all()
        stop = perf_counter_ns()

        self.read_latency = stop - start

    def monitor_all (self, sample_rate: float|int|None=None, max_aggregation_length: int|None=None, print_to_console:bool=False) -> None:

        '''
        Monitoring method which tracks all GPUs continuously in a loop.

        [Parameter]

        sample_rate:                  reading sample_rate in Hz

        max_aggregation_length:     optional, can be overriden in main object to set the maximum timeseries length
        '''

        if max_aggregation_length is not None:
            self.max_aggregation_length = max_aggregation_length
        if sample_rate is not None:
            self.sample_rate = sample_rate

        self.monitoring_active = True

        period_ns = 1e9 / self.sample_rate
        period_corrected = period_ns - self.read_latency
        period_s = 1e-9 * period_corrected
        delay = 0 if period_s <= 0 else period_s

        while self.monitoring_active:

            self.read_all()
            
            self.show_all() if print_to_console else None
                
            sleep(delay)
   
def gpx_server (sample_rate: str | None = 10, max_aggregation_length: int = 1000, port: int=8080) -> None:

    '''
    Will start a GPX web server exposed on local IP and provided port.

    [Parameter]

    sample_rate:                The sampling rate for reading GPU states in Hz.

    max_aggregation_length:     The total cache size, or timeseries values to store per GPU.
    
    port:                       TCP port.
    '''

    try:

        gpx = GPX(sample_rate, max_aggregation_length)

        # Init monitor as thread
        monitor = thread(gpx.monitor_all, 0)
        monitor.start()

        # Override localhost with local IP address.
        sleep(1) # delay
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        host = s.getsockname()[0] # Local IP Address
        s.close()

        # start server (blocking)
        os.chdir(__static__) # change into static directory
        socketserver.TCPServer.allow_reuse_address = True
        with socketserver.TCPServer((host, port), handler) as httpd:
            print(f'📡 serving GPX server at http://{host}:{port}\n')
            httpd.serve_forever()
    
    except KeyboardInterrupt:

        monitor.stop()
        gpx.monitoring_active = False
        httpd.shutdown()
        exit()

class thread (Thread):

    '''
    Thread implementation.
    '''

    # If disabled will stop all threads
    __threads_active__: bool = True

    def __init__ (self, function: Callable, wait: int, *args):

        Thread.__init__(self)

        self.wait = wait
        
        self.func = function
        self.args = args

        self.stoprequest = Event()

    def run (self, freq=10, repeat=True):

        while not self.stoprequest.is_set():
            try: # important during init, otherwise crash
                self.func(*self.args)
                if not repeat:
                    break
                # listen frequently during waiting
                for _ in range(freq*self.wait):
                    if self.stoprequest.is_set():
                        break
                    elif not self.__threads_active__:
                        self.stop()
                        break
                    sleep(1/freq)
                if not self.__threads_active__:
                    break
            except:
                pass

    def stop (self):

        self.stoprequest.set()
        # super(thread, self).join(timeout)

class handler (SimpleHTTPRequestHandler):

    '''
    Automatic REST API handler.
    '''
    
    def do_GET(self):
        
        '''
        Load static web page.
        '''

        return SimpleHTTPRequestHandler.do_GET(self)
    
    def do_POST(self):

        '''
        JSON REST API.
        '''

        # response structure
        response = {
            'data': {},     # aggregated timeseries
            'errors': []
        }

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

        # API code here
        response['data'] = GPX.device_map

        # encode to json
        encoded = json.dumps(response).encode('utf-8')

        # send
        self.wfile.write(encoded)