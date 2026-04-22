// ================= CONFIG =================
const API = {
  signup: "/signup",
  login: "/login",

  createBatch: "/batch/create",
  joinBatch: "/batch/join",

  createSession: "/session/create",
  markAttendance: "/attendance/mark",

  viewAttendance: (id) => `/session/${id}/attendance`,
  stats: "/attendance/stats",
};

// ================= UTIL =================

// Generic API call (FIXED)
async function apiCall(url, method = "GET", data = null) {
  try {
    const res = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: data ? JSON.stringify(data) : null,
    });

    // handle non-JSON safely
    const text = await res.text();

    try {
      return JSON.parse(text);
    } catch {
      console.error("Non JSON response:", text);
      return { message: "Server error" };
    }
  } catch (err) {
    console.error("Network error:", err);
    showToast("Network error", "error");
    return null;
  }
}

// Toast (no alert)
function showToast(message, type = "success") {
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerText = message;

  document.body.appendChild(toast);

  setTimeout(() => toast.remove(), 3000);
}

// Button loader
function setLoading(btn, text = "Processing...") {
  btn.disabled = true;
  btn.dataset.oldText = btn.innerText;
  btn.innerText = text;
}

function resetButton(btn) {
  btn.disabled = false;
  btn.innerText = btn.dataset.oldText || "Submit";
}

// ================= AUTH =================

async function signup() {
  const btn = event.target;
  setLoading(btn);

  const data = {
    name: document.getElementById("name").value.trim(),
    email: document.getElementById("email").value.trim(),
    password: document.getElementById("password").value.trim(),
    role: document.getElementById("role").value,
  };

  if (!data.name || !data.email || !data.password) {
    showToast("All fields required", "error");
    return resetButton(btn);
  }

  const res = await apiCall(API.signup, "POST", data);

  if (!res) return resetButton(btn);

  showToast(res.message || "Signup done");

  // auto switch to login tab
  switchTab("login");

  resetButton(btn);
}

async function login() {
  const btn = event.target;
  setLoading(btn);

  const data = {
    email: document.getElementById("login_email").value.trim(),
    password: document.getElementById("login_password").value.trim(),
  };

  if (!data.email || !data.password) {
    showToast("Enter email & password", "error");
    return resetButton(btn);
  }

  const res = await apiCall(API.login, "POST", data);

  if (!res) return resetButton(btn);

  if (res.redirect) {
    window.location.href = res.redirect;
  } else {
    showToast(res.message || "Login failed", "error");
    resetButton(btn);
  }
}

// ================= BATCH =================

async function createBatch() {
  const btn = event.target;
  setLoading(btn);

  const name = document.getElementById("batch_name").value.trim();

  if (!name) {
    showToast("Batch name required", "error");
    return resetButton(btn);
  }

  const res = await apiCall(API.createBatch, "POST", { name });

  if (!res) return resetButton(btn);

  showToast(res.message || "Batch created");

  if (res.invite_code) {
    document.getElementById("invite_code").innerText =
      "Invite Code: " + res.invite_code;
  }

  resetButton(btn);
}

async function joinBatch() {
  const code = prompt("Enter invite code:");

  if (!code) return;

  const res = await apiCall(API.joinBatch, "POST", { code });

  if (!res) return;

  showToast(res.message || "Joined batch");
  location.reload();
}

// ================= SESSION =================

async function createSession() {
  const btn = event.target;
  setLoading(btn);

  const data = {
    title: document.getElementById("title").value.trim(),
    date: document.getElementById("date").value,
    batch_id: document.getElementById("batch_id")?.value,
  };

  if (!data.title || !data.date) {
    showToast("Fill all fields", "error");
    return resetButton(btn);
  }

  const res = await apiCall(API.createSession, "POST", data);

  if (!res) return resetButton(btn);

  showToast(res.message || "Session created");

  location.reload();
}

// ================= ATTENDANCE =================

async function markAttendance(id) {
  const btn = event.target;
  setLoading(btn);

  const status = document.getElementById("status_" + id).value;

  const res = await apiCall(API.markAttendance, "POST", {
    session_id: id,
    status,
  });

  if (!res) return resetButton(btn);

  showToast(res.message || "Attendance updated");

  resetButton(btn);
}

// ================= VIEW ATTENDANCE =================

async function viewAttendance(id) {
  const data = await apiCall(API.viewAttendance(id));

  if (!data) return;

  let content = "<h3>Attendance</h3>";

  data.forEach((d) => {
    content += `<p>${d.name} - ${d.status}</p>`;
  });

  showModal(content);
}

// ================= MODAL =================

function showModal(content) {
  const modal = document.createElement("div");
  modal.className = "modal";

  modal.innerHTML = `
    <div class="modal-box">
      ${content}
      <br><br>
      <button onclick="this.closest('.modal').remove()">Close</button>
    </div>
  `;

  document.body.appendChild(modal);
}

// ================= CHART =================

async function loadChart() {
  const data = await apiCall(API.stats);

  if (!data) return;

  new Chart(document.getElementById("chart"), {
    type: "bar",
    data: {
      labels: ["Present", "Absent", "Late"],
      datasets: [
        {
          label: "Attendance",
          data: [data.present || 0, data.absent || 0, data.late || 0],
        },
      ],
    },
  });
}

// ================= INIT =================

document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("chart")) {
    loadChart();
  }
});
