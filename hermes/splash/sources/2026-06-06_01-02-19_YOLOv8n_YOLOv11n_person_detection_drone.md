**YOLOv11n outperforms YOLOv8n in drone-based person detection by utilizing fewer parameters and lower FLOPS while offering superior small-object recall.** On a **[MacBook M3 Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:2454872933540193881,headlineOfferDocid:12640058900463121258,productDocid:12640058900463121258,rds:PC_1448266432536557262%7CPROD_PC_1448266432536557262&q=product&sa=X&ved=2ahUKEwjloO_w6vGUAxWXtokEHUU7M9wQxa4PeggIAggACAgQAg)**, optimizing these models using **CoreML** unlocks maximum hardware acceleration via the Apple Neural Engine (ANE), surpassing raw PyTorch MPS speeds. 

---

📊 Performance Breakdown (

[MacBook M3 Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462544319888594,imageDocid:796392802389584553,gpcid:1448266432536557262,headlineOfferDocid:13374179803762723277,catalogid:5561753403804304800,productDocid:7285808824954105672,rds:PC_1448266432536557262%7CPROD_PC_1448266432536557262&q=product&sa=X&ved=2ahUKEwjloO_w6vGUAxWXtokEHUU7M9wQxa4PeggIAggACAwQAQ)

) 

To achieve real-time throughput for drone feeds, exporting the models from PyTorch to **CoreML (FP16)** is mandatory. 

| Metric / Framework `[13][14][15][16][17][18]` | YOLOv8n (CoreML FP16) | YOLOv11n (CoreML FP16) |
| --- | --- | --- |
| **Inference FPS** | ~90 – 110 FPS | ~100 – 120 FPS |
| **PyTorch (MPS) FPS** | ~45 – 60 FPS | ~40 – 50 FPS |
| **Parameters** | 3.2 Million | 2.6 Million (-22%) |
| **GFLOPs (@640x640)** | 8.7 | 6.5 |
| **Drone Edge Viability** | High | Very High (Better Accuracy/Watt) |

---

🛸 Drone Person Detection Viability `[7][8][9][10][11][12]`

Drone imagery features distinctive constraints like nadir (top-down) views, rapid camera motion, and tiny object pixel footprints. 

*

* **Small-Object Edge (Winner: YOLOv11n):** YOLOv8n relies on older C2f structural blocks. YOLOv11n introduces **C3k2 modules** and **C2PSA spatial attention layers**. This design extracts significantly richer spatial features, making YOLOv11n much more capable of tracking small pedestrians from high aerial altitudes. 

* **Latency & Consistency:** YOLOv11n lowers the post-processing bottleneck by generating cleaner, less redundant bounding boxes, leading to a tighter inference loop over video frames. 

*

---

💻 MacBook M3 Embedded Performance Architecture 

The base M3 system architecture behaves predictably under heavy machine learning workloads: 

*

* **Neural Engine vs. GPU:** PyTorch `device='mps'` processes frames via the M3 GPU. Converting to `.mlpackage` routes the model natively through the **Apple Neural Engine (ANE)**. This switch doubles frame rates while saving battery power. 

* **The CPU Bottleneck:** While the ANE can run inference in under 2ms, the end-to-end frame processing often suffers from image loading, resizing, and normalization delays (e.g., via PIL or OpenCV) on the CPU. To sustain >100 FPS, you must use hardware-accelerated texture mapping like **Vision Framework** or **CoreVideo**. `[1][2][3][4][5][6]`

* **Thermal Throttling:** MacBook Air M3 models lack fans. Sustained drone stream processing will cause thermal scaling after 5–10 minutes, reducing performance by 15–20%. MacBook Pro M3 models avoid this issue due to active cooling system fans. 

*

---

🚀 Optimization Quick Start 

To get the maximum benchmarked speed on your M3 Mac, export and run the model via the terminal:  bash

```
# 1. Export your model to CoreML FP16 format yolo export model=yolov11n.pt format=coreml half=True

# 2. Benchmark the exported model natively yolo benchmark model=yolov11n.mlpackage data=coco8.yaml imgsz=640 half=True

```

