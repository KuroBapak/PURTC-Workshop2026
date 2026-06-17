# Product Requirements Document (PRD)

**Project Name:** Edge AI Smart Lock System (Workshop Edition)  
**Document Status:** Final/Approved  
**Target Audience:** Workshop Participants / Engineering Students  
**Hardware Profile:** RTX 3050 Laptops (Master) + ESP32 Microcontroller (Slave)  

---

## 1. Executive Summary

This project is an Edge Computing-based Face Recognition Smart Lock system specifically designed for educational and workshop environments. Utilizing a **Master-Slave architecture**, heavy computations (AI Training & Live Inference via YOLOv8) are executed locally on a PC/Laptop utilizing a dedicated GPU (Master), while the physical actuation is strictly handled by an ESP32 microcontroller (Slave). 

The system highlights an end-to-end workflow, connecting a lightweight Vanilla Web interface (Frontend) and a FastAPI server (Backend) directly to real-world serial communication (Hardware), allowing participants to build, train, and deploy a working smart lock within minutes.

---

## 2. Objectives & Teachable Moments

* **Zero-Installation Deployment:** Ensure a frictionless experience for participants. The system must run without complex environment setups or "dependency hell." Participants simply extract a zipped folder and run a `.bat` executable — this automatically creates a **fresh Python virtual environment (`.venv`)**, installs all dependencies into it in complete isolation from the system Python, and launches the backend server. Participants then open the `index.html` file in their browser. No manual `pip install`, no conflicts with existing libraries.
* **The "Garbage In, Garbage Out" Lesson:** Intentionally **omitting auto-crop** for facial capture. This forces participants to capture their full webcam frame and educates them on the importance of a clean, isolated background when building an AI dataset for image classification. The model classifies the *entire frame*, so background noise directly degrades recognition accuracy — a powerful hands-on lesson.
* **Seamless Hardware Integration:** Demonstrate that web-based AI platforms can interact directly with the physical world (actuators) in real-time via low-latency serial communication.

---

## 3. System Architecture

| Component | Core Technology | Primary Responsibility |
| :--- | :--- | :--- |
| **Frontend** | Vanilla HTML, CSS, JS (Multi-Page with Animated Transitions) | UI/UX across 4 separate HTML pages, Dynamic multi-class CRUD, WebSocket-based burst capture, Live WebSocket Terminal, AI Threshold configuration, persistent ESP32 status indicator. |
| **Backend** | Python, FastAPI, Ultralytics YOLOv8, OpenCV (+ Haar Cascade Face Detection) | Image dataset routing, Real-time GPU model training (AutoBatch), Live Inference with face detection bounding box overlay, MJPEG stream, WebSocket log streaming, Serial bridge management with debounce. |
| **Hardware** | ESP32, PySerial, C++ (Arduino) | Receives string payloads via Serial (115200 baud), controls Servo motor, Buzzer, and LED indicators. |

### 3.1 Inference Pipeline (Dual-Model Architecture)

During Step 4 (Live Inference), the backend runs a **two-model pipeline** on each camera frame:

1. **Face Detection (OpenCV Haar Cascade)** — Locates faces in the frame and draws **bounding boxes** with labels around each detected face. This is purely for **visual feedback** — it shows participants where the system "sees" a face.
2. **Face Classification (Custom `best.pt` via YOLOv8-cls)** — Classifies the **full frame** (not the cropped face) to identify the person. This is where the "Garbage In, Garbage Out" lesson becomes tangible: if the training data had noisy backgrounds, the classifier struggles because it learned background features, not just facial features.

The bounding box and classification label are composited onto the frame before MJPEG streaming.

### 3.2 Project File Structure

