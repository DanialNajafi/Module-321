import websocket from "websocket";

import { Client } from "ssh2";

const WebSocket = websocket.w3cwebsocket;

const sshClient = new Client();

function goToStation(x, y) {
  const payload = JSON.stringify({ target: { x, y } });

  const cmd = `curl -s -XPOST http://192.168.101.60:2009/set_target --data '${payload}'`;

  sshClient.exec(cmd, (err, stream) => {
    if (err) {
      console.error("Fehler beim Ausführen des Befehls:", err);

      return;
    }

    stream
      .on("close", (code, signal) => {
        console.log("Befehl abgeschlossen, Code:", code);
      })
      .on("data", (data) => {
        console.log("STDOUT:", data.toString());
      })
      .stderr.on("data", (data) => {
        console.error("STDERR:", data.toString());
      });
  });
}

sshClient

  .on("ready", () => {
    console.log("SSH-Verbindung zu 192.168.101.60 hergestellt");
    // Zielposition setzen (Shangris Station: 4446/4340)
    goToStation(-70565, 72811);
  })

  .on("error", (err) => {
    console.error("SSH-Verbindungsfehler:", err);
  })

  .connect({
    host: "192.168.101.60",
    port: 22,
    username: "ship",
    password: "ship",
  });

const stationConnection = new WebSocket("ws://192.168.101.60:2026/api");

const shipConnection = new WebSocket("ws://192.168.101.61:5000/ship");

let latestStationMessage = null;

stationConnection.onopen = () => {
  console.log("Verbindung zum Comm-Modul hergestellt");
};

stationConnection.onmessage = (event) => {
  console.log("Nachricht von der Station:", event.data);

  latestStationMessage = JSON.parse(event.data);
};

stationConnection.onerror = (error) => {
  console.error("Stations-WebSocket-Fehler:", error);
};

shipConnection.onopen = () => {
  console.log("Verbindung zu Ship 61 hergestellt");
};

const interval = setInterval(() => {
  if (latestStationMessage && shipConnection.readyState === WebSocket.OPEN) {
    shipConnection.send(
      JSON.stringify({
        from: "Ship 60",
        to: "Ship 61",
        payload: latestStationMessage,
      }),
    );

    console.log("Stationsnachricht an Ship 61 weitergeleitet");
  }
}, 3000);

setTimeout(() => {
  clearInterval(interval);
  console.log("Kommunikation nach 30 Sekunden beendet");
}, 30000);

shipConnection.onmessage = (event) => {
  const message = JSON.parse(event.data);

  console.log("Nachricht von:", message.from);
  console.log("Payload:", message.payload);
};
