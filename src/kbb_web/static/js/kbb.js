/* Knowledge Base Builder — HTMX helpers */

document.addEventListener("DOMContentLoaded", () => {
    // Ctrl+Enter / Cmd+Enter submits the closest form from a textarea
    document.body.addEventListener("keydown", (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
            const textarea = e.target;
            if (textarea.tagName === "TEXTAREA") {
                const form = textarea.closest("form");
                if (form) {
                    e.preventDefault();
                    // Trigger HTMX submit if the form uses hx-post
                    const hxPost = form.getAttribute("hx-post");
                    if (hxPost) {
                        htmx.trigger(form, "submit");
                    } else {
                        form.requestSubmit();
                    }
                }
            }
        }
    });

    // After HTMX swaps content, focus the first textarea or input in the target
    document.body.addEventListener("htmx:afterSwap", (e) => {
        const target = e.detail.target;
        if (target) {
            const input = target.querySelector("textarea, input[type='text']");
            if (input) {
                input.focus();
            }
        }
    });

    // Swap error response body into the target element so LLM failures are visible
    document.body.addEventListener("htmx:responseError", (e) => {
        const target = e.detail.target || e.detail.elt;
        if (target && e.detail.xhr && e.detail.xhr.response) {
            target.innerHTML = e.detail.xhr.response;
        }
    });
});