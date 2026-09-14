const tg = window.Telegram.WebApp;

const API_URL = "https://oxisa-miniapp.onrender.com";

tg.ready();
tg.expand();

async function initializeOXISA() {

    const loading = document.getElementById("loading");

    try {

        loading.textContent = "Connecting to OXISA...";

        const initData = tg.initData;

        // Telegram Mini App authentication check
        if (!initData) {
            throw new Error(
                "Telegram initData পাওয়া যাচ্ছে না। Mini App অবশ্যই Telegram-এর ভিতর থেকে খুলতে হবে।"
            );
        }

        console.log("Telegram initData received");

        const response = await fetch(
            `${API_URL}/api/auth/telegram`,
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({
                    initData: initData
                })
            }
        );

        const text = await response.text();

        console.log(
            "Backend status:",
            response.status
        );

        console.log(
            "Backend response:",
            text
        );

        let data;

        try {
            data = JSON.parse(text);
        } catch {
            throw new Error(
                "Backend থেকে valid JSON response পাওয়া যায়নি।"
            );
        }

        if (!response.ok) {

            throw new Error(
                data.detail ||
                `Backend error: ${response.status}`
            );
        }

        if (!data.success) {

            throw new Error(
                "OXISA authentication failed."
            );
        }

        console.log(
            "OXISA authentication successful:",
            data
        );

        const user = data.user;

        document.getElementById(
            "userName"
        ).textContent =
            user.firstName || "User";

        document.getElementById(
            "loading"
        ).style.display = "none";

        document.getElementById(
            "content"
        ).style.display = "block";

    } catch (error) {

        console.error(
            "OXISA ERROR:",
            error
        );

        loading.classList.add("error");

        loading.innerHTML =
            `<b>OXISA Connection Error</b><br><br>
            ${error.message}<br><br>
            <small>Telegram Mini App আবার খুলে চেষ্টা করুন।</small>`;
    }
}

initializeOXISA();
