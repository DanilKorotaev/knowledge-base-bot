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
      usersBody.innerHTML = `<tr><td colspan="6">Ошибка ${res.status}</td></tr>`;
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
        <td>
          <button type="button" class="ghost reset" data-id="${u.id}">Reset pwd</button>
          <button type="button" class="ghost toggle" data-id="${u.id}" data-allowed="${u.is_allowed}">${u.is_allowed ? "Disable" : "Enable"}</button>
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
    if (await loadMe()) await loadUsers();
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
    const res = await api("/api/admin/users", { method: "POST", body: JSON.stringify(body) });
    const data = await res.json();
    createResult.hidden = false;
    createResult.textContent = JSON.stringify(data, null, 2);
    if (res.ok) await loadUsers();
  });

  (async () => {
    if (store.access && (await loadMe())) await loadUsers();
    else showLogin();
  })();
})();
