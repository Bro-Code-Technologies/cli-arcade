(() => {
  const term = new Terminal({
    cursorBlink: true,
    scrollback: 2000,
    fontSize: 14,
    theme: {
      background: "#0b0f14",
      foreground: "#cdd9e5"
    }
  });

  const fitAddon = new FitAddon.FitAddon();
  term.loadAddon(fitAddon);
  term.open(document.getElementById("terminal"));
  fitAddon.fit();

  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${protocol}://${window.location.host}/ws`);

  socket.addEventListener("open", () => {
    term.focus();
    sendResize();
  });

  socket.addEventListener("message", (ev) => {
    let msg = null;
    try {
      msg = JSON.parse(ev.data);
    } catch (err) {
      term.write(ev.data);
      return;
    }
    if (msg.type === "output") {
      term.write(msg.data);
    }
  });

  term.onData((data) => {
    socket.send(JSON.stringify({ type: "input", data }));
  });

  const sendResize = () => {
    fitAddon.fit();
    socket.send(
      JSON.stringify({ type: "resize", cols: term.cols, rows: term.rows })
    );
  };

  window.addEventListener("resize", () => {
    if (socket.readyState === WebSocket.OPEN) {
      sendResize();
    }
  });

  window.addEventListener("focus", () => term.focus());
})();
