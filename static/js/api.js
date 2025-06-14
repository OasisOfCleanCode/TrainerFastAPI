// 📁 api.js
// Универсальный fetch с автоматическим обновлением токена при 401


let isRefreshing = false;
let refreshQueue = [];

export async function apiFetch(input, init = {}) {
    // Устанавливаем токен из localStorage, если он есть
    const accessToken = localStorage.getItem("access_token");
    init.headers = {
        ...(init.headers || {}),
        "Content-Type": "application/json",
        "Accept": "application/json",
    };
    if (accessToken) {
        init.headers["Authorization"] = `Bearer ${accessToken}`;
    }
    init.credentials = "include";

    let response = await fetch(input, init);

    if (response.status === 401 && !input.includes("/api/refresh")) {
        if (!isRefreshing) {
            isRefreshing = true;
            try {
                await refreshToken();
                isRefreshing = false;
                refreshQueue.forEach(cb => cb());
                refreshQueue = [];
                return apiFetch(input, init); // повтор запроса после обновления
            } catch (e) {
                isRefreshing = false;
                refreshQueue = [];
                throw e;
            }
        } else {
            return new Promise((resolve, reject) => {
                refreshQueue.push(() => {
                    apiFetch(input, init).then(resolve).catch(reject);
                });
            });
        }
    }

    return response;
}