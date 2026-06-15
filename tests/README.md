
# 🧪 RTLS Middleware - Automated Test Suite by using PyTest

This directory contains a complete set of unit and integration tests for the multi-protocol RTLS data fusion engine (Pozyx MQTT & Ubisense UDP). The tests are designed to verify the math behind the algorithms, handle network errors, and test async communication without needing any physical hardware.

## 🛠️ Test Structure and Scope

The test suite (`test_rtls.py`) covers 4 main layers of the middleware application:

1. **Pozyx Parser (MQTT / JSON):** Verifies decoding JSON text objects and applying dynamic spatial offsets (near zone $< 3m$ vs. far zone $\ge 3m$).
2. **Ubisense Parser (UDP / Binary):** Tests low-level unpacking of raw byte streams (`struct.unpack`) and checks the system's resilience against corrupted or incomplete network packets.
3. **Data Recorder (I/O):** Tests the continuous logging module that saves location frames to `.csv` and `.txt` files.
4. **Connection Manager (FastAPI / WebSockets):** An async integration test that checks the broadcasting mechanism used to send calculated positions to connected clients (HTML maps).

---

## 🚀 Advanced Engineering Techniques

To maintain high architectural standards, the following development techniques were used in this project:

### 1. Record/Replay Approach (Production Data)
Instead of making up synthetic test data, the parsers are verified using **authentic production data dumps** recorded by the system in `ML_Record` mode:
* **Pozyx:** The test uses an actual JSON log package containing parameters like `position_score`, `blinkIndex`, and the `anchorData` array.
* **Ubisense:** The test uses a raw hexadecimal dump of a UDP frame (`e298026b...`), simulating a real physical network packet.

### 2. File System Isolation (`tmp_path`)
When testing the `DataRecorder` class, the built-in `tmp_path` fixture is used. Before running the test, PyTest creates a unique, isolated temporary directory where the recorder saves trial `.csv` files. After the test is finished, the directory is automatically destroyed. This prevents cluttering the actual project workspace (`RECORDS/`).

### 3. Async Testing and Stubbing (`pytest-asyncio`)
Since the FastAPI server runs on an Event Loop, network connection tests are marked with the `@pytest.mark.asyncio` decorator. To test WebSocket broadcasting without launching a web browser, a **Stub** object (`DummyWebSocket`) was implemented to intercept outgoing JSON frames into local memory for assertions.

### 4. DRY Optimization via Parameterization
The business logic for switching Pozyx compensation zones is tested using `@pytest.mark.parametrize`. This allows running the same test multiple times for different sets of input data and expected results, eliminating duplicate code.

---

## ⚙️ How to Run Locally

You should run the tests inside a dedicated virtual environment to isolate project dependencies.

```bash
# 1. Go to the main project directory
cd Magisterka_Dziala_Do_PyTest

# 2. Activate the virtual environment (.venv)
.\.venv\Scripts\Activate

# 3. Run tests in verbose mode
pytest -v

```

### Expected Test Output:

```text
============================= test session starts ==============================
platform win32 -- Python 3.13.14, pytest-9.1.0, pluggy-1.6.0
plugins: anyio-4.13.0, asyncio-1.4.0
collected 8 items                                                                                                      

test_rtls.py::test_parse_pozyx_real_data PASSED                                 [ 12%]
test_rtls.py::test_parse_pozyx_payload_invalid_data PASSED                      [ 25%]
test_rtls.py::test_pozyx_offsets_logic[2000-2.94] PASSED                        [ 37%]
test_rtls.py::test_pozyx_offsets_logic[4000-4.0] PASSED                         [ 50%]
test_rtls.py::test_parse_ubisense_real_data PASSED                              [ 62%]
test_rtls.py::test_parse_ubisense_invalid_status PASSED                         [ 75%]
test_rtls.py::test_data_recorder_start_and_write PASSED                         [ 87%]
test_rtls.py::test_connection_manager_connect_and_broadcast PASSED              [100%]

============================== 8 passed in 0.28s ==============================

```

---

## 🧠 Edge Cases Analysis

The test code takes into account the hardware specifics of both RTLS systems:

* **Float truncation in Ubisense:** The signal quality verification handles the fact that the `int()` function in Python cuts off the fractional part. The test accounts for the inaccuracy of float representation (32-bit IEEE 754 standard) from the raw UDP frame, allowing an acceptable bit-level margin of error for `raw_quality`.
* **Graceful Failure (Packet errors):** The `invalid_data` and `broken_packet` tests check if corrupted network streams (e.g., a cut-off UDP packet that is 8 bytes long instead of 40) are safely caught by `except Exception` blocks in the engine, ensuring the server doesn't crash.

```


```bash
git add tests/
git commit -m "test: add comprehensive pytest suite with record/replay data"
git push origin main

```