Use code with caution.

If you'd like, let me know: 

*

* Your specific **MacBook model** (Air or Pro?)

* The average **altitude or resolution** of your drone video feed

* Whether you need code for **live video pipeline acceleration** 

*

I can tailor a setup script exactly to your hardware requirements. 

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

[1] Real-time small object detection with YOLOv8n/8s and YOLOv11n/11s models in complex natural landscapes. Opens in new tab.  
https://www.researchgate.net/publication/393313265_Real-time_small_object_detection_with_YOLOv8n8s_and_YOLOv11n11s_models_in_complex_natural_landscapes

[2] Ultralytics YOLO11. Opens in new tab.  
https://docs.ultralytics.com/models/yolo11

[3] How to Train Ultralytics YOLO11 on the VisDrone Dataset. Opens in new tab.  
https://www.youtube.com/watch?v=9ymyH4H1fG4&vl=en

[4] YOLO11 vs YOLOv8: A Comprehensive Technical Comparison of Real-Time Vision Models | Ultralytics Docs. Opens in new tab.  
https://docs.ultralytics.com/compare/yolo11-vs-yolov8

[5] YOLOv8 vs YOLOv11: A Comparison - Python in Plain English. Opens in new tab.  
https://python.plainenglish.io/yolov8-vs-yolov11-a-comparison-94426b382367

[6] How to Export Ultralytics YOLO11 to CoreML for 2x Fast .... Opens in new tab.  
https://www.youtube.com/watch?v=hfSK3Mk5P0I&t=353

[7] Real-time small object detection with YOLOv8n/8s and YOLOv11n/11s models in complex natural landscapes. Opens in new tab.  
https://www.researchgate.net/publication/393313265_Real-time_small_object_detection_with_YOLOv8n8s_and_YOLOv11n11s_models_in_complex_natural_landscapes

[8] Ultralytics YOLO11. Opens in new tab.  
https://docs.ultralytics.com/models/yolo11

[9] How to Train Ultralytics YOLO11 on the VisDrone Dataset. Opens in new tab.  
https://www.youtube.com/watch?v=9ymyH4H1fG4&vl=en

[10] YOLO11 vs YOLOv8: A Comprehensive Technical Comparison of Real-Time Vision Models | Ultralytics Docs. Opens in new tab.  
https://docs.ultralytics.com/compare/yolo11-vs-yolov8

[11] YOLOv8 vs YOLOv11: A Comparison - Python in Plain English. Opens in new tab.  
https://python.plainenglish.io/yolov8-vs-yolov11-a-comparison-94426b382367

[12] How to Export Ultralytics YOLO11 to CoreML for 2x Fast .... Opens in new tab.  
https://www.youtube.com/watch?v=hfSK3Mk5P0I&t=353

[13] Real-time small object detection with YOLOv8n/8s and YOLOv11n/11s models in complex natural landscapes. Opens in new tab.  
https://www.researchgate.net/publication/393313265_Real-time_small_object_detection_with_YOLOv8n8s_and_YOLOv11n11s_models_in_complex_natural_landscapes

[14] Ultralytics YOLO11. Opens in new tab.  
https://docs.ultralytics.com/models/yolo11

[15] How to Train Ultralytics YOLO11 on the VisDrone Dataset. Opens in new tab.  
https://www.youtube.com/watch?v=9ymyH4H1fG4&vl=en

[16] YOLO11 vs YOLOv8: A Comprehensive Technical Comparison of Real-Time Vision Models | Ultralytics Docs. Opens in new tab.  
https://docs.ultralytics.com/compare/yolo11-vs-yolov8

[17] YOLOv8 vs YOLOv11: A Comparison - Python in Plain English. Opens in new tab.  
https://python.plainenglish.io/yolov8-vs-yolov11-a-comparison-94426b382367

[18] How to Export Ultralytics YOLO11 to CoreML for 2x Fast .... Opens in new tab.  
https://www.youtube.com/watch?v=hfSK3Mk5P0I&t=353

