// app/static/js/profile.js

window.addEventListener("DOMContentLoaded", async () => {
  const profileForm = document.getElementById("profile-form");
  const notAuthBlock = document.getElementById("not-authenticated");
  const galleryBlock = document.getElementById("photo-gallery");

  const fields = {
    first_name: document.getElementById("first_name"),
    last_name: document.getElementById("last_name"),
    birth_date: document.getElementById("birth_date"),
    phone: document.getElementById("phone"),
    gender: document.getElementById("gender"),
  };

  const emailSpan = document.getElementById("email");
  const emailConfirmed = document.getElementById("email-confirmed");
  const verifyBtn = document.getElementById("verify-email-btn");
  const rolesBlock = document.getElementById("roles");
  const cancelBtn = document.getElementById("cancel-btn");
  const saveBtn = document.getElementById("save-btn");
  const uploadInput = document.getElementById("upload-photo");
  const galleryTrack = document.getElementById("gallery-track");

  const passwordModal = document.getElementById("password-modal");
  const changePasswordBtn = document.getElementById("change-password-btn");
  const cancelPasswordBtn = document.getElementById("cancel-password");
  const submitPasswordBtn = document.getElementById("submit-password");

  const inputOld = document.getElementById("old-password");
  const inputNew = document.getElementById("new-password");
  const inputRepeat = document.getElementById("repeat-password");

  let original = {};

  try {
    const user = await getCurrentUser();
    const profile = user.profile || {};

    original = {
      first_name: profile.first_name || "",
      last_name: profile.last_name || "",
      birth_date: profile.data_birth?.split("T")[0] || "",
      phone: user.phone_number || "",
      gender: profile.gender || "NOT_SPECIFIED",
    };

    Object.entries(fields).forEach(([key, el]) => el.value = original[key]);
    emailSpan.textContent = user.email;
    emailConfirmed.textContent = user.is_email_confirmed ? "Подтвержден" : "Не подтвержден";
    rolesBlock.textContent = (user.roles || []).join(", ");

    profileForm.classList.remove("hidden");
    galleryBlock.classList.remove("hidden");

    if (!user.is_email_confirmed) {
      verifyBtn.classList.remove("hidden");
      verifyBtn.addEventListener("click", async () => {
        try {
          await apiFetch("/email/verify", { method: "POST" });
          showAlert("Письмо отправлено на email");
        } catch {
          showAlert("Ошибка при отправке письма", "error");
        }
      });
    }

    Object.values(fields).forEach(input => {
      input.addEventListener("input", () => {
        const hasChanged = Object.entries(fields).some(([key, el]) => el.value !== original[key]);
        saveBtn.classList.toggle("hidden", !hasChanged);
        cancelBtn.classList.toggle("hidden", !hasChanged);
      });
    });

    cancelBtn.addEventListener("click", () => {
      Object.entries(fields).forEach(([key, el]) => el.value = original[key]);
      saveBtn.classList.add("hidden");
      cancelBtn.classList.add("hidden");
    });

    saveBtn.addEventListener("click", async () => {
      const body = {
        first_name: fields.first_name.value,
        last_name: fields.last_name.value,
        data_birth: fields.birth_date.value || null,
        gender: fields.gender.value,
      };
      const phone = fields.phone.value;
      try {
        await apiFetch("/api/me/profile", {
          method: "PUT",
          body: JSON.stringify(body)
        });
        await apiFetch("/api/me/phone", {
          method: "PUT",
          body: JSON.stringify({ phone_number: phone })
        });
        showAlert("Профиль обновлён");
        cancelBtn.click();
      } catch {
        showAlert("Не удалось сохранить", "error");
      }
    });

    const loadPhotos = async () => {
      galleryTrack.innerHTML = "";
      try {
        const res = await apiFetch("/api/me/media/all");
        const photos = await res.json();
        photos.forEach(photo => {
          const container = document.createElement("div");
          container.className = "relative w-20 h-20 shrink-0 rounded overflow-hidden snap-center";

          const img = document.createElement("img");
          img.src = photo.preview_photo;
          img.alt = "Фото";
          img.className = "w-full h-full object-cover cursor-pointer";

          img.addEventListener("click", () => {
            const popup = window.open(photo.orig_photo, "_blank");
            if (!popup) showAlert("Разрешите всплывающие окна", "error");
          });

          const delBtn = document.createElement("button");
          delBtn.textContent = "✕";
          delBtn.className = "absolute top-0 right-0 bg-red-500 text-white text-xs px-1 rounded-bl";
          delBtn.addEventListener("click", async () => {
            try {
              await apiFetch(`/api/me/media/${photo.id}`, { method: "DELETE" });
              showAlert("Удалено");
              loadPhotos();
            } catch {
              showAlert("Не удалось удалить", "error");
            }
          });

          container.append(img, delBtn);
          galleryTrack.appendChild(container);
        });
      } catch {
        showAlert("Ошибка загрузки фото", "error");
      }
    };
    loadPhotos();

    uploadInput.addEventListener("change", async () => {
      const files = Array.from(uploadInput.files);
      if (!files.length) return;
      const formData = new FormData();
      files.forEach(f => formData.append("file_content", f));

      try {
        await fetch("/api/me/media", {
          method: "POST",
          body: formData,
          credentials: "include"
        });
        showAlert("Загружено");
        uploadInput.value = "";
        loadPhotos();
      } catch {
        showAlert("Ошибка загрузки", "error");
      }
    });

    // 🔐 смена пароля
    changePasswordBtn.addEventListener("click", () => passwordModal.classList.remove("hidden"));
    cancelPasswordBtn.addEventListener("click", () => {
      passwordModal.classList.add("hidden");
      inputOld.value = "";
      inputNew.value = "";
      inputRepeat.value = "";
    });

    submitPasswordBtn.addEventListener("click", async () => {
      const password = inputOld.value;
      const new_password = inputNew.value;
      const confirm_new_password = inputRepeat.value;

      if (new_password.length < 5) {
        showAlert("Пароль слишком короткий", "error");
        return;
      }
      if (new_password !== confirm_new_password) {
        showAlert("Пароли не совпадают", "error");
        return;
      }

      try {
        await apiFetch("/api/me/password", {
          method: "PUT",
          body: JSON.stringify({ password, new_password, confirm_new_password })
        });
        showAlert("Пароль обновлён");
        cancelPasswordBtn.click();
      } catch {
        showAlert("Ошибка смены пароля", "error");
      }
    });
  } catch {
    notAuthBlock.classList.remove("hidden");
  }
});