```
Project Workshop2026/
├── frontend/
│   ├── index.html          → Step 1: Setup & Connection (Landing Page)
│   ├── collect.html        → Step 2: Data Collection
│   ├── train.html          → Step 3: AI Training
│   ├── inference.html      → Step 4: Live Inference & Testing
│   ├── css/
│   │   └── style.css       → Shared design system, animations, dark theme
│   └── js/
│       ├── common.js       → Shared utilities, page transitions, API helpers, ESP status
│       ├── setup.js        → Step 1 logic (COM port scan, serial connect)
│       ├── collect.js      → Step 2 logic (class CRUD, burst capture via WebSocket)
│       ├── train.js        → Step 3 logic (training trigger, WebSocket terminal)
│       └── inference.js    → Step 4 logic (MJPEG feed, threshold slider, result display)
├── backend/
│   ├── main.py             → FastAPI app entry point, CORS, router mounting
│   ├── routers/
│   │   ├── serial_router.py    → COM port scan, connect/disconnect, status endpoints
│   │   ├── dataset_router.py   → Class CRUD, image save, WebSocket burst receiver
│   │   ├── training_router.py  → Training trigger, WebSocket log streamer
│   │   └── inference_router.py → MJPEG video stream, threshold config, WebSocket results
│   ├── services/
│   │   ├── serial_manager.py   → PySerial singleton with state-change debounce + cooldown
│   │   ├── camera_manager.py   → OpenCV camera singleton (shared resource)
│   │   ├── training_service.py → YOLOv8 training orchestrator with stdout capture
│   │   └── inference_service.py→ YOLOv8 inference + Haar Cascade face detection + MJPEG
│   └── requirements.txt    → Python dependencies
├── hardware/
│   └── smart_lock.ino      → ESP32 Arduino sketch (Servo, Buzzer, LEDs)
├── dataset/                → Auto-created by backend at runtime
│   └── train/
│       ├── {ClassName_1}/  → Raw webcam frames (.jpg)
│       └── {ClassName_N}/
├── runs/                   → Auto-created by Ultralytics during training
│   └── classify/
│       └── train/
│           └── weights/
│               └── best.pt → Trained model weights
├── .venv/                  → Auto-created Python virtual environment (isolated)
├── start.bat               → One-click launcher (creates venv, installs deps, starts server)
└── Readme.md               → This document
```

---

## 4. User Interface (UI) Flow & Features

The interface uses a modern, premium dark-themed design with a **multi-page wizard architecture**. Each step is a separate HTML file. Navigation between steps uses **CSS-driven animated page transitions** (fade-out on the current page → fade-in on the next page via JavaScript-controlled navigation with a brief delay for the exit animation).

### Persistent UI Elements (All Pages)

* **Step Progress Bar:** A horizontal 4-step indicator at the top of each page showing the user's current position in the workflow, with active/completed/pending visual states and connecting lines.
* **ESP32 Status Indicator:** A persistent badge in the header area showing the hardware connection state:
    * 🟢 **Connected** — solid green dot with a subtle breathing/pulse animation + "ESP32 Connected" text.
    * 🔴 **Disconnected** — solid red dot with a slow blink animation + "ESP32 Disconnected" text.
    * ⚫ **Skipped** — gray dot + "Software Only" text (when hardware was skipped in Step 1).
    * The status is stored in `sessionStorage` and checked/rendered by `common.js` on every page load. A periodic heartbeat poll (`GET /api/serial/status`) keeps the indicator accurate.

### Step 1: Setup & Connection (`index.html`)

* **COM Port Scanner:** A dropdown list that dynamically populates with active COM ports detected by the FastAPI backend via `GET /api/serial/ports`.
* **Refresh Button:** Re-scans available COM ports on demand.
* **Action:** "Connect" button sends `POST /api/serial/connect` to initiate the serial bridge between the Python backend and the ESP32.
* **Connection Status Indicator:** Updates the persistent ESP32 badge to Connected (green pulse) on success.
* **Skip Option:** A clearly visible "Skip — No Hardware" link that allows participants without an ESP32 to proceed directly to Step 2. The system will operate in **software-only mode** (all UI features work, serial commands are silently ignored). The ESP32 badge shows "Software Only" in gray.
* **Navigation:** "Next →" button becomes active after connection is established (or after skipping).

### Step 2: Data Collection — Dynamic Multi-Class Registration (`collect.html`)

* **Live Viewport:** Real-time webcam feed rendered in the browser using the `getUserMedia` API and a `<video>` element.
* **Dynamic Class CRUD Panel:**
    * **Add Class:** A text input + "Add" button to register a new class name (e.g., "Moreno", "Excell", "Admin"). Duplicate names are rejected. Each new class creates a corresponding `dataset/train/{ClassName}/` folder on the backend via `POST /api/dataset/classes`.
    * **Class List:** A scrollable list/card view of all registered classes, each displaying:
        * The class name.
        * A live **image counter** (e.g., "47 images captured") updated in real-time during burst capture.
        * A **"Delete" button** (with confirmation prompt) that sends `DELETE /api/dataset/classes/{class_name}` to the backend. This **permanently deletes** the class folder and all its captured images from disk, then removes the class from the UI list.
    * **Active Class Selector:** Users click/select a class from the list to make it the active capture target. The active class is visually highlighted.
