import React, { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import { api, apiBlob } from "./api.js";

const MAX_FILES = 10;
const MAX_BYTES = 100 * 1024 * 1024;

function Icon({ name }) {
  const common = { width: 22, height: 22, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round" };
  if (name === "plus") return <svg {...common}><path d="M12 5v14M5 12h14" /></svg>;
  if (name === "mic") return <svg {...common}><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M6 11a6 6 0 0 0 12 0M12 17v4" /></svg>;
  if (name === "send") return <svg {...common} strokeWidth="2.2"><path d="M12 19V5M6 11l6-6 6 6" /></svg>;
  if (name === "close") return <svg {...common}><path d="M6 6l12 12M18 6L6 18" /></svg>;
  if (name === "stop") return <svg {...common}><rect x="7" y="7" width="10" height="10" rx="1.5" fill="currentColor" stroke="none" /></svg>;
  return null;
}

function audioFilename(mime) {
  if (mime.includes("mp4")) return "voice.m4a";
  if (mime.includes("ogg")) return "voice.ogg";
  if (mime.includes("wav")) return "voice.wav";
  return "voice.webm";
}

function pickRecorderMime() {
  const types = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"];
  return types.find((type) => window.MediaRecorder?.isTypeSupported?.(type)) || "";
}

function appendTranscription(current, segment) {
  if (!current) return segment;
  if (current.endsWith("\n")) return current + segment;
  return `${current} ${segment}`;
}

function formatClock(seconds) {
  const value = Math.max(0, Math.floor(seconds));
  return `${Math.floor(value / 60)}:${String(value % 60).padStart(2, "0")}`;
}

export const Composer = forwardRef(function Composer({ disabled, status, onSend }, ref) {
  const [text, setText] = useState("");
  const [files, setFiles] = useState([]);
  const [voices, setVoices] = useState([]);
  const [menu, setMenu] = useState(false);
  const [phase, setPhase] = useState("idle");
  const [seconds, setSeconds] = useState(0);
  const [note, setNote] = useState("");
  const fileRef = useRef(null);
  const photoRef = useRef(null);
  const cameraRef = useRef(null);
  const recorder = useRef(null);
  const chunks = useRef([]);
  const stream = useRef(null);
  const filesRef = useRef(files);
  filesRef.current = files;

  useEffect(() => () => {
    filesRef.current.forEach((item) => item.preview && URL.revokeObjectURL(item.preview));
    stopStream();
  }, []);

  useEffect(() => {
    if (phase !== "recording") return undefined;
    const timer = setInterval(() => setSeconds((value) => value + 1), 1000);
    return () => clearInterval(timer);
  }, [phase]);

  function stopStream() {
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
  }

  function addFiles(list) {
    const incoming = [...(list || [])];
    if (!incoming.length) return;
    setFiles((current) => {
      const next = [...current];
      for (const file of incoming) {
        if (next.length >= MAX_FILES) {
          setNote(`Не больше ${MAX_FILES} файлов`);
          break;
        }
        if (file.size > MAX_BYTES) {
          setNote(`${file.name} больше 100 МБ`);
          continue;
        }
        const preview = file.type.startsWith("image/") ? URL.createObjectURL(file) : "";
        next.push({ id: crypto.randomUUID(), file, preview });
      }
      return next;
    });
  }

  useImperativeHandle(ref, () => ({ addFiles }));

  function removeFile(id) {
    setFiles((current) => {
      const item = current.find((entry) => entry.id === id);
      if (item?.preview) URL.revokeObjectURL(item.preview);
      return current.filter((entry) => entry.id !== id);
    });
  }

  async function startRecording() {
    setNote("");
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setNote("Запись голоса в этом браузере недоступна");
      return;
    }
    try {
      const live = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.current = live;
      const mime = pickRecorderMime();
      const media = mime ? new MediaRecorder(live, { mimeType: mime }) : new MediaRecorder(live);
      chunks.current = [];
      media.ondataavailable = (event) => {
        if (event.data.size) chunks.current.push(event.data);
      };
      media.onstop = () => finishRecording(media.mimeType || mime || "audio/webm");
      recorder.current = media;
      setSeconds(0);
      setPhase("recording");
      media.start();
    } catch (error) {
      stopStream();
      setNote(error.name === "NotAllowedError" ? "Нет доступа к микрофону" : "Не удалось начать запись");
    }
  }

  function cancelRecording() {
    const media = recorder.current;
    recorder.current = null;
    if (media && media.state !== "inactive") media.onstop = null;
    if (media && media.state !== "inactive") media.stop();
    stopStream();
    setPhase("idle");
  }

  function stopRecording() {
    const media = recorder.current;
    if (media && media.state !== "inactive") media.stop();
  }

  async function finishRecording(mime) {
    stopStream();
    recorder.current = null;
    const blob = new Blob(chunks.current, { type: mime });
    chunks.current = [];
    if (!blob.size) {
      setPhase("idle");
      setNote("Пустая запись");
      return;
    }
    setPhase("transcribing");
    try {
      const body = new FormData();
      const name = audioFilename(mime);
      body.append("audio", blob, name);
      body.append("client_transcription_id", crypto.randomUUID());
      const data = await api("/api/query/voice/transcribe", { method: "POST", body });
      const transcription = (data.transcription || "").trim();
      setVoices((current) => [...current, {
        id: crypto.randomUUID(),
        blob,
        name,
        transcription,
      }]);
      if (transcription) {
        setText((current) => appendTranscription(current, transcription));
      }
      setNote("");
    } catch (error) {
      setVoices((current) => [...current, {
        id: crypto.randomUUID(),
        blob,
        name: audioFilename(mime),
        transcription: "",
      }]);
      setNote(error.message || "Не удалось распознать речь");
    } finally {
      setPhase("idle");
    }
  }

  const canSend = !disabled && phase === "idle" && (text.trim() || files.length || voices.length);

  async function submit(event) {
    event.preventDefault();
    if (!canSend) return;
    const payload = {
      text: text.trim(),
      files: files.map((item) => item.file),
      voices: voices.map((item) => ({ blob: item.blob, name: item.name, transcription: item.transcription })),
    };
    try {
      await onSend(payload);
    } catch {
      return;
    }
    files.forEach((item) => item.preview && URL.revokeObjectURL(item.preview));
    setText("");
    setFiles([]);
    setVoices([]);
    setNote("");
    setMenu(false);
  }

  const shownStatus = phase === "recording"
    ? `Запись ${formatClock(seconds)}`
    : phase === "transcribing"
      ? "Распознаём…"
      : status || note;

  return (
    <form className={`composer-panel ${phase === "recording" ? "recording" : ""}`} onSubmit={submit}>
      {(files.length > 0 || voices.length > 0) && (
        <div className="chips">
          {files.map((item) => (
            <div className="chip" key={item.id}>
              {item.preview ? <img src={item.preview} alt="" /> : <span>{item.file.name}</span>}
              <button type="button" className="chip-x" aria-label="Убрать файл" onClick={() => removeFile(item.id)}><Icon name="close" /></button>
            </div>
          ))}
          {voices.map((item) => (
            <div className="chip voice" key={item.id}>
              <span>Голос</span>
              <button type="button" className="chip-x" aria-label="Убрать голосовое" onClick={() => setVoices((current) => current.filter((entry) => entry.id !== item.id))}><Icon name="close" /></button>
            </div>
          ))}
        </div>
      )}
      {phase !== "recording" && (
        <textarea
          rows={1}
          value={text}
          disabled={disabled || phase === "transcribing"}
          placeholder={phase === "transcribing" ? "Распознаём…" : "Сообщение"}
          onChange={(event) => setText(event.target.value)}
          onPaste={(event) => {
            const pasted = [...(event.clipboardData?.files || [])];
            if (pasted.length) {
              event.preventDefault();
              addFiles(pasted);
            }
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              event.currentTarget.form?.requestSubmit();
            }
          }}
        />
      )}
      {shownStatus && <p className="composer-status">{shownStatus}</p>}
      <div className="composer-tools">
        {phase === "recording" ? (
          <>
            <span className="rec-dot" />
            <strong>{formatClock(seconds)}</strong>
            <span className="spacer" />
            <button type="button" className="icon-btn" aria-label="Отменить запись" onClick={cancelRecording}><Icon name="close" /></button>
            <button type="button" className="icon-btn" aria-label="Остановить запись" onClick={stopRecording}><Icon name="stop" /></button>
          </>
        ) : (
          <>
            <button type="button" className="icon-btn" aria-label="Прикрепить" disabled={disabled} onClick={() => setMenu((open) => !open)}><Icon name="plus" /></button>
            {menu && (
              <div className="attach-menu">
                <button type="button" onClick={() => { setMenu(false); photoRef.current?.click(); }}>Фото и видео</button>
                <button type="button" onClick={() => { setMenu(false); cameraRef.current?.click(); }}>Камера</button>
                <button type="button" onClick={() => { setMenu(false); fileRef.current?.click(); }}>Файл</button>
              </div>
            )}
            <span className="spacer" />
            <button type="button" className="icon-btn" aria-label="Записать голосовое" disabled={disabled || phase !== "idle"} onClick={startRecording}><Icon name="mic" /></button>
            <button type="submit" className="composer-send" aria-label="Отправить" disabled={!canSend}><Icon name="send" /></button>
          </>
        )}
      </div>
      <input ref={photoRef} type="file" accept="image/*,video/*" multiple hidden onChange={(event) => { addFiles(event.target.files); event.target.value = ""; }} />
      <input ref={cameraRef} type="file" accept="image/*" capture="environment" hidden onChange={(event) => { addFiles(event.target.files); event.target.value = ""; }} />
      <input ref={fileRef} type="file" multiple hidden onChange={(event) => { addFiles(event.target.files); event.target.value = ""; }} />
    </form>
  );
});

