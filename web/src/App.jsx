import React, { useEffect, useRef, useState } from "react";
import { api, loadAuth, saveAuth } from "./api.js";
import { Composer, MessageAttachments } from "./Composer.jsx";
import { Markdown } from "./markdown.jsx";
import { StructuredUI } from "./StructuredUI.jsx";

const TABS = [
  ["chats", "Чаты"],
  ["boards", "Обзор"],
  ["actions", "Экшены"],
  ["settings", "Настройки"],
];

function telegramInitData() {
  const tg = window.Telegram?.WebApp;
  tg?.ready?.();
  return tg?.initData || "";
}

export default function App() {
  const [session, setSession] = useState(loadAuth());
  const [booting, setBooting] = useState(true);
  const [bootError, setBootError] = useState("");
  const [tab, setTab] = useState("chats");
  const [openChat, setOpenChat] = useState(null);
  const wide = useWide();

  useEffect(() => {
    let cancel = false;
    (async () => {
      const initData = telegramInitData();
      try {
        if (initData) {
          const next = await api("/api/auth/telegram/webapp", {
            method: "POST",
            body: JSON.stringify({ init_data: initData }),
          }, null);
          next.mode = "telegram";
          saveAuth(next);
          if (!cancel) setSession(next);
        } else if (loadAuth()?.access_token) {
          const me = await api("/api/auth/me");
          if (!cancel) setSession({ ...loadAuth(), user: me.user });
        }
      } catch (error) {
        if (initData) saveAuth(null);
        if (!cancel) setBootError(error.message);
      } finally {
        if (!cancel) setBooting(false);
      }
    })();
    return () => {
      cancel = true;
    };
  }, []);

  function logout() {
    const current = loadAuth();
    if (current?.refresh_token) {
      api("/api/auth/logout", {
        method: "POST",
        body: JSON.stringify({ refresh_token: current.refresh_token }),
      }).catch(() => {});
    }
    saveAuth(null);
    setSession(null);
    setOpenChat(null);
  }

  if (booting) return <p className="main">Вход…</p>;
  if (!session?.access_token) {
    return <Login error={bootError} onSuccess={(next) => { saveAuth(next); setSession(next); }} />;
  }

  const hideNav = Boolean(openChat) && !wide;
  return (
    <div className={`app ${wide ? "wide" : ""} ${hideNav ? "hidden-nav" : ""}`}>
      <nav className="nav">
        {TABS.map(([id, label]) => (
          <button key={id} className={tab === id && !openChat ? "active" : ""} type="button" onClick={() => { setTab(id); setOpenChat(null); }}>
            {label}
          </button>
        ))}
      </nav>
      <main className={`main ${wide && tab === "chats" ? "locked" : ""}`}>
        {tab === "chats" && (
          <Chats wide={wide} openChat={openChat} onOpen={setOpenChat} onClose={() => setOpenChat(null)} />
        )}
        {tab === "boards" && <BoardList surface="overview" />}
        {tab === "actions" && <BoardList surface="actions" />}
        {tab === "settings" && <Settings session={session} onLogout={logout} onUser={(user) => setSession({ ...loadAuth(), user })} />}
      </main>
    </div>
  );
}

function useWide() {
  const query = "(min-width: 900px)";
  const [wide, setWide] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const media = window.matchMedia(query);
    const onChange = () => setWide(media.matches);
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);
  return wide;
}

function Login({ error, onSuccess }) {
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(error || "");

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      const next = await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ login, password }),
      }, null);
      next.mode = "password";
      onSuccess(next);
    } catch (err) {
      setMessage(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="login" onSubmit={submit}>
      <h1>База знаний</h1>
      <p className="muted">Вход в аккаунт на этом сервере.</p>
      <label>Логин <input value={login} onChange={(event) => setLogin(event.target.value)} autoComplete="username" /></label>
      <label>Пароль <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" /></label>
      {message && <p className="error">{message}</p>}
      <button type="submit" className="primary" disabled={busy}>Войти</button>
    </form>
  );
}