* **Capture Burst (Click & Hold):**
    * A large, prominent **"Hold to Capture"** button.
    * **On Press (mousedown / touchstart):** Opens a dedicated **WebSocket connection** (`ws://.../ws/capture/{class_name}`) and begins rapidly grabbing frames from the browser's webcam using the **ImageCapture API** (`grabFrame()`) for maximum speed. Frames are converted to JPEG `Blob`s and sent as **binary WebSocket messages** directly to the backend. Target capture rate: **~10 frames per second**.
    * **On Release (mouseup / touchend):** Stops frame capture and closes the WebSocket. The backend confirms the total number of images saved.
    * **Backend Processing:** Each received binary frame is decoded and saved as a sequentially numbered `.jpg` file (e.g., `001.jpg`, `002.jpg`, ...) inside `dataset/train/{ClassName}/`.
    * **Fallback:** If the ImageCapture API is unavailable, falls back to `<canvas>` `drawImage()` + `toBlob()` frame capture.
* **Navigation:** "← Back" and "Next → Start Training" buttons.

### Step 3: AI Training — Live Terminal Feed (`train.html`)

* **Pre-Training Summary:** A brief card showing the number of classes and total images collected before training begins.
* **Action:** "Start Training" button sends `POST /api/training/start` to trigger the Ultralytics YOLOv8 classification training pipeline on the backend.
* **Training Configuration (Auto-Optimized Defaults):**
    * Model: `yolov8n-cls.pt` (Nano classification — fastest for workshop)
    * Epochs: `50`
    * Image Size: `224×224`
    * Batch Size: `AutoBatch (-1)` — Ultralytics automatically determines the optimal batch size for the participant's GPU VRAM, ensuring maximum throughput on any GPU (RTX 3050, 3060, 4090, etc.) without OOM errors.
    * Patience: `10` (early stopping — training can finish faster if convergence is reached before 50 epochs)
    * Device: Auto-detected (CUDA GPU if available, CPU fallback)
    * Project: Points to the project root so `runs/` folder is created inside the project directory.
* **Live Terminal Window:**
    * A dedicated UI container styled like a dark CLI/terminal emulator with monospace font and green-on-black text.
    * Connects via **WebSocket** (`ws://.../ws/training/logs`) to stream the actual Python `stdout` training logs in real-time.
    * Participants will watch the Epoch progress, Loss metrics, Accuracy, and GPU utilization happen live.
    * Auto-scrolls to the latest output.
* **Completion State:**
    * The WebSocket sends a structured JSON message `{ "status": "completed", "model_path": "..." }` when training finishes.
    * A **success notification/animation** appears confirming that the `best.pt` custom weights file has been successfully generated.
    * The "Start Training" button is replaced with a **"Next → Test Your Model"** button.
* **Error Handling:** If training fails, an error message is displayed in the terminal with a "Retry" button.
* **Navigation:** "← Back" and "Next →" buttons.

### Step 4: Live Inference & Testing (`inference.html`)

* **Configurable Threshold:** A range slider (`0%` to `100%`, defaulting at **`70%`**) allowing participants to dynamically adjust the strictness of the AI confidence score. The current value is displayed numerically next to the slider. Changes are sent to the backend in real-time via `POST /api/inference/threshold`.
* **Live Processed Feed (Backend MJPEG Stream with Face Detection):**
    * The backend opens the webcam via **OpenCV**, and for each frame:
        1. Runs **OpenCV Haar Cascade face detection** to locate face regions → draws **green bounding boxes** around each detected face.
        2. Runs **YOLOv8 classification** on the **full frame** using the trained `best.pt` model → gets predicted class name and confidence score.
        3. Overlays the **class name + confidence %** as a label above the bounding box (or in a status bar if no face is detected).
        4. Encodes the composited frame as JPEG and streams it to the browser as an **MJPEG stream** via `GET /api/inference/feed`.
    * The browser displays this stream using a simple `<img src="/api/inference/feed">` tag — no complex JS video handling needed.
* **Real-Time Results via WebSocket:**
    * A parallel **WebSocket** (`ws://.../ws/inference/results`) pushes structured JSON results for each processed frame:
        * Granted: `{ "class_name": "Moreno", "confidence": 0.94, "status": "granted", "faces_detected": 1 }`
        * Denied: `{ "class_name": "unknown", "confidence": 0.32, "status": "denied", "faces_detected": 0 }`
    * The frontend JS uses these messages to drive the visual feedback UI.
