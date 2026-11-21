(() => {
  const API = ""; // same origin → /api/...
  const store = {
    get access() {
      return localStorage.getItem("kb_admin_access") || "";
    },
    set access(v) {
      if (v) localStorage.setItem("kb_admin_access", v);
      else localStorage.removeItem("kb_admin_access");
    },
    get refresh() {
      return localStorage.getItem("kb_admin_refresh") || "";
    },
    set refresh(v) {
      if (v) localStorage.setItem("kb_admin_refresh", v);
      else localStorage.removeItem("kb_admin_refresh");
    },
    clear() {
      this.access = "";
      this.refresh = "";
    },
  };

  const loginView = document.getElementById("login-view");
  const mainView = document.getElementById("main-view");
  const loginError = document.getElementById("login-error");
  const whoami = document.getElementById("whoami");
  const usersBody = document.getElementById("users-body");
  const createResult = document.getElementById("create-result");

  async function api(path, opts = {}) {
    const headers = Object.assign({ "Content-Type": "application/json" }, opts.headers || {});
    if (store.access) headers.Authorization = `Bearer ${store.access}`;
    let res = await fetch(`${API}${path}`, { ...opts, headers });
    if (res.status === 401 && store.refresh) {
      const refreshed = await fetch(`${API}/api/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: store.refresh }),
      });
      if (refreshed.ok) {
        const data = await refreshed.json();
        store.access = data.access_token;
        store.refresh = data.refresh_token;
        headers.Authorization = `Bearer ${store.access}`;
        res = await fetch(`${API}${path}`, { ...opts, headers });
      }
    }
    return res;
  }

  function showLogin() {
    loginView.hidden = false;
    mainView.hidden = true;
  }

  function showMain(user) {
    loginView.hidden = true;
    mainView.hidden = false;
    whoami.textContent = user ? `${user.login} (${user.role})` : "";
  }

  async function loadMe() {
    const res = await api("/api/auth/me");
    if (!res.ok) {
      store.clear();
      showLogin();
      return null;
    }
    const data = await res.json();
    if ((data.user.role || "") !== "admin" && !data.user.is_admin) {
      store.clear();
      loginError.hidden = false;
      loginError.textContent = "Нужен аккаунт с role=admin";
      showLogin();
      return null;
    }
    showMain(data.user);
    return data.user;
  }

  async function loadUsers() {
    const res = await api("/api/admin/users");
    if (!res.ok) {
      usersBody.innerHTML = `<tr><td colspan="7">Ошибка ${res.status}</td></tr>`;
      return;
    }
    const data = await res.json();
    usersBody.innerHTML = "";
    for (const u of data.users || []) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${u.id}</td>
        <td>${u.login}</td>
        <td>${u.role}</td>
        <td>
          <select class="iso" data-id="${u.id}">
            <option value="strict" ${u.cursor_isolation === "strict" ? "selected" : ""}>strict</option>
            <option value="host" ${u.cursor_isolation === "host" ? "selected" : ""}>host</option>
          </select>
        </td>
        <td>${u.is_allowed ? "yes" : "no"}</td>
        <td>${u.telegram_linked ? "привязан" : "нет"}</td>
        <td>
          <button type="button" class="ghost reset" data-id="${u.id}">Reset pwd</button>
          <button type="button" class="ghost toggle" data-id="${u.id}" data-allowed="${u.is_allowed}">${u.is_allowed ? "Disable" : "Enable"}</button>
          <button type="button" class="ghost invite" data-id="${u.id}" data-login="${u.login}">Ссылка в Telegram</button>
        </td>`;
      usersBody.appendChild(tr);
    }
    usersBody.querySelectorAll("select.iso").forEach((el) => {
      el.addEventListener("change", async () => {
        await api(`/api/admin/users/${el.dataset.id}`, {
          method: "PATCH",
          body: JSON.stringify({ cursor_isolation: el.value }),
        });
      });
    });
    usersBody.querySelectorAll("button.reset").forEach((el) => {
      el.addEventListener("click", async () => {
        const res = await api(`/api/admin/users/${el.dataset.id}/reset-password`, {
          method: "POST",
          body: JSON.stringify({ must_change_password: true }),
        });
        const data = await res.json();
        alert(res.ok ? `Temp password: ${data.temporary_password}` : `Error ${res.status}`);
      });
    });
    usersBody.querySelectorAll("button.toggle").forEach((el) => {
      el.addEventListener("click", async () => {
        const allowed = el.dataset.allowed === "true";
        await api(`/api/admin/users/${el.dataset.id}`, {
          method: "PATCH",
          body: JSON.stringify({ is_allowed: !allowed }),
        });
        await loadUsers();
      });
    });
    usersBody.querySelectorAll("button.invite").forEach((el) => {
      el.addEventListener("click", async () => {
        const res = await api(`/api/admin/users/${el.dataset.id}/telegram-invite`, {
          method: "POST",
          body: "{}",
        });
        const data = await res.json();
        if (!res.ok) {
          showInvite(null, data.detail || data.message || `Ошибка ${res.status}`);
          return;
        }
        showInvite(data.telegram_invite, el.dataset.login);
      });
    });
  }

  function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[ch]));
  }

  function showInvite(invite, loginOrError) {
    const box = document.getElementById("invite-box");
    if (!invite) {
      box.hidden = false;
      box.textContent = String(loginOrError || "Не удалось выдать ссылку");
      return;
    }
    const url = invite.url || "";
    const expires = invite.expires_at ? new Date(invite.expires_at).toLocaleString() : "";
    box.hidden = false;
    box.innerHTML = `
      <p>Ссылка для <b>${esc(loginOrError)}</b>. Человек откроет бота и нажмёт «Да, привязать».</p>
      <p><a href="${esc(url)}" target="_blank" rel="noreferrer">${esc(url || invite.command)}</a></p>
      <p class="muted">Действует до ${esc(expires)}. Код: ${esc(invite.code)}</p>
      <div class="row">
        <button type="button" id="btn-copy-invite">Скопировать ссылку</button>
      </div>`;
    const copy = document.getElementById("btn-copy-invite");
    if (copy) {
      copy.addEventListener("click", async () => {
        const text = url || invite.command;
        try {
          await navigator.clipboard.writeText(text);
          copy.textContent = "Скопировано";
        } catch (_) {
          copy.textContent = text;
        }
      });
    }
  }

  document.getElementById("btn-login").addEventListener("click", async () => {
    loginError.hidden = true;
    const login = document.getElementById("login").value.trim();
    const password = document.getElementById("password").value;
    const res = await fetch(`${API}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ login, password }),
    });
    if (!res.ok) {
      loginError.hidden = false;
      loginError.textContent = `Ошибка входа (${res.status})`;
      return;
    }
    const data = await res.json();
    store.access = data.access_token;
    store.refresh = data.refresh_token;
    if (await loadMe()) {
      await loadUsers();
      await loadCrashLogSetting();
    }
  });

  document.getElementById("btn-logout").addEventListener("click", async () => {
    try {
      await api("/api/auth/logout", {
        method: "POST",
        body: JSON.stringify({ refresh_token: store.refresh || null }),
      });
    } catch (_) {}
    store.clear();
    showLogin();
  });

  document.getElementById("btn-refresh").addEventListener("click", () => loadUsers());

  document.getElementById("btn-create").addEventListener("click", async () => {
    createResult.hidden = true;
    const body = {
      login: document.getElementById("new-login").value.trim(),
      email: document.getElementById("new-email").value.trim() || null,
      role: document.getElementById("new-role").value,
      cursor_isolation: document.getElementById("new-isolation").value,
      must_change_password: true,
    };
    if (document.getElementById("new-telegram").checked) body.invite_via = "telegram";
    const res = await api("/api/admin/users", { method: "POST", body: JSON.stringify(body) });
    const data = await res.json();
    createResult.hidden = false;
    if (res.ok && data.user) {
      createResult.textContent = `Создан ${data.user.login}. Временный пароль: ${data.user.temporary_password}`;
      if (data.user.telegram_invite) showInvite(data.user.telegram_invite, data.user.login);
    } else {
      createResult.textContent = JSON.stringify(data, null, 2);
    }
    if (res.ok) await loadUsers();
  });

  async function loadCrashLogSetting() {
    const box = document.getElementById("accept-crash-logs");
    const status = document.getElementById("crash-logs-status");
    if (!box) return;
    const res = await api("/api/admin/settings");
    if (!res.ok) {
      status.textContent = `Не удалось прочитать настройку (${res.status})`;
      return;
    }
    const data = await res.json();
    box.checked = Boolean(data.accept_crash_logs);
    status.textContent = "";
  }

  const acceptCrashLogs = document.getElementById("accept-crash-logs");
  if (acceptCrashLogs) {
    acceptCrashLogs.addEventListener("change", async () => {
      const status = document.getElementById("crash-logs-status");
      const res = await api("/api/admin/settings", {
        method: "PATCH",
        body: JSON.stringify({ accept_crash_logs: acceptCrashLogs.checked }),
      });
      status.textContent = res.ok ? "" : `Ошибка ${res.status}`;
      if (!res.ok) acceptCrashLogs.checked = !acceptCrashLogs.checked;
    });
  }

  (async () => {
    if (store.access && (await loadMe())) {
      await loadUsers();
      await loadCrashLogSetting();
    } else showLogin();
  })();
})();
