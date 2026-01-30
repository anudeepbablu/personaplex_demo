import { useState, useRef, useCallback, useEffect } from 'react';
import type { WSMessage, TranscriptEntry, ExtractedFields, SpeakingState } from '../types';

interface UseAudioStreamOptions {
  sessionId: string | null;
  onTranscript?: (entry: TranscriptEntry) => void;
  onExtraction?: (data: ExtractedFields) => void;
  onStateChange?: (state: string) => void;
  onSpeakingChange?: (speaking: SpeakingState) => void;
  onError?: (error: string) => void;
}

interface UseAudioStreamReturn {
  isConnected: boolean;
  isRecording: boolean;
  startRecording: () => Promise<void>;
  stopRecording: () => void;
  sendTextInput: (text: string) => void;
  sendControl: (action: string, payload?: any) => void;
  audioLevel: number;
}

export function useAudioStream({
  sessionId,
  onTranscript,
  onExtraction,
  onStateChange,
  onSpeakingChange,
  onError,
}: UseAudioStreamOptions): UseAudioStreamReturn {
  const [isConnected, setIsConnected] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);

  const wsRef = useRef<WebSocket | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const animationFrameRef = useRef<number | null>(null);

  // Connect WebSocket
  const connect = useCallback(() => {
    console.log('[useAudioStream] 🔌 connect() called, sessionId:', sessionId);
    
    if (!sessionId) {
      console.log('[useAudioStream] ⚠️ No sessionId, aborting connect');
      return;
    }
    
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      console.log('[useAudioStream] ⚠️ WebSocket already open, skipping');
      return;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/sessions/${sessionId}/audio`;
    console.log('[useAudioStream] 🌐 Connecting to:', wsUrl);

    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('[useAudioStream] ✅ WebSocket OPEN');
      setIsConnected(true);
    };

    ws.onclose = (event) => {
      console.log('[useAudioStream] ❌ WebSocket CLOSED, code:', event.code, 'reason:', event.reason);
      setIsConnected(false);
    };

    ws.onerror = (error) => {
      console.error('[useAudioStream] 🚨 WebSocket ERROR:', error);
      onError?.('Connection error');
    };

    ws.onmessage = (event) => {
      if (event.data instanceof Blob) {
        console.log('[useAudioStream] 🔊 Received audio blob, size:', event.data.size, 'bytes');
        playAudioBlob(event.data);
      } else {
        try {
          const msg: WSMessage = JSON.parse(event.data);
          console.log('[useAudioStream] 📩 Received message:', msg.type, msg);
          handleMessage(msg);
        } catch (e) {
          console.error('[useAudioStream] Failed to parse message:', e, 'raw:', event.data);
        }
      }
    };

    wsRef.current = ws;
  }, [sessionId, onError]);

  // Handle incoming messages
  const handleMessage = useCallback((msg: WSMessage) => {
    switch (msg.type) {
      case 'transcript':
        onTranscript?.({
          speaker: msg.speaker,
          text: msg.text,
          timestamp: msg.timestamp,
        });
        break;

      case 'extraction':
        onExtraction?.(msg.data);
        break;

      case 'state':
        onStateChange?.(msg.state);
        break;

      case 'speaking':
        onSpeakingChange?.({
          user_speaking: msg.user_speaking,
          agent_speaking: msg.agent_speaking,
        });
        break;

      case 'error':
        onError?.(msg.message);
        break;

      case 'info':
        console.log('Server info:', msg.message);
        break;
    }
  }, [onTranscript, onExtraction, onStateChange, onSpeakingChange, onError]);

  // Play audio from raw PCM bytes (Int16Array)
  const playAudioBlob = async (blob: Blob) => {
    try {
      const arrayBuffer = await blob.arrayBuffer();
      
      // Backend sends raw 16-bit PCM at 24kHz
      const int16Array = new Int16Array(arrayBuffer);
      const float32Array = new Float32Array(int16Array.length);
      
      // Convert Int16 to Float32 (-1.0 to 1.0)
      for (let i = 0; i < int16Array.length; i++) {
        float32Array[i] = int16Array[i] / 32768.0;
      }
      
      // Create audio buffer and play
      const audioContext = new AudioContext({ sampleRate: 24000 });
      const audioBuffer = audioContext.createBuffer(1, float32Array.length, 24000);
      audioBuffer.getChannelData(0).set(float32Array);
      
      const source = audioContext.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioContext.destination);
      source.start();
    } catch (e) {
      console.error('Failed to play audio:', e);
    }
  };

  // Start recording
  const startRecording = useCallback(async () => {
    console.log('[useAudioStream] 🎤 startRecording() called');
    console.log('[useAudioStream] WebSocket state:', wsRef.current?.readyState, '(0=CONNECTING, 1=OPEN, 2=CLOSING, 3=CLOSED)');
    
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.log('[useAudioStream] WebSocket not ready, connecting first...');
      connect();
      await new Promise(resolve => setTimeout(resolve, 500));
      console.log('[useAudioStream] After wait, WebSocket state:', wsRef.current?.readyState);
    }

    try {
      console.log('[useAudioStream] 🎙️ Requesting microphone access...');
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 24000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      console.log('[useAudioStream] ✅ Microphone access granted');

      mediaStreamRef.current = stream;

      // Set up audio context and analyser
      const audioContext = new AudioContext({ sampleRate: 24000 });
      audioContextRef.current = audioContext;
      console.log('[useAudioStream] AudioContext created, sampleRate:', audioContext.sampleRate);

      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      analyserRef.current = analyser;
      source.connect(analyser);

      // Create processor for sending audio
      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      let audioChunkCount = 0;
      processor.onaudioprocess = (e) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          const inputData = e.inputBuffer.getChannelData(0);
          const pcmData = new Int16Array(inputData.length);

          for (let i = 0; i < inputData.length; i++) {
            pcmData[i] = Math.max(-32768, Math.min(32767, inputData[i] * 32768));
          }

          wsRef.current.send(pcmData.buffer);
          audioChunkCount++;
          if (audioChunkCount % 50 === 1) {
            console.log('[useAudioStream] 📤 Sent audio chunk #', audioChunkCount, 'size:', pcmData.byteLength, 'bytes');
          }
        }
      };

      source.connect(processor);
      processor.connect(audioContext.destination);

      // Start audio level monitoring
      const updateAudioLevel = () => {
        if (analyserRef.current) {
          const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
          analyserRef.current.getByteFrequencyData(dataArray);
          const avg = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
          setAudioLevel(avg / 255);
        }
        animationFrameRef.current = requestAnimationFrame(updateAudioLevel);
      };
      updateAudioLevel();

      setIsRecording(true);
      console.log('[useAudioStream] ✅ Recording started successfully');
    } catch (error) {
      console.error('[useAudioStream] 🚨 Failed to start recording:', error);
      onError?.('Failed to access microphone');
    }
  }, [connect, onError]);

  // Stop recording and close connection
  const stopRecording = useCallback(() => {
    console.log('[useAudioStream] 🛑 stopRecording() called');
    
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }

    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
      console.log('[useAudioStream] Audio processor disconnected');
    }

    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
      console.log('[useAudioStream] AudioContext closed');
    }

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(track => track.stop());
      mediaStreamRef.current = null;
      console.log('[useAudioStream] Media stream stopped');
    }

    // Close WebSocket to stop receiving audio from PersonaPlex
    if (wsRef.current) {
      console.log('[useAudioStream] Closing WebSocket connection');
      wsRef.current.close();
      wsRef.current = null;
    }

    // Reset speaking state
    onSpeakingChange?.({ user_speaking: false, agent_speaking: false });

    setIsConnected(false);
    setIsRecording(false);
    setAudioLevel(0);
    console.log('[useAudioStream] ✅ Recording stopped and connection closed');
  }, [onSpeakingChange]);

  // Send text input (for simulation mode)
  const sendTextInput = useCallback((text: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'text_input',
        text,
      }));
    }
  }, []);

  // Send control message
  const sendControl = useCallback((action: string, payload?: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        action,
        ...payload,
      }));
    }
  }, []);

  // Connect when sessionId changes
  useEffect(() => {
    if (sessionId) {
      connect();
    }

    return () => {
      stopRecording();
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [sessionId, connect, stopRecording]);

  return {
    isConnected,
    isRecording,
    startRecording,
    stopRecording,
    sendTextInput,
    sendControl,
    audioLevel,
  };
}
