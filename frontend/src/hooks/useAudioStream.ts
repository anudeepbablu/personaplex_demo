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
    if (!sessionId || wsRef.current?.readyState === WebSocket.OPEN) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/sessions/${sessionId}/audio`;

    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('WebSocket connected');
      setIsConnected(true);
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setIsConnected(false);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      onError?.('Connection error');
    };

    ws.onmessage = (event) => {
      if (event.data instanceof Blob) {
        // Audio data from agent - play it
        playAudioBlob(event.data);
      } else {
        try {
          const msg: WSMessage = JSON.parse(event.data);
          handleMessage(msg);
        } catch (e) {
          console.error('Failed to parse message:', e);
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

  // Play audio blob
  const playAudioBlob = async (blob: Blob) => {
    try {
      const arrayBuffer = await blob.arrayBuffer();
      const audioContext = new AudioContext({ sampleRate: 24000 });
      const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
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
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      connect();
      await new Promise(resolve => setTimeout(resolve, 500));
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 24000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });

      mediaStreamRef.current = stream;

      // Set up audio context and analyser
      const audioContext = new AudioContext({ sampleRate: 24000 });
      audioContextRef.current = audioContext;

      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      analyserRef.current = analyser;
      source.connect(analyser);

      // Create processor for sending audio
      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (e) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          const inputData = e.inputBuffer.getChannelData(0);
          const pcmData = new Int16Array(inputData.length);

          for (let i = 0; i < inputData.length; i++) {
            pcmData[i] = Math.max(-32768, Math.min(32767, inputData[i] * 32768));
          }

          wsRef.current.send(pcmData.buffer);
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
    } catch (error) {
      console.error('Failed to start recording:', error);
      onError?.('Failed to access microphone');
    }
  }, [connect, onError]);

  // Stop recording
  const stopRecording = useCallback(() => {
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }

    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }

    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(track => track.stop());
      mediaStreamRef.current = null;
    }

    setIsRecording(false);
    setAudioLevel(0);
  }, []);

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
