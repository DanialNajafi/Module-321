import websocket from "websocket";
const WebSocket = websocket.w3cwebsocket;



const stationConnection = new WebSocket("ws://192.168.101.60:5005/api");


const shipConnection = new WebSocket("ws://192.168.101.61:5000/ship");

const stationMessage = {
  source: "Artemis Station",
  destination: "Shangris Station",
  msg: "Hallo, hier ist Artemis Station"
};

stationConnection.onopen = () => {
  console.log("Verbindung zur Artemis Station hergestellt");

const inteval = setInterval(() => {
  if (shipConnection.connected) {
    shipConnection.send(JSON.stringify({
      from: "Ship 60",
      to: "Ship 61",
      payload: stationMessage
    }));
    console.log("Nachricht an Ship 61 weitergeleitet");
  }
  }, 3000);

setTimeout(() => {
  clearInterval(inteval);
  console.log("Kommunikation nach 30 Sekunden beendet");
}, 30000);
};

shipConnection.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log("Nachricht von: ", message.from);
  console.log("Nachricht von Ship 61 empfangen:", message.payload);
}