const fs = require("fs");

function escapeCssAttr(value) {
  return String(value)
    .replace(/\\/g, "\\\\")
    .replace(/"/g, '\\"')
    .replace(/\n/g, "\\a ")
    .replace(/\r/g, "\\d ");
}

async function waitForRenderReady(page, timeoutMs) {
  const waitBudget = Math.max(timeoutMs - 500, 1000);
  await page.evaluate(async (innerTimeout) => {
    const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

    if (document.fonts && document.fonts.ready) {
      try {
        await Promise.race([
          document.fonts.ready,
          sleep(Math.min(innerTimeout, 1500)),
        ]);
      } catch (_) {
        // ignore font readiness failures and continue with capture
      }
    }

    const images = Array.from(document.images || []);
    await Promise.all(
      images.map(async (img) => {
        try {
          if (img.complete && img.naturalWidth > 0) {
            return;
          }
          if (typeof img.decode === "function") {
            await img.decode();
            return;
          }
          await new Promise((resolve) => {
            img.addEventListener("load", resolve, { once: true });
            img.addEventListener("error", resolve, { once: true });
          });
        } catch (_) {
          // continue even if an image fails to decode
        }
      })
    );

    if (typeof window.__SLIDEHTML_READY__ === "function") {
      try {
        await window.__SLIDEHTML_READY__();
      } catch (_) {
        // treat ready hook failures as non-fatal to keep export resilient
      }
      return;
    }

    if (typeof window.__SLIDEHTML_READY__ === "undefined") {
      return;
    }

    const deadline = Date.now() + innerTimeout;
    while (Date.now() < deadline) {
      if (window.__SLIDEHTML_READY__ === true) {
        return;
      }
      await sleep(25);
    }
    throw new Error("window.__SLIDEHTML_READY__ did not become true before capture");
  }, waitBudget);
}

async function decorateSnapshotWithRenderedAssets(page, snapshot) {
  if (!snapshot || !Array.isArray(snapshot.slides)) {
    return snapshot;
  }

  for (const slide of snapshot.slides) {
    const nodes = Array.isArray(slide.nodes) ? slide.nodes : [];
    for (const node of nodes) {
      const exportMode = String(node.export || "").toLowerCase();
      const shouldRasterize =
        node.kind === "flatten" ||
        node.kind === "svg" ||
        exportMode === "png" ||
        exportMode === "svg";
      const box = node.box || {};
      if (!shouldRasterize || !node.id || Number(box.width || 0) < 1 || Number(box.height || 0) < 1) {
        continue;
      }

      const selector = `[data-sh-id="${escapeCssAttr(node.id)}"]`;
      const locator = page.locator(selector).first();
      if ((await locator.count()) < 1) {
        continue;
      }

      try {
        const png = await locator.screenshot({
          type: "png",
          animations: "disabled",
          scale: "device",
        });
        const dataUri = `data:image/png;base64,${png.toString("base64")}`;
        node.renderedSrc = dataUri;
        node.renderedMimeType = "image/png";
        if (!node.src || node.kind === "flatten" || node.kind === "svg" || exportMode === "png" || exportMode === "svg") {
          node.src = dataUri;
        }
      } catch (_) {
        // leave the node as-is and allow Python fallback behavior
      }
    }
  }

  return snapshot;
}

async function main() {
  const [, , inputPath, outputPath] = process.argv;
  if (!inputPath || !outputPath) {
    throw new Error("usage: playwright_runner.js <input.json> <output>");
  }

  const packageDir = process.env.PLAYWRIGHT_PACKAGE_DIR;
  if (!packageDir) {
    throw new Error("PLAYWRIGHT_PACKAGE_DIR is required");
  }

  const playwright = require(packageDir);
  const payload = JSON.parse(fs.readFileSync(inputPath, "utf8"));
  const browserOrder = Array.isArray(payload.browserOrder) ? payload.browserOrder : ["chromium"];
  const viewport = payload.viewport || { width: 1280, height: 720 };
  const timeoutMs = Number(process.env.PLAYWRIGHT_RUNNER_TIMEOUT_MS || 15000);
  const errors = [];

  for (const browserName of browserOrder) {
    const browserType = playwright[browserName];
    if (!browserType) {
      continue;
    }

    const executablePath =
      typeof browserType.executablePath === "function"
        ? browserType.executablePath()
        : null;
    if (executablePath && !fs.existsSync(executablePath)) {
      errors.push(`[${browserName}] executable not found: ${executablePath}`);
      continue;
    }

    let browser = null;
    try {
      const launchOptions = buildLaunchOptions(browserName);
      browser = await browserType.launch(launchOptions);
      const context = await browser.newContext({ viewport });
      const page = await context.newPage();
      await page.route("**/*", (route) => {
        const url = route.request().url();
        if (/^https?:/i.test(url)) {
          return route.abort();
        }
        return route.continue();
      });
      page.setDefaultTimeout(timeoutMs);
      await page.setContent(payload.html, { waitUntil: "domcontentloaded", timeout: timeoutMs });
      await waitForRenderReady(page, timeoutMs);

      if (payload.mode === "snapshot") {
        if (typeof payload.captureScript !== "string" || !payload.captureScript.trim()) {
          throw new Error("snapshot capture script is missing");
        }
        let result = await page.evaluate((source) => {
          const evaluated = globalThis.eval(`(${source})`);
          return typeof evaluated === "function" ? evaluated() : evaluated;
        }, payload.captureScript);
        if (typeof result === "undefined") {
          throw new Error("snapshot capture script returned undefined");
        }
        result = await decorateSnapshotWithRenderedAssets(page, result);
        fs.writeFileSync(outputPath, JSON.stringify(result), "utf8");
        return;
      }

      if (payload.mode === "pdf") {
        if (browserName !== "chromium") {
          throw new Error("pdf export requires chromium");
        }
        const pdf = await page.pdf(payload.pdfOptions || {});
        fs.writeFileSync(outputPath, pdf);
        return;
      }

      throw new Error(`unsupported mode: ${payload.mode}`);
    } catch (error) {
      errors.push(`[${browserName}] ${error && error.stack ? error.stack : String(error)}`);
    } finally {
      if (browser) {
        try {
          await browser.close();
        } catch (error) {
          // ignore close failures during fallback
        }
      }
    }
  }

  throw new Error(errors.length ? errors.join("\n\n") : "no browser succeeded");
}

function buildLaunchOptions(browserName) {
  const env = { ...process.env };
  const options = {
    headless: true,
    env,
    timeout: Number(process.env.PLAYWRIGHT_RUNNER_TIMEOUT_MS || 15000),
  };

  if (browserName === "chromium") {
    options.chromiumSandbox = false;
  }

  return options;
}

main().catch((error) => {
  const text = error && error.stack ? error.stack : String(error);
  process.stderr.write(`${text}\n`);
  process.exit(1);
});
