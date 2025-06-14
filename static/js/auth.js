// 📌 auth.js — авторизация, токены, получение профиля

let isRefreshing = false;
let refreshSubscribers = [];

function subscribeTokenRefresh(cb) {
  refreshSubscribers.push(cb);
}

function onTokenRefreshed(token) {
  refreshSubscribers.forEach(cb => cb(token));
  refreshSubscribers = [];
}

// 📤 Авторизация
async function login(username, password) {
  const data = new URLSearchParams();
  data.append("username", username);
  data.append("password", password);
  data.append("scope", "USER");

  const res = await fetch("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: data,
    credentials: "include"
  });

  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || "Ошибка входа");
  }

  const result = await res.json();
  if (result.scope && result.scope !== "USER") {
    throw new Error("Доступ запрещен: недостаточно прав");
  }

  localStorage.setItem("access_token", result.access_token);
}

// 📤 Выход
async function logout() {
  await fetch("/api/logout", {
    method: "POST",
    credentials: "include"
  });

  localStorage.removeItem("access_token");
  window.location.href = "/";
}

// ♻️ Обновление токена
async function refreshToken() {
  const res = await fetch("/api/refresh", {
    method: "PUT",
    credentials: "include"
  });

  if (!res.ok) throw new Error("Не удалось обновить токен");

  const data = await res.json();
  localStorage.setItem("access_token", data.access_token);
  return data.access_token;
}

// 🧠 Получение пользователя
async function getCurrentUser() {
    let token = localStorage.getItem("access_token");

    let res = await fetch("/api/me", {
        method: "GET",
        headers: { Authorization: "Bearer " + token },
        credentials: "include"
    });

    if (res.status === 401) {
        try {
            token = await refreshToken();
            res = await fetch("/api/me", {
                method: "GET",
                headers: { Authorization: "Bearer " + token },
                credentials: "include"
            });
        } catch (e) {
            throw new Error("Не авторизован");
        }
    }

    if (!res.ok) throw new Error("Ошибка при получении профиля");
    return await res.json();
}
// Обновление токена доступа
async function refreshToken() {
    const res = await fetch("/api/refresh", {
        method: "PUT",
        credentials: "include"
    });

    if (!res.ok) throw new Error("Не удалось обновить токен");

    const json = await res.json();
    localStorage.setItem("access_token", json.access_token);
    return json.access_token;
}
window.refreshToken = refreshToken;
window.getCurrentUser = getCurrentUser;
window.logout = logout;
window.login = login;