* **Visual Feedback UI:**
    * **Access Granted:** If the AI detects a registered class **above** the threshold:
        * The UI viewport border pulses **Green** with a glow animation.
        * Displays a large welcome message: "✅ Welcome, {ClassName}".
        * Shows the confidence percentage.
    * **Access Denied:** If the AI confidence is **below** the threshold or the prediction is "unknown":
        * The UI viewport border pulses **Red** with a glow animation.
        * Displays an alert: "🚫 Access Denied / Unknown".
        * Shows the confidence percentage.
* **Serial Command Logic (Backend-Side with Debounce):**
    * The backend's inference loop evaluates each prediction result.
    * A **state-change debounce** mechanism ensures serial commands are only sent when the access state **transitions** (e.g., Denied → Granted or Granted → Denied).
    * A **5-second cooldown** is enforced after sending `"OPEN"` to match the ESP32's servo hold duration, preventing command spam.
    * If no hardware is connected (software-only mode from Step 1), serial commands are silently skipped.
* **Controls:** "Start Inference" / "Stop Inference" toggle button and "← Back to Training" link.

---

## 5. Backend Logic (FastAPI Blueprint)

### 5.1 API Endpoint Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/serial/ports` | Scan and return list of available COM ports. |
| `POST` | `/api/serial/connect` | Connect to a specified COM port at 115200 baud. |
| `POST` | `/api/serial/disconnect` | Disconnect the active serial connection. |
| `GET` | `/api/serial/status` | Returns current connection state (`connected`/`disconnected`/`skipped`). |
| `GET` | `/api/dataset/classes` | List all registered classes with image counts. |
| `POST` | `/api/dataset/classes` | Create a new class (creates folder on disk). |
| `DELETE` | `/api/dataset/classes/{name}` | Delete a class and all its images from disk. |
| `WS` | `/ws/capture/{class_name}` | WebSocket for burst image capture (binary frames). |
| `POST` | `/api/training/start` | Trigger YOLOv8 classification training. |
| `WS` | `/ws/training/logs` | WebSocket for live training log streaming. |
| `POST` | `/api/inference/start` | Start the inference engine and MJPEG stream. |
| `POST` | `/api/inference/stop` | Stop the inference engine and release camera. |
| `POST` | `/api/inference/threshold` | Update the confidence threshold in real-time. |
| `GET` | `/api/inference/feed` | MJPEG video stream of annotated inference frames. |
| `WS` | `/ws/inference/results` | WebSocket for real-time inference result JSON. |

### 5.2 Core Services

* **Serial Manager (Singleton):** Wraps `pyserial`. Manages a single open COM port connection. Implements a **state-change debounce** — only sends `"OPEN"` or `"CLOSE"` when the access state transitions. Enforces a **5-second cooldown** after `"OPEN"` to match the ESP32 servo hold time. Exposes a `/api/serial/status` endpoint for the persistent ESP32 badge. In software-only mode (no port connected), all `send()` calls are no-ops.

* **Camera Manager (Singleton):** Wraps `cv2.VideoCapture`. Ensures only one process accesses the camera at a time. Used by the inference service (Step 4) for backend-side camera access. **Not used in Step 2** (browser-side camera). Provides thread-safe `read()` access.

* **Training Service:** Executes `YOLO('yolov8n-cls.pt').train(data='dataset', epochs=50, imgsz=224, batch=-1, patience=10, device='auto', project='runs')`. Uses `batch=-1` for **AutoBatch** — Ultralytics automatically measures GPU VRAM and selects the largest batch size that fits, ensuring optimal performance on any GPU. Captures `stdout` using a custom stream redirector and broadcasts lines to all connected WebSocket clients. Emits a structured completion/error JSON message when training finishes. Runs training in a **background thread** so the FastAPI event loop is not blocked.

* **Inference Service:** Loads the latest `best.pt` model and OpenCV Haar Cascade face detector (`haarcascade_frontalface_default.xml`). Opens the camera via Camera Manager. Runs a continuous frame-processing loop:
    1. Capture frame → run Haar Cascade face detection → draw bounding boxes.
    2. Run YOLOv8 classification on the **full frame** → get class name + confidence.
    3. Overlay label text above the bounding box.
    4. Determine `granted` (confidence > threshold & known class) vs `denied`.
    5. Pass result to Serial Manager for hardware actuation (with debounce).
    6. Encode composited frame as JPEG → yield as MJPEG multipart boundary.
    7. Store latest result dict for WebSocket broadcasting.

