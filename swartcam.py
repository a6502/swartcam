#!/usr/bin/env python3
#!/usr/bin/python3 -W all

"""

See the README.md

"""

# standad python
import configparser
from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import subprocess
import threading
from textwrap import dedent
from time import sleep, strftime
from urllib.parse import parse_qs

# pi specific
from picamera import PiCamera

# ugly  globals
config = None
camthread = None
stream_cmd = None

base_cmd = """exec ffmpeg -xerror \
-f h264 -r 15 -thread_queue_size 512 -i - \
-f alsa -thread_queue_size 512 -fflags nobuffer -itsoffset 5.5 -ac 1 -i plug:ladspa \
-vcodec copy -acodec aac -ac 2 -ab 128k -ar 44100 -map 0:0 -map 1:0 -strict experimental -f flv \
"""

class CamThread(threading.Thread):

    def __init__(self):
        super(CamThread, self).__init__()
        # should
        self.preview = threading.Event()
        self.streaming = threading.Event()
        # is
        self.doing_preview = False
        self.is_streaming = False

    def run(self):
        print('starting camera')
        with PiCamera(resolution=(1280,720), framerate=15) as camera:
            camera.awb_mode = 'incandescent' #'tungsten'
            camera.brightness = 52
            camera.drc_strength = 'high'
            #camera.exposure_mode = 'spotlight'
            camera.meter_mode = 'backlit'
            while True:
                #self.preview.wait()
                if self.preview.is_set() and not self.doing_preview:
                    print('starting preview')
                    camera.start_preview()
                    self.doing_preview = True
                elif not self.preview.is_set() and self.doing_preview:
                    print('stopping preview')
                    """ If a preview is not currently running, no exception is raised - the method will simply do nothing.  """
                    camera.stop_preview()
                    self.doing_preview = False
                if self.streaming.is_set():
                    print('calling do_stream')
                    self.do_stream(camera)
                    print('do_stream done?')
                sleep(1)

    def do_stream(self, camera):
        try:
            print('starting stream')
            ffmpeg = subprocess.Popen(
                stream_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=True)
            camera.start_recording(
                ffmpeg.stdin,
                format='h264',
                quality=28,
                bitrate=500000,
                intra_period=75,
                intra_refresh='adaptive',
                sps_timing=True,
            )
            camera.request_key_frame()

            while self.streaming.is_set():
                camera.annotate_text = strftime("%Y-%m-%d %H:%M:%S")
                camera.wait_recording(1)
            #print('stopping stream')
            #camera.stop_recording()
            #ffmpeg.stdin.close()
            #ffmpeg.terminate()
        except KeyboardInterrupt: 
            camera.stop_recording()
        finally:
            print('\nstopping stream\n')
            camera.stop_recording()
            ffmpeg.stdin.close()
            ffmpeg.terminate()
            sleep(1)
            ffmpeg.kill()
            print("\ncleaned up?\n")

class StaticServer(BaseHTTPRequestHandler):
 
    def do_GET(self):
        path, _, query_string = self.path.partition('?')
        query = parse_qs(query_string)
        
        #print(f'path {path}')
        #print(f'query {query}')
                
        if path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            out=dedent("""\
                <!doctype html>
                <html lang="en">
                  <head>
                    <meta charset="utf-8">
                    <title>SwartCamControl</title>
                  </head>
                  <body>
                    <h1>SwartCamControl</h1>
                    <p>Preview: {preview_status}</p>
                    <p>Streaming: {streaming_status}</p>
                    <div>
                      <form method="post" action="/">
                        <input type="submit" {preview_button}>
                        <input type="submit" {streaming_button}>
                      </form>
                    </div>
                  </body>
                </html>
                """)
            global camthread # being explicit
            p = camthread.preview.is_set()
            s = camthread.streaming.is_set()
            self.wfile.write(out.format(
                preview_status = 'On' if p else 'Off',
                streaming_status = 'On' if s else 'Off',
                preview_button = (
                    'name="stop_preview" value="Stop Preview" disabled' if s
                    else 'name="stop_preview" value="Stop Preview"' if p
                    else 'name="start_preview" value="Start Preview"'),
                streaming_button = (
                    'name="stop_streaming" value="Stop Streaming"' if s
                    else 'name="start_streaming" value="Start Streaming"' if p 
                    else 'name="start_streaming" value="Start Streaming" disabled'),
            ).encode())
        else:
            self._error(404, 'not found')

    def do_POST(self):
        path, _, query_string = self.path.partition('?')
        query = parse_qs(query_string, keep_blank_values=True)

        if self.headers['Content-Type'] != 'application/x-www-form-urlencoded':
            self._error(500, 'content type not supported')
            return        

        length = int(self.headers['Content-Length'])
        form_data = parse_qs(self.rfile.read(length).decode('utf-8').strip())
        
        print(f'path {path}')
        #print(f'query {query}')
        #print(f'form_data {form_data}')
        q = {**query, **form_data}
        print(f'q {q}')

        global camthread # just to be explicit

        if q.get('start_preview'):
            camthread.preview.set()
        elif q.get('stop_preview'):
            camthread.preview.clear()
        elif q.get('start_streaming'):
            camthread.streaming.set()
        elif q.get('stop_streaming'):
            camthread.streaming.clear()
        else:
            self._error(500, 'huh?')
            return
                
        self.send_response(303)
        self.send_header('Location', '/')
        self.end_headers()

    def _error(self, code, msg):
        self.send_response(code)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(msg.encode())

 
def run(server_class=HTTPServer, handler_class=StaticServer, port=8000):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print('Starting httpd on port {}'.format(port))
    httpd.serve_forever(poll_interval=1)
 
def main():
    
    global config
    config = configparser.ConfigParser()
    config.read_file(open(
        os.path.dirname(os.path.realpath(__file__)) + '/swartcam.conf'
    ))
    global base_cmd
    global stream_cmd
    stream_cmd = base_cmd + config['swartcam']['dest']
    print(f"stream_cmd {stream_cmd}")
    global camthread
    camthread = CamThread()
    camthread.start()
    run()
    print('done?')

main()

