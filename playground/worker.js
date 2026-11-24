// Runs Python off the page's main thread, so the page stays responsive.
// Downloads Pyodide and x12sdk once (the browser caches them); after that,
// everything a visitor opens is processed here, in their own browser.

const PYODIDE_VERSION = "314.0.7";
const X12SDK_VERSION = "2.4.0";
const PYODIDE_URL = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;

async function start() {
  const { loadPyodide } = await import(PYODIDE_URL + "pyodide.mjs");
  const pyodide = await loadPyodide({ indexURL: PYODIDE_URL });
  await pyodide.loadPackage("micropip");
  await pyodide.pyimport("micropip").install(`x12sdk==${X12SDK_VERSION}`);
  const source = await (await fetch("app.py", { cache: "no-cache" })).text();
  pyodide.FS.writeFile("/home/pyodide/app.py", source);
  pyodide.runPython("import sys; sys.path.insert(0, '/home/pyodide')");
  const app = pyodide.pyimport("app");
  return { app, version: app.version() };
}

const ready = start();

ready.then(
  ({ version }) => postMessage({ type: "ready", version }),
  (error) => postMessage({ type: "failed", message: String(error && error.message || error) }),
);

onmessage = async ({ data }) => {
  const { id, action, args } = data;
  try {
    const { app } = await ready;
    const reply = JSON.parse(app.call(action, JSON.stringify(args)));
    postMessage({ type: "result", id, ...reply });
  } catch (error) {
    // a bug, not a bad file: say so plainly
    postMessage({ type: "result", id, error: "Something went wrong in the playground: " + String(error && error.message || error).split("\n").slice(-2).join(" ") });
  }
};