function Chats({ wide, openChat, onOpen, onClose }) {
  const [archived, setArchived] = useState(false);
  const [sessions, setSessions] = useState([]);
  const [error, setError] = useState("");

  async function reload() {
    try {
      const path = archived ? "/api/sessions/archived?per_page=100" : "/api/sessions?per_page=100";
      const data = await api(path);
      setSessions(data.sessions || []);
      setError("");
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => { reload(); }, [archived]);

  async function create(useKnowledgeBase) {
    const data = await api("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ title: "", use_knowledge_base: useKnowledgeBase }),
    });
    await reload();
    onOpen(data.session);
  }

  const list = (
    <section className="pane">
      <div className="page-head">
        <h1>Чаты</h1>
        <button type="button" className="primary" onClick={() => create(true)}>Новый</button>
      </div>
      <div className="segment">
        <button type="button" className={archived ? "" : "on"} onClick={() => setArchived(false)}>Сессии</button>
        <button type="button" className={archived ? "on" : ""} onClick={() => setArchived(true)}>Архив</button>
      </div>
      {error && <p className="error">{error}</p>}
      <div className="list">
        {sessions.map((item) => (
          <button key={item.id} type="button" className={`card ${openChat?.id === item.id ? "active" : ""}`} onClick={() => onOpen(item)}>
            <strong>{item.title}</strong>
            <time>{formatWhen(item.updated_at)}{archived ? " · архив" : ""}</time>
          </button>
        ))}
        {!sessions.length && <p className="muted">Пока пусто.</p>}
      </div>
    </section>
  );

  const chat = openChat ? (
    <ChatThread key={openChat.id} session={openChat} archived={archived} onClose={onClose} onChanged={reload} />
  ) : (
    <p className="muted pane">Выберите чат.</p>
  );

  if (!wide) return openChat ? chat : list;
  return <div className="split">{list}<section className="chat-pane">{chat}</section></div>;
}

function kbEnabled(session) {
  const stored = localStorage.getItem(`kb.web.kb.${session.id}`);
  if (stored === "0") return false;
  if (stored === "1") return true;
  return session.use_knowledge_base !== false;
}

