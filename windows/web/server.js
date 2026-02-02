const path = require("path");
require("dotenv").config();
const http = require("http");
const express = require("express");
const { WebSocketServer } = require("ws");
const pty = require("node-pty");

const app = express();
const server = http.createServer(app);
const wss = new WebSocketServer({ server, path: "/ws" });

const projectRoot = path.resolve(__dirname, "..");
const cliPath = path.join(projectRoot, "cli.py");

app.use(express.static(path.join(__dirname, "public")));

const startPty = () => {
  const override = process.env.CLI_ARCADE_PY;
  const isWin = process.platform === "win32";
  let pythonCmd = override || (isWin ? "py" : "python3");
  let args = [cliPath];
  if (!override && isWin) {
    args = ["-3", cliPath];
  }

  return pty.spawn(pythonCmd, args, {
    name: "xterm-256color",
    cwd: projectRoot,
    env: { ...process.env, TERM: "xterm-256color" },
    cols: 100,
    rows: 30
  });
};

wss.on("connection", (ws) => {
  let shell = null;
  let pendingCols = 100;
  let pendingRows = 30;
  try {
    ws.send(JSON.stringify({ type: "output", data: "\r\n[Press Enter to start]\r\n" }));
  } catch (err) {
    // ignore
  }

  const attachPty = () => {
    shell = startPty();
    if (pendingCols && pendingRows) {
      try {
        shell.resize(pendingCols, pendingRows);
      } catch (err) {
        // ignore
      }
    }
    shell.onData((data) => {
      ws.send(JSON.stringify({ type: "output", data }));
    });

    shell.onExit(() => {
      shell = null;
      try {
        ws.send(JSON.stringify({ type: "output", data: "\r\n[CLI exited. Press Enter to restart]\r\n" }));
      } catch (err) {
        // ignore
      }
    });
  };

  ws.on("message", (raw) => {
    let msg = null;
    try {
      msg = JSON.parse(raw.toString());
    } catch (err) {
      shell.write(raw.toString());
      return;
    }

    if (msg.type === "input" && typeof msg.data === "string") {
      if (!shell) {
        if (msg.data.includes("\r") || msg.data.includes("\n")) {
          try {
            ws.send(JSON.stringify({ type: "output", data: "\x1bc" }));
          } catch (err) {
            // ignore
          }
          attachPty();
        }
        return;
      }
      shell.write(msg.data);
    } else if (msg.type === "resize") {
      const cols = Math.max(20, Number(msg.cols) || 80);
      const rows = Math.max(10, Number(msg.rows) || 24);
      pendingCols = cols;
      pendingRows = rows;
      if (shell) {
        shell.resize(cols, rows);
      }
    }
  });

  ws.on("close", () => {
    try {
      if (shell) {
        shell.kill();
      }
    } catch (err) {
      // ignore
    }
  });
});

const port = Number(process.env.PORT || 3000);
server.listen(port, () => {
  console.log(`CLI Arcade web terminal on http://localhost:${port}`);
});
