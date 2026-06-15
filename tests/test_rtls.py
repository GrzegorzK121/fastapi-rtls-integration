import pytest
import json
import struct
import config
from fusion_engine import parse_pozyx_payload, parse_ubisense_binary
from recorder import DataRecorder, ConnectionManager

# ==============================================================================
# TESTY DLA SYSTEMU POZYX - JSON / MQTT
# ==============================================================================

def test_parse_pozyx_real_data():
    """
    Test na prawdziwym JSON-ie wyciągniętym z logów z systemu.
    Notatka dla mnie: Zawsze lepiej testować na prawdziwych zrzutach (Record/Replay) 
    niż ręcznie wymyślać dane, bo wychodzą potem głupoty na produkcji.
    """
    
    # Surowy string wyciągnięty z testów, gdzie rejestrowano odczyty, za pomocą trybu ML_Record
    real_json = '''[{
        "version":"2.0",
        "tagId":"200000297",
        "timestamp":1776879440.1924548,
        "data":{
            "metrics":{"latency":20,"rates":{"success":9.96,"update":9.96,"packetLoss":0.1}},
            "tagData":{"blinkIndex":43986926},
            "anchorData":[
                {"tagId":"200000297","anchorId":"5816","rss":-80.5},
                {"tagId":"200000297","anchorId":"5846","rss":-87.52}
            ],
            "coordinates":{"x":-606,"y":1186,"z":500},
            "position_score":89.99864568024857,
            "zones":[],
            "type":1
        },
        "gateway_name":"GHxXSs4u3",
        "success":true
    }]'''

    result = parse_pozyx_payload(real_json)

    assert result is not None
    assert result["id"] == "200000297"
    assert result["system"] == "Pozyx"
    assert result["hw_timestamp"] == "43986926"

    # --- MATEMATYKA OFFSETÓW (zostawiam rozpisane, żeby się nie zaciąć na obronie) ---
    # X z JSONA to -606 mm = -0.606 m. 
    # Warunek (x < 3.0) wchodzi w POZYX_OFFSET_X -2.06 + 3
    # Wynik: -0.606 - 2.06 + 3 = 0.334 m -> Zaokrąglane do 0.33
    assert result["x"] == 0.33
    
    # Y z JSONA to 1186 mm = 1.186 m.
    # Wynik: 1.186 + 0.61 (POZYX_OFFSET_Y) + 3 = 4.796 m -> Zaokrąglane do 4.80
    assert result["y"] == 4.80
    
    # Z z JSONA to 500 mm = 0.50 m
    assert result["z"] == 0.50

    # Jakość to ułamek 89.9986... Algorytm odcina/zaokrągla do 90.
    assert result["raw_quality"] == 90
    assert result["quality"] == "90%"

def test_parse_pozyx_payload_invalid_data():
    """Co jak broker MQTT rzuci jakimiś śmieciami? Aplikacja ma przeżyć i zwrócić None."""
    result = parse_pozyx_payload("to_nie_jest_json_tylko_jakis_smiec")
    assert result is None


# Używam parametryzacji, żeby nie pisać kodu dwa razy. 
# Złota zasada DRY (Don't Repeat Yourself) - fajnie wygląda w CV.
@pytest.mark.parametrize("raw_x_mm, expected_x_approx", [
    (2000, 2.94),   # Blisko: (2.0) - 2.06 + 3 = 2.94
    (4000, 4.0),    # Daleko: (4.0) + 0.00 = 4.0
])
def test_pozyx_offsets_logic(raw_x_mm, expected_x_approx):
    """Sprawdzam, czy algorytm na pewno dobrze przełącza strefy kompensacji (blisko/daleko)."""
    raw_payload = json.dumps([{
        "success": True,
        "tagId": "test_tag",
        "data": {"coordinates": {"x": raw_x_mm, "y": 0, "z": 0}}
    }])
    
    result = parse_pozyx_payload(raw_payload)
    # Używam approx, bo po dodawaniu floatów w Pythonie lubią wychodzić liczby typu 2.940000000001
    assert result["x"] == pytest.approx(expected_x_approx, 0.01)


# ==============================================================================
# TESTY DLA SYSTEMU UBISENSE - UDP / BINARNE
# ==============================================================================