function ChatThread({ session, archived, onClose, onChanged }) {
  const [messages, setMessages] = useState([]);
  const [title, setTitle] = useState(session.title || "");
  const [useKb, setUseKb] = useState(kbEnabled(session));
  const [menu, setMenu] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const scroller = useRef(null);
  const composerRef = useRef(null);

  useEffect(() => {
    let cancel = false;
    setTitle(session.title || "");
    setUseKb(kbEnabled(session));
    setMenu(false);
    setMessages([]);
    setLoading(true);
    setError("");
    api(`/api/sessions/${session.id}/messages?limit=100`)
      .then((data) => {
        if (!cancel) setMessages(data.messages || []);
      })
      .catch((err) => {
        if (!cancel) setError(err.message);
      })
      .finally(() => {
        if (!cancel) setLoading(false);
      });
    return () => {
      cancel = true;
    };
  }, [session.id]);

  useEffect(() => {
    const node = scroller.current;
    if (node && !loading) node.scrollTop = node.scrollHeight;
  }, [messages, loading]);

  async function sendDraft({ text, files, voices }) {
    setBusy(true);
    setError("");
    const body = new FormData();
    body.append("content", text || "");
    body.append("use_knowledge_base", useKb ? "true" : "false");
    body.append("client_message_id", crypto.randomUUID());
    for (const file of files) body.append("files", file, file.name);
    if (voices.length) {
      body.append("audio_transcriptions", JSON.stringify(voices.map((voice) => voice.transcription || "")));
      for (const voice of voices) body.append("audio", voice.blob, voice.name);
    }
    try {
      const data = await api(`/api/sessions/${session.id}/messages/compose`, {
        method: "POST",
        structuredUi: true,
        body,
      });
      setMessages(data.messages || []);
      onChanged();
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setBusy(false);
    }
  }

  async function rename(event) {
    event.preventDefault();
    const next = title.trim();
    if (!next) return;
    await api(`/api/sessions/${session.id}`, {
      method: "PATCH",
      body: JSON.stringify({ title: next }),
    });
    onChanged();
  }

  async function toggleArchive() {
    await api(`/api/sessions/${session.id}/${archived ? "restore" : "archive"}`, { method: "POST" });
    onChanged();
    onClose();
  }

  return (
    <section
      className={`chat ${dragOver ? "drag-over" : ""}`}
      onDragEnter={(event) => {
        if ([...(event.dataTransfer?.types || [])].includes("Files")) setDragOver(true);
      }}
      onDragOver={(event) => {
        if ([...(event.dataTransfer?.types || [])].includes("Files")) {
          event.preventDefault();
          setDragOver(true);
        }
      }}
      onDragLeave={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setDragOver(false);
      }}
      onDrop={(event) => {
        event.preventDefault();
        setDragOver(false);
        composerRef.current?.addFiles(event.dataTransfer?.files);
      }}
    >
      {dragOver && <div className="drop-overlay">Отпустите файлы</div>}
      <header className="chat-bar">
        <button type="button" className="icon" onClick={onClose} aria-label="Назад">←</button>
        <h2>{title}</h2>
        <div className="menu">
          <button type="button" className="icon" aria-label="Действия" onClick={() => setMenu((open) => !open)}>⋯</button>
          {menu && (
            <div className="menu-pop">
              <form onSubmit={rename}>
                <input value={title} onChange={(event) => setTitle(event.target.value)} aria-label="Название чата" />
                <button type="submit">Переименовать</button>
              </form>
              <label className="check">
                <input
                  type="checkbox"
                  checked={useKb}
                  onChange={(event) => {
                    const next = event.target.checked;
                    setUseKb(next);
                    localStorage.setItem(`kb.web.kb.${session.id}`, next ? "1" : "0");
                  }}
                />
                Использовать базу знаний
              </label>
              <button type="button" onClick={toggleArchive}>{archived ? "Вернуть из архива" : "В архив"}</button>
            </div>
          )}
        </div>
      </header>
      <div className="messages" ref={scroller}>
        {loading && (
          <div className="loader" role="status" aria-label="Загрузка">
            <span />
          </div>
        )}
        {!loading && messages.map((message) => (
          <article key={message.id} className={`bubble ${message.role === "user" ? "user" : "assistant"}`}>
            <header>
              <span>{message.role === "user" ? "Вы" : "Ассистент"}</span>
              <time>{formatWhen(message.created_at)}</time>
            </header>
            <Markdown text={message.content} />
            <MessageAttachments attachments={message.attachments} />
            {message.structured_ui && (
              <StructuredUI
                document={message.structured_ui}
                busy={busy}
                onEvent={async (event) => {
                  setBusy(true);
                  try {
                    const data = await api(`/api/sessions/${session.id}/ui-events`, {
                      method: "POST",
                      body: JSON.stringify(event),
                    });
                    setMessages(data.messages || []);
                  } catch (err) {
                    setError(err.message);
                  } finally {
                    setBusy(false);
                  }
                }}
              />
            )}
          </article>
        ))}
      </div>
      {error && <p className="error composer-error">{error}</p>}
      <Composer ref={composerRef} disabled={busy} status={busy ? "Отправка…" : ""} onSend={sendDraft} />
    </section>
  );
}

function isActionBoard(board) {
  const id = String(board.id || "");
  return id === "actions-presets" || id === "active-jobs" || id.startsWith("actions-") || board.surface === "actions";
}

