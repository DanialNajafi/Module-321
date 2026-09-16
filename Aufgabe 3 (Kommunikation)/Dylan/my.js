import http from "http";
import pkg from "websocket";
const { server: WebSocketServer, client: WSClient } = pkg;
import { Client } from "ssh2";

const sshClient = new Client();

function goToStation(x, y) {
  const payload = JSON.stringify({ target: { x, y } });
  const cmd = `curl -s -XPOST http://192.168.101.61:2009/set_target --data '${payload}'`;
  sshClient.exec(cmd, (err, stream) => {
    if (err) return console.error("Fehler:", err);
    stream
      .on("close", (code) => console.log("SSH-Befehl beendet, Code:", code))
      .on("data", (d) => console.log("STDOUT:", d.toString()))
      .stderr.on("data", (d) => console.error("STDERR:", d.toString()));
  });
}

let shipToShipConnection = null; // Verbindung zu Ship 60

// 1) Verbindung zum Shangris-Comm-Modul aufbauen
const wsClient = new WSClient();

wsClient.on("connect", (shangrisConn) => {
  console.log("connected (Comm Module Shangris)");

  shangrisConn.on("message", (message) => {
    if (message.type !== "utf8") return;
    console.log("server (Comm Module Shangris) -> client: " + message.utf8Data);

    // Weiterleiten an Ship 60, falls verbunden
    if (shipToShipConnection && shipToShipConnection.connected) {
      shipToShipConnection.sendUTF(message.utf8Data);
      console.log("client -> Ship 60: " + message.utf8Data);
    }
  });

  shangrisConn.on("close", () => console.log("Verbindung zu Comm Module Shangris geschlossen"));

  // Wird aufgerufen, wenn Ship 60 uns etwas schickt -> weiter an Shangris-Modul
  global.forwardToShangris = (data) => {
    if (shangrisConn.connected) {
      console.log("client -> server (Comm Module Shangris): " + data);
      shangrisConn.sendUTF(data);
    }
  };
});

wsClient.on("connectFailed", (err) => console.error("Verbindung zu Shangris-Modul fehlgeschlagen:", err));
wsClient.connect("ws://192.168.101.61:2025/ws");

// 2) Server für Ship 60 (Schiff-zu-Schiff)
sshClient
  .on("ready", () => {
    console.log("SSH-Verbindung zu 192.168.101.61 hergestellt");
    goToStation(4446, 4340);

    const server = http.createServer();
    server.listen(5000, () => console.log("Ship 61 WebSocket-Server läuft auf Port 5000"));

    const wsServer = new WebSocketServer({ httpServer: server, autoAcceptConnections: false });

    wsServer.on("request", (request) => {
      const connection = request.accept(null, request.origin);
      shipToShipConnection = connection;
      console.log("Verbunden mit Ship 60");

      connection.on("message", (message) => {
        if (message.type === "utf8") {
          console.log("Ship 60 -> client: " + message.utf8Data);
          if (global.forwardToShangris) {
            global.forwardToShangris(message.utf8Data);
          }
        }
      });

      connection.on("close", () => {
        console.log("Verbindung zu Ship 60 geschlossen");
        shipToShipConnection = null;
      });
    });
  })
  .on("error", (err) => console.error("SSH-Verbindungsfehler:", err))
  .connect({ host: "192.168.101.61", port: 22, username: "ship", password: "ship" });