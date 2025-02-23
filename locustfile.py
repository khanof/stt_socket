from locust import HttpUser, task, between
import websocket
import time
import numpy as np

class WebSocketUser(HttpUser):
    wait_time = between(1, 5)

    def on_start(self):
        self.audio_data = np.random.randint(-32768, 32767, 16000, dtype=np.int16).tobytes()

    @task
    def test_websocket(self):
        ws = websocket.WebSocket()
        ws.connect("ws://localhost:8080/ws")
        
        start_time = time.time()
        ws.send_binary(self.audio_data)
        result = ws.recv()
        latency = (time.time() - start_time) * 1000
        
        if "Error" in result:
            self.environment.events.request_failure.fire(
                request_type="WebSocket", name="transcribe", response_time=latency, exception=None
            )
        else:
            self.environment.events.request_success.fire(
                request_type="WebSocket", name="transcribe", response_time=latency, response_length=len(result)
            )
        
        ws.close()