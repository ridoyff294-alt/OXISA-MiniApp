const tg = window.Telegram.WebApp;

const API_URL = "https://oxisa-miniapp.onrender.com";

tg.ready();
tg.expand();

async function initializeOXISA() {
    try {
        const initData = tg.initData;

        if (!initData) {
            throw new Error("Telegram authentication data not available");
        }

        const response = await fetch(`${API_URL}/api/auth/telegram`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                initData: initData
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Authentication failed");
        }

        console.log("OXISA user authenticated:", data);

        const user = data.user;

        document.getElementById("userName").textContent =
            user.firstName || "User";

        document.getElementById("loading").style.display = "none";
        document.getElementById("content").style.display = "block";

    } catch (error) {

        console.error("OXISA Error:", error);

        document.getElementById("loading").textContent =
            "Unable to connect to OXISA. Please try again.";
    }
}

initializeOXISA();
