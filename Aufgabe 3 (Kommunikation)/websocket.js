import websocket from "websocket";
const WebSocket = websocket.w3cwebsocket;

const ws = new WebSocket("ws://192.168.101.60:5005/api");
ws.onmessage = (event) => {
  console.log("server <- client: " + event.data);
};
ws.onopen = () => {
  const data = {
    source: "Artemis Station",
    destination: "Shangris Station",
    msg: "Hallo, hier ist Artemis Station"
  };

  ws.send(JSON.stringify(data));
};