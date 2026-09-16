import websocket from "websocket";

import { Client } from "ssh2";

const WebSocket = websocket.w3cwebsocket;

const sshClient = new Client();

function goToStation(x, y) {
  const payload = JSON.stringify({ target: { x, y } });

  const cmd = `curl -s -XPOST http://192.168.101.60:2009/set_target --data '${payload}'`;

  sshClient.exec(cmd, (err, stream) => {
    if (err) return console.error("Fehler:", err);

    stream

      .on("close", (code) => console.log("SSH-Befehl beendet, Code:", code))

      .on("data", (d) => console.log("STDOUT:", d.toString()))

      .stderr.on("data", (d) => console.error("STDERR:", d.toString()));
  });
}

sshClient

  .on("ready", () => {
    console.log("SSH-Verbindung zu 192.168.101.60 hergestellt");

    goToStation(-70565, 72811);
  })

  .on("error", (err) => console.error("SSH-Verbindungsfehler:", err))

  .connect({
    host: "192.168.101.60",
    port: 22,
    username: "ship",
    password: "ship",
  });

// Verbindung zum Elyse-Terminal-Comm-Modul

const stationConnection = new WebSocket("ws://192.168.101.60:2026/api");

// Schiff-zu-Schiff Verbindung zu Ship 61

const shipConnection = new WebSocket("ws://192.168.101.61:5000/ship");

stationConnection.onopen = () => {
  console.log("Verbindung zum Elyse-Terminal-Comm-Modul hergestellt");
};

// Echte Nachrichten vom Elyse-Terminal -> weiterleiten an Ship 61

// stationConnection.onmessage = (event) => {
//   console.log("Von Elyse-Terminal-Modul empfangen:", event.data);

//   if (shipConnection.readyState === WebSocket.OPEN) {
//     shipConnection.send(event.data);

//     console.log("An Ship 61 weitergeleitet");
//   }
// };

// Nachrichten von Ship 61 -> weiterleiten an Elyse-Terminal-Modul

shipConnection.onmessage = (event) => {
  console.log("Von Ship 61 empfangen:", event.data);

  if (stationConnection.readyState === WebSocket.OPEN) {
    stationConnection.send(event.data);

    console.log("An Elyse-Terminal-Modul weitergeleitet");
  }
};

shipConnection.onopen = () => {
  console.log("Verbindung zu Ship 61 hergestellt");
};
