### 🧠 System Architecture
```mermaid
graph TD
    subgraph Hardware
        P[Pozyx - MQTT]
        U[Ubisense - UDP]
    end

    subgraph Middleware
        P --> JSON_P[JSON Parser]
        U --> BIN_P[Binary Parser]
        JSON_P --> SS[(System State)]
        BIN_P --> SS
        SS --> FE{Fusion Engine}
        FE -->|Logic| Z[Zone Logic]
        Z -->|Fusion| VT[Virtual Tag]
    end

    subgraph Output
        VT --> WS[WebSocket Manager]
        VT --> Rec[Data Recorder]
        WS --> Dashboard[Live Map]
        Rec --> Files[CSV / ML Dataset]
    end

```mermaid
graph LR
    Input[Data from Sensors] --> Timeout{Timeout < 1.5s?}
    Timeout -->|Yes| Valid{Quality > 0?}
    Timeout -->|No| Offline[Quality = 0]
    Valid -->|X < 20m| Poz[Pozyx Only]
    Valid -->|X > 23.5m| Ubi[Ubisense Only]
    Valid -->|20-23.5m| Fusion[Weighted Average]
    Poz --> Final[Final Tag Position]
    Ubi --> Final
    Fusion --> Final
