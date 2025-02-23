const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const transcriptDiv = document.getElementById('transcript');
let mediaRecorder;
let socket;

startBtn.onclick = async () => {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    console.log('Audio stream acquired:', stream);
    
    // Use AudioContext to get raw PCM data
    const audioContext = new AudioContext({ sampleRate: 16000 });
    const source = audioContext.createMediaStreamSource(stream);
    const processor = audioContext.createScriptProcessor(16384, 1, 1);

    socket = new WebSocket('ws://localhost:8080/ws');

    socket.onopen = () => console.log('WebSocket connected');
    socket.onmessage = (event) => {
      console.log('Received transcription:', event.data);
      transcriptDiv.innerText += event.data + '\n';
    };
    socket.onerror = (error) => console.error('WebSocket error:', error);
    socket.onclose = (event) => console.log('WebSocket closed:', event.code, event.reason);

    processor.onaudioprocess = (event) => {
      const inputData = event.inputBuffer.getChannelData(0);
      const pcmData = new Int16Array(inputData.length);
      for (let i = 0; i < inputData.length; i++) {
        pcmData[i] = Math.max(-32768, Math.min(32767, inputData[i] * 32768));  // Convert float32 to int16
      }
      if (socket.readyState === WebSocket.OPEN) {
        console.log('Sending PCM chunk, size:', pcmData.buffer.byteLength);
        socket.send(pcmData.buffer);
      }
    };

    source.connect(processor);
    processor.connect(audioContext.destination);

    console.log('Audio processing started');
    startBtn.disabled = true;
    stopBtn.disabled = false;

    // Store references for cleanup
    window.audioContext = audioContext;
    window.processor = processor;
    window.source = source;
  } catch (error) {
    console.error('Failed to start recording:', error);
  }
};

stopBtn.onclick = () => {
  if (window.audioContext) {
    console.log('Stopping audio processing...');
    window.processor.disconnect();
    window.source.disconnect();
    window.audioContext.close();
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.close();
    }
    startBtn.disabled = false;
    stopBtn.disabled = true;
  }
};