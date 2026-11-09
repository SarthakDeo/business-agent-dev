/**
 * Browser Audio Recorder for Voice2Flow Prisma STT.
 * Captures microphone audio, computes real-time volume levels,
 * encodes standard 16kHz 16-bit mono PCM WAV bytes, and maintains
 * an in-browser Web Speech fallback when Prisma STT is unconfigured.
 */

export class AudioRecorder {
  private mediaStream: MediaStream | null = null;
  private audioContext: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private scriptProcessor: ScriptProcessorNode | null = null;
  private pcmBuffers: Float32Array[] = [];
  private recording = false;
  private targetSampleRate = 16000;
  private browserTranscript = "";
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private recognition: any = null;

  async start(): Promise<void> {
    if (this.recording) return;

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error(
        "Microphone access is not supported by this browser. You can use text input instead."
      );
    }

    try {
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
    } catch (err: unknown) {
      const errName = (err as Error)?.name || "";
      if (errName === "NotAllowedError" || errName === "PermissionDeniedError") {
        throw new Error(
          "Microphone access is required for voice input. You can enable microphone access in your browser settings, or use text input instead."
        );
      }
      if (errName === "NotFoundError" || errName === "DevicesNotFoundError") {
        throw new Error(
          "No microphone found on your system. Please connect a microphone or use text input."
        );
      }
      throw new Error(
        "Could not access microphone. Please check your device permissions or use text input instead."
      );
    }

    const AudioContextClass =
      window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;

    this.audioContext = new AudioContextClass();
    const sourceNode = this.audioContext.createMediaStreamSource(this.mediaStream);

    this.analyser = this.audioContext.createAnalyser();
    this.analyser.fftSize = 256;
    sourceNode.connect(this.analyser);

    // Buffer audio samples for standard WAV export
    this.pcmBuffers = [];
    const bufferSize = 4096;
    this.scriptProcessor = this.audioContext.createScriptProcessor(bufferSize, 1, 1);

    this.scriptProcessor.onaudioprocess = (e) => {
      if (!this.recording) return;
      const channelData = e.inputBuffer.getChannelData(0);
      this.pcmBuffers.push(new Float32Array(channelData));
    };

    sourceNode.connect(this.scriptProcessor);
    this.scriptProcessor.connect(this.audioContext.destination);

    // Initialize Web Speech API fallback for resilience if available
    this.browserTranscript = "";
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const WinAny = window as any;
    const SpeechRec = WinAny.SpeechRecognition || WinAny.webkitSpeechRecognition;
    if (SpeechRec) {
      try {
        this.recognition = new SpeechRec();
        this.recognition.continuous = true;
        this.recognition.interimResults = true;
        this.recognition.lang = "en-IN";
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        this.recognition.onresult = (event: any) => {
          let text = "";
          for (let i = 0; i < event.results.length; i++) {
            text += event.results[i][0].transcript + " ";
          }
          this.browserTranscript = text.trim();
        };
        this.recognition.onerror = () => {};
        this.recognition.start();
      } catch {
        this.recognition = null;
      }
    }

