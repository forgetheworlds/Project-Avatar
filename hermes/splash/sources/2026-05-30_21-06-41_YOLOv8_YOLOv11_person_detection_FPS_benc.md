On an Apple MacBook with a base **M3 chip (10-core GPU)** using the **Metal Performance Shaders (MPS)** backend, **YOLOv11** outperforms **YOLOv8** in processing efficiency. While both models achieve smooth real-time frame rates for person detection at standard 640x640 resolutions, YOLOv11 delivers faster inference speeds and higher precision with fewer parameters. 

The benchmark performance breakdown across PyTorch MPS (Metal GPU) and CoreML optimizations is detailed below. 

Expected FPS Performance Summary (640x640 Resolution) 

| Model Variant `[1][2][3][4][5]` | YOLOv8 (PyTorch MPS) | YOLOv11 (PyTorch MPS) | CoreML Optimized Export |
| --- | --- | --- | --- |
| **Nano (n)** | ~60 – 75 FPS | **~75 – 95 FPS** | **~100+ FPS** |
| **Small (s)** | ~40 – 50 FPS | **~50 – 65 FPS** | ~70 – 85 FPS |
| **Medium (m)** | ~20 – 28 FPS | **~25 – 35 FPS** | ~40 – 48 FPS |
| **Large (l)** | ~12 – 15 FPS | **~15 – 20 FPS** | ~22 – 28 FPS |

---

Key Performance Drivers on M3 Metal GPU 

* **Architectural Upgrades**: YOLOv11 replaces YOLOv8's `C2f` modules with `C3k2` blocks. This adjustment reduces parameter counts while utilizing a `C2PSA` spatial attention mechanism. The design minimizes redundant processing and maximizes the M3's unified memory bandwidth. 
* **Metal vs. CoreML**: Running raw PyTorch code via `device='mps'` relies heavily on your GPU shaders. Exporting models to **CoreML format** using `model.export(format='coreml')` allows the system to engage the **Apple Neural Engine (ANE)** alongside the Metal GPU. This configuration shifts the processing load off the GPU cores, boosting **YOLOv11 Nano to over 100 FPS**. 
* **Thermal Behavior (Air vs. Pro)**: The fan-cooled 14-inch MacBook Pro sustains peak performance over long video streams. The fanless MacBook Air will throttle performance by approximately 15% to 25% after 5–10 minutes of continuous high-load inference. 
*

Optimization Best Practices for macOS 

To maximize frame rates for person detection on an M3 Mac, execute the following script setup to utilize native FP16 half-precision and AMP (Automatic Mixed Precision):  python

``` from ultralytics import YOLO

# Load the optimized YOLOv11 model model = YOLO("yolo11n.pt")

# Stream video using the Metal Performance Shaders (MPS) backend with half-precision results = model.predict( source="live_camera_feed.mp4", device="mps", half=True,       # Enforces FP16 reduction for Apple Silicon classes=[0]      # Class 0 isolates person detection to reduce post-processing overhead
)

```

Use code with caution.

Are you looking to deploy this for **real-time webcam streaming**, or are you processing **saved video files**? I can provide the exact code needed to implement a high-efficiency frame-skipping pipeline. 

Copy

# Share public link

This public link is valid for 7 days and shares a thread, including any personal information you added. This link or copies made by others cannot be deleted. If you share with third parties, their policies apply.

Can’t copy the link right now. Try again later.

Facebook

Gmail

X

Reddit

WhatsApp

Good response

Bad response

Saved time

Clear

Helpful

Comprehensive

Other

Incorrect

Inappropriate

Not working

Unhelpful

Other

A copy of this chat, including the images and video, will be included with your feedback

A copy of this chat will be included with your feedback

Your feedback will include a copy of this chat and the image from your search

Your feedback will include a copy of this chat, any links you shared, and the image from your search.

Thanks for letting us know

Google may use account and system data to understand your feedback and improve our services, subject to our [Privacy Policy](https://policies.google.com/privacy) and [Terms of Service](https://policies.google.com/terms). For legal issues, [make a legal removal request](https://support.google.com/legal/answer/3110420).

---

## Sources:

[1] YOLO11 vs YOLOv8: A Comprehensive Technical Comparison of .... Opens in new tab.  
https://docs.ultralytics.com/compare/yolo11-vs-yolov8

[2] Is YOLOv26 Actually Better? - Medium. Opens in new tab.  
https://medium.com/@mhuzaifadev/is-yolov26-actually-better-40527d2b95d7

[3] An Overview of YOLO26, YOLO11, YOLOv8, and YOLOv5 Object .... Opens in new tab.  
https://arxiv.org/html/2510.09653v2

[4] Choosing the right Ultralytics YOLO model. Opens in new tab.  
https://www.ultralytics.com/blog/ultralytics-yolo26-vs-yolo11-vs-yolov8-which-one-should-you-use

[5] Benchmarking YOLOv8–YOLOv12 for Real-Time Object Detection .... Opens in new tab.  
https://www.preprints.org/manuscript/202605.0936

