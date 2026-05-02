document.addEventListener("DOMContentLoaded", () => {
    const textarea = document.getElementById("portfolio-text");
    const charCount = document.getElementById("char-count");
    const generateBtn = document.getElementById("generate-btn");
    const landingView = document.getElementById("landing-view");
    const landingStepInput = document.getElementById("landing-step-input");
    const planReview = document.getElementById("plan-review");
    const planOutline = document.getElementById("plan-outline");
    const planTableBody = document.getElementById("plan-table-body");
    const planCancelBtn = document.getElementById("plan-cancel-btn");
    const planRegenerateBtn = document.getElementById("plan-regenerate-btn");
    const planConfirmBtn = document.getElementById("plan-confirm-btn");
    const planningOverlay = document.getElementById("planning-overlay");

    const progressOverlay = document.getElementById("progress-overlay");
    const progressFill = document.getElementById("progress-fill");
    const progressText = document.getElementById("progress-text");
    const progressTitle = document.getElementById("progress-title");
    const progressSlides = document.getElementById("progress-slides");
    const previewView = document.getElementById("preview-view");
    const topbarActions = document.getElementById("topbar-actions");
    const slideStage = document.getElementById("slide-stage");
    const slideViewport = document.getElementById("slide-viewport");
    const thumbnailStrip = document.getElementById("thumbnail-strip");
    const prevBtn = document.getElementById("prev-btn");
    const nextBtn = document.getElementById("next-btn");
    const slideIndexEl = document.getElementById("slide-index");
    const slideTotalEl = document.getElementById("slide-total");
    const slideCountBadge = document.getElementById("slide-count-badge");
    const exportPdfBtn = document.getElementById("export-pdf-btn");
    const exportPptxBtn = document.getElementById("export-pptx-btn");
    const fullscreenLink = document.getElementById("fullscreen-link");
    const newBtn = document.getElementById("new-btn");
    const themeOptionsEl = document.getElementById("theme-options");

    let slides = [];
    let currentSlide = 0;
    let deckId = null;
    let slideCSS = "";
    let generateAbort = null;
    let isGenerating = false;
    /** @type {"idle"|"planning"|"plan_review"|"generating"} */
    let uiPhase = "idle";
    /** @type {{ planId: string, themeId: string, outline: string, pages: object[] } | null} */
    let planState = null;

    /** FastAPI(uvicorn) 기본 포트와 다른 출처에서 열 때 API·프리뷰 URL을 맞춤 (meta api-base 로 수동 지정 가능) */
    function getApiBase() {
        const meta = document.querySelector('meta[name="api-base"]');
        if (meta) {
            const v = (meta.getAttribute("content") || "").trim();
            if (v) return v.replace(/\/$/, "");
        }
        const portMeta = document.querySelector('meta[name="api-port"]')?.getAttribute("content")?.trim();
        const apiPort =
            portMeta && /^\d+$/.test(portMeta) ? portMeta : "8000";
        const { protocol, hostname, port } = window.location;
        if (protocol === "file:") {
            return `http://127.0.0.1:${apiPort}`;
        }
        const host = (hostname || "").toLowerCase();
        const isLocal =
            host === "localhost" ||
            host === "127.0.0.1" ||
            host === "[::1]" ||
            host === "::1";
        const locPortNorm =
            port || (protocol === "https:" ? "443" : "80");
        if (isLocal && locPortNorm !== String(apiPort)) {
            return `http://127.0.0.1:${apiPort}`;
        }
        return "";
    }

    function appUrl(path) {
        const base = getApiBase();
        const p = path.startsWith("/") ? path : "/" + path;
        if (!base) return p;
        return base + p;
    }

    function apiFetch(path, init = {}) {
        const url = appUrl(path);
        const merged = { ...init };
        if (getApiBase()) {
            merged.credentials = merged.credentials ?? "omit";
        }
        return fetch(url, merged);
    }

    function escapeHtml(str) {
        const d = document.createElement("div");
        d.textContent = str == null ? "" : String(str);
        return d.innerHTML;
    }

    function getSelectedThemeId() {
        const el = themeOptionsEl?.querySelector('input[name="theme_id"]:checked');
        return el?.value || "default";
    }

    function renderThemeFallback(reason) {
        const hint =
            reason === "empty"
                ? "서버에서 테마 목록이 비어 있습니다. slide_templates 경로와 서버 로그를 확인해 주세요."
                : "서버에 연결할 수 없거나 응답이 올바르지 않습니다. 주소가 앱 루트(예: /)인지 확인해 주세요.";
        themeOptionsEl.innerHTML = `
                <label class="theme-option">
                    <input type="radio" name="theme_id" value="default" checked />
                    <span class="theme-option-body">
                        <span class="theme-option-title">SlideForge 기본 (폴백)</span>
                        <span class="theme-option-desc">${escapeHtml(hint)}</span>
                        <span class="theme-option-meta">default · /api/themes 재시도됨</span>
                    </span>
                </label>`;
    }

    async function loadThemes() {
        if (!themeOptionsEl) return;
        const tryOnce = async () => {
            const r = await apiFetch("/api/themes");
            if (!r.ok) throw new Error("bad status");
            const themes = await r.json();
            if (!Array.isArray(themes) || themes.length === 0) throw new Error("empty");
            return themes;
        };
        try {
            let themes;
            try {
                themes = await tryOnce();
            } catch (firstErr) {
                await new Promise((r) => setTimeout(r, 400));
                themes = await tryOnce();
            }
            themeOptionsEl.innerHTML = themes
                .map(
                    (t, i) => `
                <label class="theme-option">
                    <input type="radio" name="theme_id" value="${escapeHtml(t.theme_id)}" ${i === 0 ? "checked" : ""} />
                    <span class="theme-option-body">
                        <span class="theme-option-title">${escapeHtml(t.name)}</span>
                        <span class="theme-option-desc">${escapeHtml(t.description)}</span>
                        <span class="theme-option-meta">${t.slide_count}종 슬라이드</span>
                    </span>
                </label>`
                )
                .join("");
        } catch (e) {
            const reason = e && e.message === "empty" ? "empty" : "network";
            renderThemeFallback(reason);
        }
    }

    void loadThemes();

    textarea.addEventListener("input", () => {
        charCount.textContent = textarea.value.length.toLocaleString();
    });

    generateBtn.addEventListener("click", startPlanPhase);

    textarea.addEventListener("keydown", (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
            e.preventDefault();
            startPlanPhase();
        }
    });

    function parseSseBlock(block) {
        let eventName = "message";
        const dataParts = [];
        for (const line of block.split("\n")) {
            if (line.startsWith("event:")) eventName = line.slice(6).trim();
            else if (line.startsWith("data:")) {
                const rest = line.slice(5);
                dataParts.push(rest.startsWith(" ") ? rest.slice(1) : rest);
            }
        }
        if (!dataParts.length) return null;
        return { event: eventName, data: dataParts.join("\n") };
    }

    async function consumeSseStream(response, onEvent) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";
        while (true) {
            const { done, value } = await reader.read();
            buf += decoder.decode(value || new Uint8Array(), { stream: !done });
            buf = buf.replace(/\r\n/g, "\n");
            let pos;
            while ((pos = buf.indexOf("\n\n")) !== -1) {
                const raw = buf.slice(0, pos).trim();
                buf = buf.slice(pos + 2);
                if (!raw) continue;
                const ev = parseSseBlock(raw);
                if (ev) {
                    const out = onEvent(ev);
                    if (out != null && typeof out.then === "function") {
                        await out;
                    }
                }
            }
            if (done) break;
        }
    }

    function hideProgressOverlay() {
        progressOverlay.classList.add("hidden");
        progressOverlay.classList.remove("progress-overlay--dock");
        progressOverlay.setAttribute("aria-hidden", "true");
    }

    function showProgressOverlayDocked() {
        progressOverlay.classList.remove("hidden");
        progressOverlay.classList.add("progress-overlay--dock");
        progressOverlay.setAttribute("aria-hidden", "false");
    }

    function resetToLandingFromGeneration() {
        landingView.classList.remove("hidden");
        landingStepInput.classList.remove("hidden");
        planReview.classList.add("hidden");
        previewView.classList.add("hidden");
        previewView.classList.remove("preview-view--generating");
        topbarActions.classList.add("hidden");
        hideProgressOverlay();
        slides = [];
        currentSlide = 0;
        deckId = null;
        slideCSS = "";
        slideStage.innerHTML = "";
        thumbnailStrip.innerHTML = "";
        isGenerating = false;
        uiPhase = "idle";
        planState = null;
        exportPdfBtn.disabled = false;
        exportPptxBtn.disabled = false;
        newBtn.disabled = false;
        generateBtn.disabled = false;
    }

    function showSlideSkeleton() {
        slideStage.innerHTML = `
            <div class="slide-skeleton-wrap">
                <div class="slide-skeleton" aria-hidden="true"></div>
                <p class="slide-skeleton-label">슬라이드 준비 중…</p>
            </div>`;
    }

    async function handleIncomingSlide(data) {
        if (!deckId) return;
        if (!slideCSS) {
            slideCSS = await fetchSlideCSS();
        }
        slides.push(data);
        slideTotalEl.textContent = slides.length;
        slideCountBadge.textContent = slides.length;
        const pct = Math.min(10 + slides.length * 12, 88);
        progressFill.style.width = pct + "%";
        progressText.textContent = `${slides.length}장 수신 · ${data.template}`;

        const chip = document.createElement("span");
        chip.className = "progress-chip";
        chip.textContent = `#${slides.length} ${data.template}`;
        progressSlides.appendChild(chip);

        slideStage.querySelector(".slide-skeleton-wrap")?.remove();
        addThumbnail(data, slides.length - 1);
        goToSlide(slides.length - 1);
        requestAnimationFrame(() => {
            scaleSlide();
            refreshThumbnailScales();
        });
    }

    async function fetchSlideKinds(themeId) {
        const r = await apiFetch(`/api/slide-kinds/${encodeURIComponent(themeId)}`);
        if (!r.ok) throw new Error("slide-kinds");
        return r.json();
    }

    function renderPlanTable(pages, kinds) {
        const opts = (sel) =>
            kinds
                .map(
                    (k) =>
                        `<option value="${escapeHtml(k.id)}" ${k.id === sel ? "selected" : ""}>${escapeHtml(k.name)}</option>`
                )
                .join("");
        planTableBody.innerHTML = pages
            .map((p) => {
                const kp = (p.key_points || []).join("\n");
                return `<tr data-plan-index="${p.index}">
                    <td class="plan-td-idx">${p.index}</td>
                    <td><select class="plan-template-select" aria-label="슬라이드 종류">${opts(p.template)}</select></td>
                    <td><input type="text" class="plan-title-input" value="${escapeHtml(p.title)}" /></td>
                    <td><textarea class="plan-purpose-input" rows="2">${escapeHtml(p.purpose)}</textarea></td>
                    <td><textarea class="plan-kp-input" rows="2" placeholder="한 줄에 하나">${escapeHtml(kp)}</textarea></td>
                </tr>`;
            })
            .join("");
    }

    function collectPlanPagesFromDom() {
        const rows = planTableBody.querySelectorAll("tr[data-plan-index]");
        const pages = [];
        rows.forEach((row) => {
            const idx = parseInt(row.getAttribute("data-plan-index"), 10);
            const template = row.querySelector(".plan-template-select").value;
            const title = row.querySelector(".plan-title-input").value.trim();
            const purpose = row.querySelector(".plan-purpose-input").value.trim();
            const kpRaw = row.querySelector(".plan-kp-input").value;
            const key_points = kpRaw
                .split("\n")
                .map((s) => s.trim())
                .filter(Boolean);
            pages.push({ index: idx, template, title, purpose, key_points });
        });
        return pages.sort((a, b) => a.index - b.index);
    }

    function showPlanReview(data) {
        planState = {
            planId: data.plan_id,
            themeId: data.theme_id,
            outline: data.outline,
            pages: data.pages,
        };
        planOutline.textContent = data.outline;
        void fetchSlideKinds(data.theme_id)
            .then((kinds) => {
                renderPlanTable(data.pages, kinds);
            })
            .catch(() => {
                renderPlanTable(
                    data.pages,
                    data.pages.map((p) => ({ id: p.template, name: p.template }))
                );
            });
        landingStepInput.classList.add("hidden");
        planReview.classList.remove("hidden");
        uiPhase = "plan_review";
    }

    async function startPlanPhase() {
        const text = textarea.value.trim();
        if (!text) return;
        if (uiPhase === "planning" || isGenerating) return;

        uiPhase = "planning";
        generateBtn.disabled = true;
        planningOverlay.classList.remove("hidden");

        try {
            const resp = await apiFetch("/api/plan", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text, theme_id: getSelectedThemeId() }),
            });
            if (!resp.ok) {
                let msg = "플랜 생성에 실패했습니다.";
                try {
                    const errBody = await resp.json();
                    if (typeof errBody.detail === "string") msg = errBody.detail;
                    else if (Array.isArray(errBody.detail))
                        msg = errBody.detail.map((d) => d.msg || d).join(" ");
                } catch {}
                if (resp.status === 404) {
                    msg =
                        "API를 찾을 수 없습니다(404). uvicorn이 떠 있는지 확인하고, 가능하면 브라우저에서 http://127.0.0.1:8000/ 로 앱을 여세요.";
                }
                alert(msg);
                uiPhase = "idle";
                return;
            }
            const data = await resp.json();
            showPlanReview(data);
        } catch (e) {
            alert(e.message || "네트워크 오류");
            uiPhase = "idle";
        } finally {
            planningOverlay.classList.add("hidden");
            generateBtn.disabled = false;
        }
    }

    planCancelBtn.addEventListener("click", () => {
        planReview.classList.add("hidden");
        landingStepInput.classList.remove("hidden");
        planState = null;
        uiPhase = "idle";
    });

    planRegenerateBtn.addEventListener("click", () => {
        planReview.classList.add("hidden");
        landingStepInput.classList.remove("hidden");
        void startPlanPhase();
    });

    planConfirmBtn.addEventListener("click", () => {
        if (!planState) return;
        const pages = collectPlanPagesFromDom();
        void startDeckGeneration(planState.planId, pages);
    });

    async function startDeckGeneration(planId, pages) {
        if (generateAbort) generateAbort.abort();
        generateAbort = new AbortController();

        isGenerating = true;
        uiPhase = "generating";
        generateBtn.disabled = true;
        exportPdfBtn.disabled = true;
        exportPptxBtn.disabled = true;
        newBtn.disabled = true;

        slides = [];
        currentSlide = 0;
        deckId = null;
        slideCSS = "";
        thumbnailStrip.innerHTML = "";
        progressSlides.innerHTML = "";

        landingView.classList.add("hidden");
        planReview.classList.add("hidden");
        previewView.classList.remove("hidden");
        previewView.classList.add("preview-view--generating");
        topbarActions.classList.remove("hidden");
        fullscreenLink.href = "#";
        showSlideSkeleton();

        showProgressOverlayDocked();
        progressFill.style.width = "4%";
        progressTitle.textContent = "2단계 · 실시간 생성";
        progressText.textContent = "슬라이드 HTML을 스트리밍합니다…";

        let settled = false;

        const finishWithError = (msg) => {
            settled = true;
            isGenerating = false;
            uiPhase = "idle";
            progressTitle.textContent = "오류 발생";
            progressText.textContent = msg;
            progressFill.style.width = "0%";
            setTimeout(() => {
                resetToLandingFromGeneration();
                generateBtn.disabled = false;
            }, 2200);
        };

        const onDisconnect = () => {
            if (settled) return;
            if (slides.length > 0 && deckId) {
                progressTitle.textContent = "연결 종료";
                progressText.textContent = `${slides.length}장까지 수신되었습니다. 새로고침 후 다시 시도해 주세요.`;
                isGenerating = false;
                uiPhase = "idle";
                generateBtn.disabled = false;
                exportPdfBtn.disabled = false;
                exportPptxBtn.disabled = false;
                newBtn.disabled = false;
                previewView.classList.remove("preview-view--generating");
                hideProgressOverlay();
                return;
            }
            progressTitle.textContent = "연결 끊김";
            progressText.textContent = "서버와의 연결이 끊어졌습니다.";
            setTimeout(() => {
                resetToLandingFromGeneration();
                generateBtn.disabled = false;
            }, 2000);
        };

        try {
            const resp = await apiFetch("/api/generate", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Accept: "text/event-stream",
                },
                body: JSON.stringify({ plan_id: planId, pages }),
                signal: generateAbort.signal,
            });

            if (!resp.ok) {
                let msg = "생성 요청이 거절되었습니다.";
                try {
                    const errBody = await resp.json();
                    if (typeof errBody.detail === "string") msg = errBody.detail;
                    else if (Array.isArray(errBody.detail))
                        msg = errBody.detail.map((d) => d.msg || d).join(" ");
                } catch {}
                finishWithError(msg);
                return;
            }

            await consumeSseStream(resp, async (ev) => {
                if (ev.event === "generation_started") {
                    try {
                        const data = JSON.parse(ev.data);
                        deckId = data.deck_id;
                        fullscreenLink.href = appUrl(`/preview/${deckId}`);
                        progressText.textContent = "덱이 준비되었습니다. 스타일을 불러오는 중…";
                        slideCSS = "";
                        try {
                            slideCSS = await fetchSlideCSS();
                        } catch {}
                        progressText.textContent = "슬라이드를 받는 중…";
                    } catch {}
                } else if (ev.event === "slide_ready") {
                    await handleIncomingSlide(JSON.parse(ev.data));
                } else if (ev.event === "slide_error") {
                    const data = JSON.parse(ev.data);
                    if (data.retrying) {
                        progressText.textContent = `슬라이드 ${data.index + 1} 재검증·재생성 중…`;
                    }
                } else if (ev.event === "deck_complete") {
                    settled = true;
                    isGenerating = false;
                    uiPhase = "idle";
                    const data = JSON.parse(ev.data);
                    deckId = data.deck_id;
                    progressFill.style.width = "100%";
                    progressTitle.textContent = "생성 완료";
                    progressText.textContent = `총 ${data.total_slides}장이 준비되었습니다`;

                    setTimeout(() => {
                        hideProgressOverlay();
                        previewView.classList.remove("preview-view--generating");
                        generateBtn.disabled = false;
                        exportPdfBtn.disabled = false;
                        exportPptxBtn.disabled = false;
                        newBtn.disabled = false;
                        planState = null;
                        if (slides.length) {
                            goToSlide(0);
                            requestAnimationFrame(() => {
                                scaleSlide();
                                refreshThumbnailScales();
                            });
                        }
                    }, 480);
                } else if (ev.event === "error") {
                    let msg = "생성 중 오류가 발생했습니다.";
                    try {
                        const data = JSON.parse(ev.data);
                        msg = data.message || msg;
                    } catch {}
                    finishWithError(msg);
                }
            });

            if (!settled) onDisconnect();
        } catch (e) {
            if (e.name === "AbortError") {
                isGenerating = false;
                uiPhase = "idle";
                generateBtn.disabled = false;
                return;
            }
            finishWithError(e.message || "네트워크 오류가 발생했습니다.");
        } finally {
            generateAbort = null;
        }
    }

    async function fetchSlideCSS() {
        try {
            const resp = await apiFetch(`/preview/${deckId}`);
            const html = await resp.text();
            const match = html.match(/<style>([\s\S]*?)<\/style>/);
            if (match) return match[1];
        } catch {}
        return "";
    }

    function renderSlideHTML(html) {
        const wrapper = document.createElement("div");
        if (slideCSS) {
            const styleEl = document.createElement("style");
            styleEl.textContent = slideCSS;
            wrapper.appendChild(styleEl);
        }
        wrapper.innerHTML += html;
        return wrapper;
    }

    function goToSlide(index) {
        if (index < 0 || index >= slides.length) return;
        currentSlide = index;

        slideStage.innerHTML = "";
        slideStage.appendChild(renderSlideHTML(slides[index].html));
        scaleSlide();

        slideIndexEl.textContent = index + 1;
        prevBtn.disabled = index === 0;
        nextBtn.disabled = index === slides.length - 1;

        thumbnailStrip.querySelectorAll(".thumbnail").forEach((t, i) => {
            t.classList.toggle("active", i === index);
            if (i === index) t.scrollIntoView({ block: "nearest", behavior: "smooth" });
        });
    }

    function scaleSlide() {
        const vw = slideViewport.clientWidth;
        const vh = slideViewport.clientHeight;
        if (vw <= 0 || vh <= 0) return;
        const scale = Math.min(vw / 1280, vh / 720);
        slideStage.style.transform = `scale(${scale})`;
    }

    function refreshThumbnailScales() {
        thumbnailStrip.querySelectorAll(".thumbnail").forEach((thumb) => {
            const inner = thumb.querySelector(".thumbnail-inner");
            if (!inner) return;
            const w = thumb.clientWidth;
            if (w <= 0) return;
            inner.style.transform = `scale(${w / 1280})`;
        });
    }

    function addThumbnail(slide, index) {
        const thumb = document.createElement("div");
        thumb.className = "thumbnail" + (index === 0 ? " active" : "");

        const inner = document.createElement("div");
        inner.className = "thumbnail-inner";
        if (slideCSS) {
            const s = document.createElement("style");
            s.textContent = slideCSS;
            inner.appendChild(s);
        }
        inner.innerHTML += slide.html;

        const label = document.createElement("div");
        label.className = "thumbnail-label";
        label.textContent = `${index + 1}`;

        thumb.appendChild(inner);
        thumb.appendChild(label);
        thumb.addEventListener("click", () => goToSlide(index));
        thumbnailStrip.appendChild(thumb);
        requestAnimationFrame(() => {
            const w = thumb.clientWidth || 176;
            inner.style.transform = `scale(${w / 1280})`;
        });
    }

    prevBtn.addEventListener("click", () => goToSlide(currentSlide - 1));
    nextBtn.addEventListener("click", () => goToSlide(currentSlide + 1));

    document.addEventListener("keydown", (e) => {
        if (previewView.classList.contains("hidden")) return;
        if (e.target.tagName === "TEXTAREA" || e.target.tagName === "INPUT") return;
        if (e.key === "ArrowLeft") goToSlide(currentSlide - 1);
        if (e.key === "ArrowRight") goToSlide(currentSlide + 1);
    });

    function onPreviewLayoutResize() {
        if (previewView.classList.contains("hidden")) return;
        scaleSlide();
        refreshThumbnailScales();
    }

    window.addEventListener("resize", onPreviewLayoutResize);

    if (typeof ResizeObserver !== "undefined") {
        const previewLayoutObserver = new ResizeObserver(() =>
            requestAnimationFrame(onPreviewLayoutResize)
        );
        previewLayoutObserver.observe(slideViewport);
        previewLayoutObserver.observe(thumbnailStrip);
    }

    newBtn.addEventListener("click", () => {
        if (isGenerating) return;
        previewView.classList.add("hidden");
        previewView.classList.remove("preview-view--generating");
        topbarActions.classList.add("hidden");
        landingView.classList.remove("hidden");
        landingStepInput.classList.remove("hidden");
        planReview.classList.add("hidden");
        slides = [];
        currentSlide = 0;
        deckId = null;
        slideCSS = "";
        slideStage.innerHTML = "";
        thumbnailStrip.innerHTML = "";
        planState = null;
        uiPhase = "idle";
    });

    async function doExport(type, btn) {
        if (!deckId) return;
        btn.disabled = true;
        const origContent = btn.innerHTML;
        btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><circle cx="7" cy="7" r="5" stroke="currentColor" stroke-width="1.5" stroke-dasharray="20" stroke-dashoffset="5"><animateTransform attributeName="transform" type="rotate" from="0 7 7" to="360 7 7" dur=".6s" repeatCount="indefinite"/></circle></svg> 생성 중`;
        try {
            const resp = await apiFetch(`/api/decks/${deckId}/export/${type}`, { method: "POST" });
            if (!resp.ok) throw new Error(await resp.text());
            const blob = await resp.blob();
            downloadBlob(blob, `portfolio.${type}`);
        } catch (err) {
            alert(`${type.toUpperCase()} 생성 실패: ${err.message}`);
        } finally {
            btn.disabled = false;
            btn.innerHTML = origContent;
        }
    }

    exportPdfBtn.addEventListener("click", () => doExport("pdf", exportPdfBtn));
    exportPptxBtn.addEventListener("click", () => doExport("pptx", exportPptxBtn));

    function downloadBlob(blob, filename) {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
});