### 5.3 Dataset Manager

* Receives binary JPEG frames via WebSocket from the JS frontend during burst capture.
* Decodes and saves them as sequentially numbered `.jpg` files inside the dynamically created `dataset/train/{Class_Name}/` directories.
* On class deletion (`DELETE`), recursively removes the entire `dataset/train/{Class_Name}/` directory using `shutil.rmtree()`.

---

## 6. Hardware Actuation Protocol

Communication between the Master PC and the ESP32 uses a standard Baud Rate of **115200**. The microcontroller runs a lightweight C++ loop waiting for strict string instructions.

### Scenario A: Access Granted
* **Trigger Condition:** Face prediction matches ANY registered class **AND** the confidence score is strictly `>` the UI Threshold (default 70%).
* **Python Payload:** `"OPEN"`
* **Debounce Rule:** Only sent on state transition (Denied → Granted). A 5-second cooldown is enforced after each `"OPEN"` command.
* **ESP32 Execution:**
    1.  Turns **ON** the Green LED.
    2.  Turns **OFF** the Red LED.
    3.  Triggers the Buzzer to emit 2 short, rapid beeps.
    4.  Rotates the Servo to 90 degrees (Unlocking mechanism).
    5.  Holds state for 5 seconds.
    6.  Automatically rotates the Servo back to 0 degrees (Locking mechanism).

### Scenario B: Access Denied
* **Trigger Condition:** Face prediction is evaluated as "Unknown" **OR** the confidence score is `≤` the UI Threshold.
* **Python Payload:** `"CLOSE"`
* **Debounce Rule:** Only sent on state transition (Granted → Denied).
* **ESP32 Execution:**
    1.  Turns **ON** the Red LED.
    2.  Turns **OFF** the Green LED.
    3.  Triggers the Buzzer to emit 1 long, continuous beep.
    4.  Maintains the Servo firmly at 0 degrees (Locked state).

---

## 7. Technical Specifications

| Parameter | Value |
| :--- | :--- |
| **YOLOv8 Model** | `yolov8n-cls.pt` (Nano Classification) |
| **Face Detection** | OpenCV Haar Cascade (`haarcascade_frontalface_default.xml`) |
| **Training Epochs** | 50 (with early stopping patience=10) |
| **Image Size** | 224×224 px |
| **Batch Size** | AutoBatch (`-1`) — auto-optimized per GPU VRAM |
| **Device** | Auto (CUDA GPU preferred, CPU fallback) |
| **Trained Weights** | `runs/classify/train/weights/best.pt` (inside project root) |
| **Default Confidence Threshold** | 70% |
| **Burst Capture Rate** | ~10 FPS via ImageCapture API over WebSocket |
| **MJPEG Stream** | OpenCV → Haar Cascade → YOLOv8-cls → JPEG encode → multipart stream |
| **Serial Baud Rate** | 115200 |
| **Serial Debounce** | State-change only + 5s cooldown after OPEN |
| **Frontend Framework** | Vanilla HTML/CSS/JS (No build tools) |
| **Backend Framework** | FastAPI + Uvicorn |
| **Python Dependencies** | fastapi, uvicorn, ultralytics, opencv-python, pyserial, aiofiles |

---

## 8. Deployment & Launch

### Prerequisites
* Python 3.10+ installed and available in system PATH.
* NVIDIA GPU with CUDA drivers installed (for GPU-accelerated training).
* Google Chrome or Microsoft Edge browser (for ImageCapture API support).

### Quick Start
1. Extract the project `.zip` folder to any location.
2. Double-click `start.bat` — this automatically creates an isolated Python virtual environment, installs all dependencies, and launches the backend server.
3. Open `frontend/index.html` in your browser.
4. Follow the 4-step wizard to build and deploy your smart lock!

### start.bat Behavior
```
1. Checks for Python 3.10+ in PATH.
2. Creates a fresh .venv/ virtual environment (if not already present).
3. Activates the virtual environment.
4. Installs all packages from requirements.txt into .venv/ (pip install -r).
5. Launches the FastAPI server via Uvicorn on http://localhost:8000.
6. Keeps the terminal open so participants can see backend logs.
```

> **Why a virtual environment?** Workshop participant laptops may have pre-existing Python libraries that conflict with our dependencies. A `.venv` ensures a completely clean, isolated Python environment every time — zero dependency hell, guaranteed reproducibility.