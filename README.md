### 🧠 System Architecture
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
