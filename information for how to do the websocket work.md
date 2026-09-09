Jetzt ist die Aufgabe klarer: Ihr braucht **zwei Verbindungen**.

1. **Von eurem Schiff zur Raumstation**, um Nachrichten zu empfangen.
2. **Zwischen euren Schiffs-VMs**, um diese Nachrichten weiterzuleiten.

Euer aktueller Code macht nur Verbindung 1 und sendet genau **eine** Nachricht. Für die Aufgabe braucht ihr zusätzlich einen eigenen WebSocket-Server auf eurem Schiff und eine Wiederholung mindestens alle drei Sekunden.

## Architektur

Beispiel:

```text
Ship 60 ── WebSocket ──> Raumstation 192.168.101.60:5005/api
Ship 61 ── WebSocket ──> Raumstation 192.168.101.60:5005/api

Ship 60 <── eigener WebSocket ──> Ship 61
       z. B. Port 5000
```

Port `5000` darf verwendet werden, weil er größer oder gleich `5000` ist. Beide VMs können denselben Port verwenden, weil sie unterschiedliche IP-Adressen haben:

```text
Ship 60: 192.168.101.60:5000
Ship 61: 192.168.101.61:5000
```

## Wichtig für deinen aktuellen Code

Diese Adresse:

```js
ws://192.168.101.60:5005/api
```

ist vermutlich die **Raumstation**. Sie ist nicht automatisch die Adresse des anderen Schiffs.

Für die Kommunikation zwischen Schiffen braucht ihr beispielsweise:

```js
ws://192.168.101.61:5000/ship
```

Ship 61 muss dafür auf Port `5000` einen WebSocket-Server öffnen.

## Kontinuierliche Weiterleitung

Die Logik muss ungefähr so aussehen:

```js
const stationMessage = {
  source: "Artemis Station",
  destination: "Shangris Station",
  msg: "Nachricht von der Raumstation"
};

shipConnection.send(JSON.stringify({
  from: "Ship 60",
  to: "Ship 61",
  payload: stationMessage
}));
```

Alle drei Sekunden:

```js
const interval = setInterval(() => {
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
  clearInterval(interval);
  console.log("Kommunikation nach 20 Sekunden beendet");
}, 20000);
```

Auf Ship 61 empfängt ihr die Nachrichten weiterhin mit `onmessage`:

```js
shipConnection.onmessage = (event) => {
  const message = JSON.parse(event.data);

  console.log("Von:", message.from);
  console.log("Stationsnachricht:", message.payload);
};
```

Damit erfüllt ihr:

- WebSocket als Client zur Raumstation
- eigene WebSocket-Kommunikation zwischen den VMs
- Weiterleitung mindestens alle drei Sekunden
- Kommunikation über mindestens 20 Sekunden
- Verwendung eines Ports ab `5000`

Die genaue IP-Adresse für Ship 61 muss die IP-Adresse der **anderen VM** sein. Sie sollte nicht automatisch mit der Raumstations-IP `192.168.101.60` gleichgesetzt werden.






dylan:
import websocket from "websocket";
const WebSocket = websocket.w3cwebsocket;
 
const ws = new WebSocket("ws://192.168.101.61:2025/ws");
ws.onmessage = (event) => {
  console.log("server <- client: " + event.data);
};
ws.onopen = () => {
  console.log("connected");
  {
    const data = { source: "Artemis Station", data: [1, 2, 3, 4] };
    console.log("client -> server: " + JSON.stringify(data));
    ws.send(JSON.stringify(data));
  }
};
 