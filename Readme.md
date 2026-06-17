# 🔐 Edge AI Smart Lock System — Workshop Edition

Welcome to the **Edge AI Smart Lock System**, a complete, end-to-end Computer Vision workshop project! 

This project demonstrates how to build a production-grade facial recognition smart lock entirely from scratch. You will train your own custom AI model directly on your local GPU (supporting both NVIDIA CUDA and AMD DirectML), and watch it interact with physical hardware via a real-time web interface.

---

## ✨ Features

- **Zero-Friction Setup:** A simple double-click on `start.bat` builds an isolated Python virtual environment and installs all dependencies instantly.
- **Hardware Agnostic AI:** Fully supports **NVIDIA (CUDA)**, **AMD / Ryzen AI (ROCm & DirectML)**, and standard CPU fallback.
- **Smart Face Cropping:** Uses OpenCV's Haar Cascade to isolate and tightly crop faces *before* they hit the neural network, ensuring incredible accuracy.
- **Multi-Face Inference:** Tracks and evaluates multiple faces in the camera simultaneously, each with independent bounding boxes and predictions.
- **Real-Time Hardware Simulation:** Features a 3-stage dynamic unlock sequence (`Locked` ➔ `Verifying... Hold Still` ➔ `Unlocked`) mimicking the behavior of commercial security systems.
- **Master-Slave Architecture:** The heavy AI lifting is done on your PC (Master), while the physical actuation commands are streamed to an ESP32 microcontroller (Slave) over a serial bridge.

---

## 🚀 Quick Start Guide

### Step 0: Initial Setup
1. Extract the project folder to your local drive.
2. Double-click the `start.bat` file.
3. When prompted, select your hardware profile:
   - **Press 1** for NVIDIA GPUs (Default).
   - **Press 2** for AMD GPUs or Ryzen AI iGPUs.
4. The script will automatically build your isolated `.venv`, install the exact pinned libraries, and launch the FastAPI backend.
5. Open `frontend/index.html` in your web browser.

### Step 1: Hardware Connection
- Upon opening the web app, you will be prompted to select a COM port.
- If you have an **ESP32 Smart Lock Module** plugged in via USB, select its COM port and click **Connect**.
- If you don't have hardware, simply click **Skip — No Hardware** to run in software-only mode.

### Step 2: Data Collection
In this step, you will build the dataset the AI will learn from.
1. Enter your name (e.g., "Admin", "John") into the **Add Class** field and hit **Add**.
2. Select your newly created class from the list.
3. Look at your webcam, then **Click and Hold** the large "Hold to Capture" button. The system will rapidly burst-capture photos of your face. Collect around 50–60 images with different angles and lighting.
4. (Optional) The backend comes pre-loaded with an `unknown` class dataset containing random faces to teach the AI what *unauthorized* people look like!

### Step 3: AI Training
1. Click **Start Training**.
2. The Ultralytics YOLOv8 engine will initialize and automatically calculate the optimal batch size for your GPU.
3. Watch the live terminal feed as the neural network trains for up to 50 Epochs.
4. Once training finishes, the model weights (`best.pt`) are automatically loaded into the inference engine.

### Step 4: Live Inference & Testing
1. Click **Start Inference** to activate the live testing engine.
2. Step in front of the camera. The Haar Cascade detector will instantly locate your face and feed it to your freshly trained YOLOv8 model.
3. **The Verification Sequence:**
   - **Access Denied:** If an unknown person is detected, the border pulses Red and the hardware remains locked.
   - **Verifying:** If you are recognized, the border pulses Orange. A progress bar appears requiring you to hold still and maintain eye contact for ~1.5 seconds.
   - **Access Granted:** Once verified, the border pulses Green, the UI displays `UNLOCKED`, and an `OPEN` command is fired to the ESP32 to trigger the servo motor!
4. You can adjust the **Confidence Threshold** slider in real-time to make the security system more or less strict.

---

## 💻 Tech Stack

- **Frontend:** Vanilla HTML, CSS, JS (No frameworks, ultra-lightweight)
- **Backend:** Python 3.12, FastAPI, Uvicorn, WebSockets
- **AI & Vision:** Ultralytics YOLOv8-cls, PyTorch, OpenCV
- **Hardware:** ESP32 (C++ / Arduino IDE), PySerial

## 🛠 Troubleshooting

- **"Camera in Use" Error:** Ensure no other applications (Zoom, Discord, OBS) are currently using your webcam.
- **Port Access Denied:** If the ESP32 fails to connect, make sure the Arduino IDE Serial Monitor is closed.
- **No Face Detected:** Ensure your room is well-lit. The Haar Cascade requires decent contrast to find eyes and facial structures.

Enjoy building your intelligent smart lock!