function BoardList({ surface }) {
  const [boards, setBoards] = useState([]);
  const [presets, setPresets] = useState([]);
  const [selected, setSelected] = useState(null);
  const [period, setPeriod] = useState("");
  const [error, setError] = useState("");

  async function reload() {
    const [boardData, archivedData, presetData] = await Promise.all([
      api("/api/boards"),
      api("/api/boards/archived"),
      api("/api/boards/presets"),
    ]);
    const active = boardData.boards || [];
    const archived = (archivedData.boards || []).map((board) => ({ ...board, archived: true }));
    setBoards([...active, ...archived]);
    setPresets(presetData.presets || []);
  }

  useEffect(() => {
    reload().catch((err) => setError(err.message));
  }, []);

  const visible = boards.filter((board) => (surface === "actions" ? isActionBoard(board) : !isActionBoard(board)));
  const catalog = presets.filter((preset) => (surface === "actions" ? isActionBoard(preset) : !isActionBoard(preset)));

  async function open(board, nextPeriod = period) {
    const query = nextPeriod ? `?period=${encodeURIComponent(nextPeriod)}` : "";
    const detail = await api(`/api/boards/${board.id}${query}`);
    setSelected(detail);
  }

  async function refresh() {
    if (!selected?.board?.id) return;
    const query = period ? `?period=${encodeURIComponent(period)}` : "";
    const detail = await api(`/api/boards/${selected.board.id}/refresh${query}`, { method: "POST" });
    setSelected(detail);
  }

  return (
    <section>
      <h1>{surface === "actions" ? "Экшены" : "Обзор"}</h1>
      {error && <p className="error">{error}</p>}
      {selected ? (
        <div className="list">
          <div className="toolbar">
            <button type="button" className="ghost" onClick={() => setSelected(null)}>Назад</button>
            <input
              type="month"
              aria-label="Период"
              value={period === "all" ? "" : period}
              onChange={(event) => {
                const next = event.target.value;
                setPeriod(next);
                open(selected.board, next).catch((err) => setError(err.message));
              }}
            />
            <button type="button" className="ghost" onClick={() => { setPeriod("all"); open(selected.board, "all").catch((err) => setError(err.message)); }}>Всё</button>
            <button type="button" className="ghost" onClick={refresh}>Обновить</button>
          </div>
          <h2>{selected.board?.title || selected.title}</h2>
          {(selected.board?.subtitle) && <p className="muted">{selected.board.subtitle}</p>}
          <StructuredUI document={selected.document || selected.rendered_document} onEvent={null} />
        </div>
      ) : (
        <div className="list">
          {visible.map((board) => {
            const cell = board.list_cell || {};
            const metrics = Array.isArray(cell.metrics) ? cell.metrics.slice(0, 3) : [];
            return (
              <button key={board.id} type="button" className="card" onClick={() => open(board).catch((err) => setError(err.message))}>
                <strong>{cell.title || board.title}</strong>
                <span className="sub">{board.archived ? "Архив · " : ""}{cell.subtitle || board.subtitle || ""}</span>
                {metrics.length > 0 && (
                  <span className="metric-line">
                    {metrics.map((metric) => (
                      <span key={metric.label}>
                        <small>{metric.label}</small>
                        <b>{metric.value}</b>
                      </span>
                    ))}
                  </span>
                )}
                {cell.status_text && <span className="chip">{cell.status_text}</span>}
              </button>
            );
          })}
          {catalog.map((preset) => (
            <div key={preset.id} className="card">
              <strong>{preset.title}</strong>
              <small>{preset.installed ? "установлен" : "не установлен"}</small>
              <button
                type="button"
                className="ghost"
                onClick={async () => {
                  const method = preset.installed ? "DELETE" : "POST";
                  const path = preset.installed
                    ? `/api/boards/presets/${preset.id}`
                    : `/api/boards/presets/${preset.id}/install`;
                  await api(path, { method });
                  await reload();
                }}
              >
                {preset.installed ? "Убрать" : "Установить"}
              </button>
            </div>
          ))}
          {!visible.length && !catalog.length && <p className="muted">Пока пусто.</p>}
        </div>
      )}
    </section>
  );
}

function Settings({ session, onLogout, onUser }) {
  const user = session.user || {};
  const telegram = session.mode === "telegram";
  const [currentPassword, setCurrentPassword] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");

  async function changePassword(event) {
    event.preventDefault();
    setMessage("");
    try {
      const body = { new_password: password };
      if (currentPassword) body.current_password = currentPassword;
      await api("/api/auth/change-password", {
        method: "POST",
        body: JSON.stringify(body),
      });
      setCurrentPassword("");
      setPassword("");
      setMessage("Пароль обновлён");
      const me = await api("/api/auth/me");
      onUser(me.user);
    } catch (err) {
      setMessage(err.message);
    }
  }

  return (
    <section className="list">
      <h1>Настройки</h1>
      <p><strong>{user.login}</strong></p>
      <p className="muted">Роль: {user.role || "user"}</p>
      <p>Telegram: {user.telegram_linked ? `привязан${user.telegram_username ? ` (@${user.telegram_username})` : ""}` : "не привязан"}</p>
      {!telegram && (
        <form className="list" onSubmit={changePassword}>
          <label>Текущий пароль <input type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} autoComplete="current-password" /></label>
          <label>Новый пароль <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} minLength={8} autoComplete="new-password" /></label>
          <button type="submit" className="primary">Сменить пароль</button>
        </form>
      )}
      {message && <p className="muted">{message}</p>}
      <button type="button" className="ghost" onClick={onLogout}>Выйти</button>
    </section>
  );
}

function formatWhen(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString();
}