def test_parse_ubisense_real_data():
    """
    Test parsowania binarnych ramek (bajtów) wyciągniętych z Wiresharka/logów.
    Tutaj dekodujemy surowego structa z sieci.
    """
    # Prawdziwy zrzut (hex dump) wyciągnięty z testów, gdzie rejestrowano odczyty, za pomocą trybu ML_Record
    raw_hex = "e298026b0011ce000000597d0000000160bd8f41ce0ef2405c174e40cb5e863f1210ab4d0e88d000"
    real_payload = bytes.fromhex(raw_hex)
    
    result = parse_ubisense_binary(real_payload)
    
    assert result is not None
    assert result["id"] == "00:11:ce:00:00:00:59:7d"
    assert result["system"] == "Ubisense"
    assert result["hw_timestamp"] == "1210AB4D0E88D000"
    
    # --- Matematyka offsetów z config.py ---
    # X surowe = 17.967, + offset UBISENSE (19.76) = 37.73
    assert result["x"] == 37.73
    # Y surowe = 7.564, + offset UBISENSE (-5.18) = 2.38
    assert result["y"] == 2.38
    assert result["z"] == 3.22
    
    # Wariancja wychodzi na ~1.049. Wzór 100-(1.049*50) daje float 47.5.
    # System odcina resztę w int(), więc daję listę w razie błędu reprezentacji zmiennoprzecinkowej.
    assert result["raw_quality"] in [47, 48]
    assert result["quality"] in ["47%", "48%"]

def test_parse_ubisense_invalid_status():
    """Test zachowania przy błędzie w ramce (podmieniony status w hex)."""
    # Zamieniłem bajty statusu z '01' na '02', żeby był błąd
    bad_hex = "e298026b0011ce000000597d0000000260bd8f41ce0ef2405c174e40cb5e863f1210ab4d0e88d000"
    result = parse_ubisense_binary(bytes.fromhex(bad_hex))
    
    assert result is not None
    assert result["raw_quality"] == 0
    assert result["quality"] == "Błąd: 2"



# ==============================================================================
# TESTY MODUŁÓW (PLIKI / WEBSOCKETS)
# ==============================================================================

def test_data_recorder_start_and_write(tmp_path):
    """
    Test modułu zapisu (DataRecorder).
    Genialny trik z tmp_path - PyTest zakłada tymczasowy folder dla testu i go sam potem usuwa.
    Dzięki temu nie syfię sobie folderu 'RECORDS' na komputerze testowymi CSV-kami!
    """
    recorder = DataRecorder()
    
    # Zapisuj do folderu tymczasowego od PyTesta
    recorder.records_dir = tmp_path
    recorder.start_recording("Magisterka_TestLog", ".csv")
    
    assert recorder.is_saving_data is True
    assert recorder.file_handle is not None

    # Wrzucamy zmyśloną klatkę do zapisania
    fake_state = {
        "tag1": {"system": "Pozyx", "x": 10.0, "y": 5.0, "z": 0, "quality": "80%"}
    }
    recorder.write_frame(fake_state)
    recorder.stop_recording()

    # Sprawdzam, czy plik fizycznie się utworzył w tym wirtualnym folderze
    files = list(tmp_path.iterdir())
    assert len(files) == 1
    
    # Otwieram go i czytam, czy format się zgadza
    with open(files[0], "r") as f:
        lines = f.readlines()
        assert "Timestamp,Tag_ID,System,X,Y,Z,Quality" in lines[0] # To musi być w nagłówku
        assert "tag1,Pozyx,10.0,5.0,0,80%" in lines[1]             # A tu moje zmyślone dane


class DummyWebSocket:
    """
    Sztuczny klient WebSocket.
    Zastępuje nam przeglądarkę z frontendem. Zapisuje to, co serwer do niego wyśle
    do swojej wewnętrznej listy 'sent_messages', żebym mógł to potem sprawdzić.
    """
    def __init__(self):
        self.accepted = False
        self.sent_messages = []

    async def accept(self):
        self.accepted = True

    async def send_json(self, msg):
        self.sent_messages.append(msg)


@pytest.mark.asyncio
async def test_connection_manager_connect_and_broadcast():
    """
    Test asynchroniczny menedżera FastAPI (broadcasting do map HTML).
    Musimy mieć mark.asyncio, bo te metody to coroutiny (async/await).
    """
    manager = ConnectionManager()
    ws = DummyWebSocket()
    
    # Ktoś wszedł na stronę / mapę (symulacja)
    await manager.connect(ws)
    
    assert ws.accepted is True
    assert len(manager.active_connections) == 1
    
    # Silnik wyliczył nową pozycję z fuzji i robi broadcast do wszystkich otwartych kart
    test_msg = {"type": "update_positions", "tags": {"Tester1": {"x": 10, "y": 10}}}
    await manager.broadcast(test_msg)
    
    # Mój klient przeglądarki powinien mieć tę wiadomość u siebie na liście
    assert len(ws.sent_messages) == 1
    assert ws.sent_messages[0] == test_msg

    # Odświeżenie strony = klient się odpina
    manager.disconnect(ws)
    assert len(manager.active_connections) == 0
