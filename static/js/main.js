// app/static/js/main.js

// ========= ОСНОВНОЙ СКРИПТ BeaHea =========

// После полной загрузки страницы
document.addEventListener('DOMContentLoaded', function() {

    /* === Плавное появление элементов при скролле === */
    const fadeElements = document.querySelectorAll('.fade-in');

    // Создаем IntersectionObserver для анимации появления
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('opacity-100', 'translate-y-0'); // Показываем элемент
                observer.unobserve(entry.target); // Больше не отслеживаем этот элемент
            }
        });
    }, { threshold: 0.1 });

    // Назначаем анимацию каждому элементу с классом fade-in
    fadeElements.forEach(el => {
        el.classList.add('opacity-0', 'translate-y-10', 'transition', 'duration-700');
        observer.observe(el);
    });

    /* === Плавная прокрутка при клике по якорным ссылкам === */
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                window.scrollTo({
                    top: target.offsetTop - 80, // отступ для шапки
                    behavior: 'smooth'
                });
            }
        });
    });

    /* === Автоопределение темы из localStorage === */
    const savedTheme = localStorage.getItem("theme");
    if (savedTheme === "dark") {
        document.documentElement.classList.add("dark");
    } else if (savedTheme === "light") {
        document.documentElement.classList.remove("dark");
    }

    /* === Переключатель темы (на случай если где-то добавится кнопка с id=theme-toggle) === */
    document.addEventListener("click", function (e) {
        if (e.target.id === "theme-toggle") {
            document.documentElement.classList.toggle("dark");
            const isDark = document.documentElement.classList.contains("dark");
            localStorage.setItem("theme", isDark ? "dark" : "light");
        }
    });
    (async () => {
        const authDesktop = document.getElementById("auth-desktop");
        const authMobile = document.getElementById("auth-mobile");

        try {
            const user = await getCurrentUser();
            const name = user.profile?.first_name?.trim() || user.email?.split("@")[0] || "чемпион";

            const desktopHTML = `
                <span class="text-sm text-dark dark:text-white">Привет, ${name}!</span>
                <button id="accountBtnDesktop" class="text-sm text-red-500 hover:text-red-700">Профиль</button>
                <button id="logoutBtnDesktop" class="text-sm text-red-500 hover:text-red-700">Выйти</button>
            `;

            const mobileHTML = `
                <span class="block py-2 text-dark dark:text-white">Привет, ${name}!</span>
                <button id="accountBtnMobile" class="text-sm text-red-500 hover:text-red-700">Профиль</button>
                <button id="logoutBtnMobile" class="block py-2 text-red-500 hover:text-red-700">Выйти</button>
            `;

            if (authDesktop) authDesktop.innerHTML = desktopHTML;
            if (authMobile) authMobile.innerHTML = mobileHTML;

            document.getElementById("accountBtnMobile")?.addEventListener("click", () => {
                window.location.href = "/account";
            });
            document.getElementById("accountBtnDesktop")?.addEventListener("click", () => {
                window.location.href = "/account";
            });
            document.getElementById("logoutBtnDesktop")?.addEventListener("click", logout);
            document.getElementById("logoutBtnMobile")?.addEventListener("click", logout);

        } catch (err) {
            console.log("⛔ Не авторизован:", err.message);
        }
    })();
});