    this.recording = true;
  }

  getAudioLevel(): number {
    if (!this.analyser || !this.recording) return 0;
    const dataArray = new Uint8Array(this.analyser.frequencyBinCount);
    this.analyser.getByteFrequencyData(dataArray);

    let sum = 0;
    for (let i = 0; i < dataArray.length; i++) {
      sum += dataArray[i];
    }
    const avg = sum / dataArray.length;
    // Normalize to 0.0 - 1.0 range
    return Math.min(1, Math.max(0, avg / 128));
  }

  getBrowserTranscript(): string {
    return this.browserTranscript;
  }

  async stop(): Promise<Blob> {
    if (!this.recording) {
      throw new Error("Recording is not active");
    }

    this.recording = false;
    const inputSampleRate = this.audioContext ? this.audioContext.sampleRate : 44100;

    if (this.recognition) {
      try {
        this.recognition.stop();
      } catch {
        // ignore
      }
    }

    // Clean up nodes and stream tracks
    if (this.scriptProcessor) {
      this.scriptProcessor.disconnect();
      this.scriptProcessor = null;
    }
    if (this.analyser) {
      this.analyser.disconnect();
      this.analyser = null;
    }
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => track.stop());
      this.mediaStream = null;
    }
    if (this.audioContext && this.audioContext.state !== "closed") {
      await this.audioContext.close();
      this.audioContext = null;
    }

    // Merge buffers
    const totalLength = this.pcmBuffers.reduce((acc, b) => acc + b.length, 0);
    if (totalLength === 0) {
      throw new Error("No speech audio was captured. Please speak again.");
    }

    const merged = new Float32Array(totalLength);
    let offset = 0;
    for (const b of this.pcmBuffers) {
      merged.set(b, offset);
      offset += b.length;
    }
    this.pcmBuffers = [];

    // Resample to 16,000 Hz for standard Voice2Flow / Prisma STT input
    const resampled = this.resample(merged, inputSampleRate, this.targetSampleRate);

    // Encode to 16-bit PCM WAV Blob
    return this.encodeWAV(resampled, this.targetSampleRate);
  }

  cancel(): void {
    this.recording = false;
    this.pcmBuffers = [];
    if (this.recognition) {
      try {
        this.recognition.stop();
      } catch {
        // ignore
      }
      this.recognition = null;
    }
    if (this.scriptProcessor) {
      this.scriptProcessor.disconnect();
      this.scriptProcessor = null;
    }
    if (this.analyser) {
      this.analyser.disconnect();
      this.analyser = null;
    }
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => track.stop());
      this.mediaStream = null;
    }
    if (this.audioContext && this.audioContext.state !== "closed") {
      this.audioContext.close().catch(() => {});
      this.audioContext = null;
    }
  }

  isRecording(): boolean {
    return this.recording;
  }

  private resample(input: Float32Array, inRate: number, outRate: number): Float32Array {
    if (inRate === outRate) return input;
    const ratio = inRate / outRate;
    const outLength = Math.round(input.length / ratio);
    const result = new Float32Array(outLength);

    for (let i = 0; i < outLength; i++) {
      const srcIdx = i * ratio;
      const lower = Math.floor(srcIdx);
      const upper = Math.min(lower + 1, input.length - 1);
      const fraction = srcIdx - lower;
      result[i] = input[lower] * (1 - fraction) + input[upper] * fraction;
    }
    return result;
  }

  private encodeWAV(samples: Float32Array, sampleRate: number): Blob {
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);

    const writeString = (view: DataView, offset: number, string: string) => {
      for (let i = 0; i < string.length; i++) {
        view.setUint8(offset + i, string.charCodeAt(i));
      }
    };

    // RIFF chunk descriptor
    writeString(view, 0, "RIFF");
    view.setUint32(4, 36 + samples.length * 2, true);
    writeString(view, 8, "WAVE");

    // fmt sub-chunk (16-bit mono PCM)
    writeString(view, 12, "fmt ");
    view.setUint32(16, 16, true); // SubChunk1Size
    view.setUint16(20, 1, true); // AudioFormat: 1 = PCM
    view.setUint16(22, 1, true); // NumChannels: 1 = Mono
    view.setUint32(24, sampleRate, true); // SampleRate (16000)
    view.setUint32(28, sampleRate * 2, true); // ByteRate (16000 * 2)
    view.setUint16(32, 2, true); // BlockAlign (2 bytes)
    view.setUint16(34, 16, true); // BitsPerSample: 16

    // data sub-chunk
    writeString(view, 36, "data");
    view.setUint32(40, samples.length * 2, true);

    // Write 16-bit PCM samples
    let offset = 44;
    for (let i = 0; i < samples.length; i++, offset += 2) {
      const s = Math.max(-1, Math.min(1, samples[i]));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    }

    return new Blob([buffer], { type: "audio/wav" });
  }
}
