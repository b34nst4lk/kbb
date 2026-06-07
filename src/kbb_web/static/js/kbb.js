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

    // Initialize voice recorder buttons on the page
    initVoiceRecorder();
});


// --- Voice Recorder ---
// Captures audio from the microphone via MediaRecorder API,
// uploads to /api/transcribe, and fills the response textarea.

class VoiceRecorder {
    constructor(buttonEl) {
        this.button = buttonEl;
        this.mediaRecorder = null;
        this.chunks = [];
        this.isRecording = false;
        this.stream = null;

        this.button.addEventListener("click", () => this.toggle());
    }

    async toggle() {
        if (this.isRecording) {
            this.stop();
        } else {
            await this.start();
        }
    }

    async start() {
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        } catch (err) {
            alert("Microphone access denied. Please allow microphone access to record audio.");
            return;
        }

        const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
            ? "audio/webm;codecs=opus"
            : MediaRecorder.isTypeSupported("audio/webm")
                ? "audio/webm"
                : "audio/ogg;codecs=opus";

        this.mediaRecorder = new MediaRecorder(this.stream, { mimeType });
        this.chunks = [];

        this.mediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) {
                this.chunks.push(e.data);
            }
        };

        this.mediaRecorder.onstop = () => this.upload();

        this.mediaRecorder.start();
        this.isRecording = true;
        this.updateUI();
    }

    stop() {
        if (this.mediaRecorder && this.mediaRecorder.state !== "inactive") {
            this.mediaRecorder.stop();
        }
        if (this.stream) {
            this.stream.getTracks().forEach((track) => track.stop());
        }
        this.isRecording = false;
        this.updateUI();
    }

    async upload() {
        const mimeType = this.chunks[0]?.type || "audio/webm";
        const ext = mimeType.includes("ogg") ? ".ogg" : ".webm";
        const blob = new Blob(this.chunks, { type: mimeType });
        const formData = new FormData();
        formData.append("file", blob, `recording${ext}`);

        const textarea = document.getElementById("response-textarea");
        if (textarea) {
            textarea.placeholder = "⏳ Transcribing...";
        }

        this.button.textContent = "⏳ Transcribing...";
        this.button.disabled = true;

        try {
            const text = await transcribeAudio(formData);
            if (textarea && text) {
                textarea.value = text;
                textarea.placeholder = "Write your response here. Ctrl+Enter to submit. Or use Record/Upload above.";
                textarea.focus();
            }
        } catch (err) {
            alert("Transcription failed: " + err.message);
            if (textarea) {
                textarea.placeholder = "Write your response here. Ctrl+Enter to submit. Or use Record/Upload above.";
            }
        } finally {
            this.button.textContent = "🎤 Record";
            this.button.disabled = false;
        }
    }

    updateUI() {
        if (this.isRecording) {
            this.button.textContent = "⏹ Stop";
            this.button.classList.add("recording");
        } else {
            this.button.textContent = "🎤 Record";
            this.button.classList.remove("recording");
        }
    }
}

function initVoiceRecorder() {
    const buttons = document.querySelectorAll("[data-voice-recorder]");
    buttons.forEach((btn) => new VoiceRecorder(btn));
}


// --- Shared transcription upload function ---
// Posts to /api/transcribe (JSON API) and returns the transcribed text.

async function transcribeAudio(formData) {
    const response = await fetch("/api/transcribe", {
        method: "POST",
        body: formData,
    });

    if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText);
    }

    const data = await response.json();
    return data.text;
}