#!/usr/bin/python3
from GPX import gpx_server, GPX

if __name__ == '__main__':
    
    # run a GPX web server 
    gpx_server(sample_rate=10, max_aggregation_length=500, port=8080)