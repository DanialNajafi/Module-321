import websocket from "websocket";
import { Client } from "ssh2";

const WebSocket = websocket.w3cwebsocket;
const sshClient = new Client();
let latestMessageForElyse = null;

function goToStation() {
  const payload = JSON.stringify({ target: { x: -70565, y: 72811 } });
  const cmd = `curl -s -XPOST http://192.168.101.60:2009/set_target --data '${payload}'`;
  sshClient.exec(cmd, (err) => { });
}

sshClient
  .on("ready", () => {
    console.log("🚀 SSH-Verbindung zu Ship 60 hergestellt.");
    goToStation();

    // ANTI-DRIFT: Alle 5 Sekunden Kurs neu setzen, damit wir nicht abdriften!
    setInterval(goToStation, 5000);

    console.log("⏳ Warte 10 Sekunden auf Ankunft an der Station...");
    setTimeout(startWebSockets, 10000);
  })
  .connect({ host: "192.168.101.60", port: 22, username: "ship", password: "ship" });

function startWebSockets() {
  const stationConnection = new WebSocket("ws://192.168.101.60:2026/api");
  const shipConnection = new WebSocket("ws://192.168.101.61:5000/");

  stationConnection.onopen = () => console.log("✅ Elyse Terminal verbunden");
  shipConnection.onopen = () => console.log("✅ Partnerschiff verbunden");

  // NACHRICHT EMPFANGEN VON ELYSE
  stationConnection.onmessage = (event) => {
    if (shipConnection.readyState === WebSocket.OPEN) {
      try {
        const received = JSON.parse(event.data);
        const arrayPayload = received.msg || received.data; // Nimmt msg oder data

        // Weiter an Partner
        shipConnection.send(JSON.stringify({
          source: "Elyse Terminal",
          data: arrayPayload, // Sende beides, um sicherzugehen!
          msg: arrayPayload
        }));
      } catch (e) { }
    }
  };

  // NACHRICHT EMPFANGEN VOM PARTNER (in Zwischenablage speichern)
  shipConnection.onmessage = (event) => {
    try {
      latestMessageForElyse = JSON.parse(event.data);
    } catch (e) { }
  };

  // RATE LIMITING (SPAM-SCHUTZ): Nur 1 Nachricht pro Sekunde an Elyse senden!
  setInterval(() => {
    if (latestMessageForElyse && stationConnection.readyState === WebSocket.OPEN) {
      const arrayPayload = latestMessageForElyse.msg || latestMessageForElyse.data;

      const payload = {
        source: "Shangris Station",
        msg: arrayPayload // Elyse erwartet zwingend "msg"
      };

      stationConnection.send(JSON.stringify(payload));
      console.log("⬅️ [1x pro Sekunde] Nachricht an Elyse abgeliefert.");
      latestMessageForElyse = null; // Leeren, damit wir nicht doppelt senden
    }
  }, 1000);
}