export function MessageAttachments({ attachments }) {
  const [urls, setUrls] = useState({});
  useEffect(() => {
    let cancel = false;
    const created = [];
    (async () => {
      const next = {};
      for (const item of attachments || []) {
        if (!item.download_url) continue;
        try {
          const blob = await apiBlob(item.download_url);
          const url = URL.createObjectURL(blob);
          created.push(url);
          next[item.id] = url;
        } catch {
          next[item.id] = "";
        }
      }
      if (!cancel) setUrls(next);
    })();
    return () => {
      cancel = true;
      created.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [attachments]);

  if (!attachments?.length) return null;
  return (
    <div className="msg-files">
      {attachments.map((item) => {
        const url = urls[item.id];
        if (item.file_type === "voice" || (item.mime_type || "").startsWith("audio/")) {
          return url ? <audio key={item.id} controls src={url} /> : <span key={item.id} className="muted">Голосовое</span>;
        }
        if ((item.mime_type || "").startsWith("image/") || item.file_type === "photo") {
          return url ? <img key={item.id} src={url} alt={item.file_name || ""} /> : null;
        }
        return (
          <a key={item.id} href={url || undefined} download={item.file_name || "file"}>
            {item.file_name || "Файл"}
          </a>
        );
      })}
    </div>
  );
}
