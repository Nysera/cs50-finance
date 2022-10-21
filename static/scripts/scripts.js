const header = (function() {
    const body = document.querySelector("body");
    const menuButton = document.querySelector("#menuToggle");

    menuButton.addEventListener("click", function() {
        !body.classList.contains("menu-open") ? toggleMenu("open", body) : toggleMenu("close", body);
    });

    const toggleMenu = function(action, element) {
        if (action === "open") {
            element.classList.add("menu-open");
        } else if(action === "close") {
            element.classList.remove("menu-open");
        }
    };

    const hideMenuOnResize = function() {
        const width = window.innerWidth;

        if (body.classList.contains("menu-open") && width >= 600) {
            toggleMenu("close", body);
        }
    };

    window.addEventListener("resize", hideMenuOnResize);
}());

const flashMessages = (function() {
    const flashMessageContainer = document.querySelector(".flash-container .flash_wrapper");
    const flashCloseButton = document.querySelector(".flash-container .flash_wrapper .flash_close");

    if (!flashMessageContainer) {
        return;
    }

    flashCloseButton.addEventListener("click", function() {
        flashMessageContainer.remove(this.parentElement);
    });
})();