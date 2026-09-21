const http = require("http");
const WebSocketServer = require("websocket").server;
const WSClient = require("websocket").client;
const { Client } = require("ssh2");

const sshClient = new Client();
let shipToShipConnection = null;
let latestMessageForShangris = null;

function goToStation() {
  const payload = JSON.stringify({ target: { x: 4446, y: 4340 } });
  const cmd = "curl -s -XPOST http://192.168.101.61:2009/set_target --data '" + payload + "'";
  sshClient.exec(cmd, (err) => {});
}

sshClient
  .on("ready", () => {
    console.log("🚀 SSH-Verbindung zu Ship 61 hergestellt.");
    goToStation();
    
    // ANTI-DRIFT: Alle 5 Sekunden Kurs neu setzen!
    setInterval(goToStation, 5000);

    const server = http.createServer();
    server.listen(5000, () => console.log("✅ Ship 61 Server läuft auf Port 5000"));
    const wsServer = new WebSocketServer({ httpServer: server, autoAcceptConnections: false });

    wsServer.on("request", (request) => {
      const connection = request.accept(null, request.origin);
      shipToShipConnection = connection;
      console.log("🤝 Ship 60 verbunden!");

      // VOM PARTNER EMPFANGEN (in Zwischenablage speichern)
      connection.on("message", (message) => {
        if (message.type === "utf8") {
          try {
            latestMessageForShangris = JSON.parse(message.utf8Data);
          } catch (e) {}
        }
      });
    });

    console.log("⏳ Warte 10 Sekunden auf Ankunft an der Station...");
    setTimeout(connectToShangris, 10000);
  })
  .connect({ host: "192.168.101.61", port: 22, username: "ship", password: "ship" });

function connectToShangris() {
  const wsClient = new WSClient();

  wsClient.on("connect", (shangrisConn) => {
    console.log("✅ Shangris Comm-Modul verbunden!");

    // VON SHANGRIS EMPFANGEN -> AN PARTNER SENDEN
    shangrisConn.on("message", (message) => {
      if (message.type === "utf8" && shipToShipConnection && shipToShipConnection.connected) {
        try {
          const received = JSON.parse(message.utf8Data);
          const arrayPayload = received.msg || received.data;
          
          shipToShipConnection.sendUTF(JSON.stringify({ 
            source: "Shangris Station", 
            data: arrayPayload,
            msg: arrayPayload
          }));
        } catch (e) {}
      }
    });

    // RATE LIMITING (SPAM-SCHUTZ): Nur 1 Nachricht pro Sekunde an Shangris senden!
    setInterval(() => {
      if (latestMessageForShangris && shangrisConn.connected) {
        const arrayPayload = latestMessageForShangris.msg || latestMessageForShangris.data;
        
        const payload = {
          source: "Elyse Terminal",
          data: arrayPayload // Shangris erwartet höchstwahrscheinlich "data"
        };
        
        shangrisConn.sendUTF(JSON.stringify(payload));
        console.log("⬅️ [1x pro Sekunde] Nachricht an Shangris abgeliefert.");
        latestMessageForShangris = null; // Leeren
      }
    }, 1000);
  });

  wsClient.connect("ws://192.168.101.61:2025/ws");
}