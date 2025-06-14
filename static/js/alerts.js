// alerts.js
// 📌 Уведомления (успех/ошибка) для сайта BeaHea

// Функция для создания уведомления
function showAlert(message, type = "success", timeout = 4000) {
    const container = document.getElementById("alert-container");

    const alert = document.createElement("div");
    alert.className = `
        px-6 py-4 rounded shadow-lg max-w-xs transition transform fade-in
        ${type === "success" ? "bg-primary text-dark" : "bg-red-400 text-white"}
    `;
    alert.innerText = message;

    container.appendChild(alert);

    // Автоматическое удаление через timeout
    setTimeout(() => {
        alert.classList.add("opacity-0", "-translate-y-2");
        setTimeout(() => alert.remove(), 300); // Анимация исчезновения
    }, timeout);
}
