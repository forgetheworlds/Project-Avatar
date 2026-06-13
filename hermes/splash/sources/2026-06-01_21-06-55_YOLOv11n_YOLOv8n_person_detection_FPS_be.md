**YOLOv11n delivers higher accuracy (39.5% mAP) than YOLOv8n (37.3% mAP) with roughly 15% fewer parameters, though raw native PyTorch inference speed remains highly comparable between both versions on Apple Silicon.** When running person detection workloads on a **[MacBook M3 (Base/Pro/Max) Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:8498403889690231088,headlineOfferDocid:11723625597104317814,productDocid:11723625597104317814,rds:PC_1448266432536557262%7CPROD_PC_1448266432536557262&q=product&sa=X&ved=2ahUKEwiK_cjmrueUAxWjN4YAHSR_PJIQxa4PeggIAggACAUQAg)**, the performance profile splits drastically between standard Python execution and hardware-optimized frameworks like CoreML. 

Performance & Benchmark Comparison 

The following table reflects standardized real-world benchmarks for person detection at a `640x640` input resolution on an

[Apple M3 Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:2454872933540193881,headlineOfferDocid:12640058900463121258,productDocid:12640058900463121258,rds:PC_1448266432536557262%7CPROD_PC_1448266432536557262&q=product&sa=X&ved=2ahUKEwiK_cjmrueUAxWjN4YAHSR_PJIQxa4PeggIAggACAoQAg) chip using the [Ultralytics Python API](https://docs.ultralytics.com/compare/yolov8-vs-yolo11): `[7][8][9][10][11][12]`

| Metric / Variant `[1][2][3][4][5][6]` | YOLOv8n (PyTorch) | YOLOv11n (PyTorch) | YOLOv8n (CoreML FP16) | YOLOv11n (CoreML FP16) |
| --- | --- | --- | --- | --- |
| **Model Size (.pt / .mlpackage)** | ~6.2 MB | **~5.4 MB** | ~3.1 MB | **~2.8 MB** |
| **Parameters** | 3.2 Million | **2.6 Million** | 3.2 Million | **2.6 Million** |
| **COCO mAP50-95** | 37.3% | **39.5%** | 37.1% | **39.3%** |
| **CPU Inference (Latency / FPS)** | ~55ms (18 FPS) | **~48ms (21 FPS)** | ~25ms (40 FPS) | **~20ms (50 FPS)** |
| **GPU / MPS Inference (FPS)** | **55 - 65 FPS** | 50 - 60 FPS | N/A (CoreML uses ANE) | N/A (CoreML uses ANE) |
| **Apple Neural Engine (ANE) FPS** | N/A | N/A | ~90 - 110 FPS | **~110 - 130 FPS** |

*Note: YOLOv11n introduces architectural optimizations like the `C3k2` block and `C2PSA` spatial attention. This gives it a significant edge over YOLOv8n when detecting small, crowded, or heavily occluded individuals, despite using a smaller parameter footprint.* 

---

CPU vs. GPU (MPS) Performance Profile 

* **CPU Core Architecture:** The M3 CPU cores handle unoptimized PyTorch models reliably. YOLOv11n benefits from a leaner backbone, yielding up to a 10-15% latency reduction over YOLOv8n on raw CPU cores. 
* **GPU Backend (MPS):** Utilizing Apple's `device='mps'` (Metal Performance Shaders) maps workloads directly to the M3 GPU. This moves processing from ~15-20 FPS on standard Python CPU loops straight into smooth, real-time **50+ FPS territory**. 

---

Apple Silicon Optimization Tips 

To unlock maximum processing speed for a real-time deployment setup on a

MacBook M3

, apply these targeted optimization steps: 

1. **Leverage CoreML and the Apple Neural Engine (ANE)**  
Do not deploy native `.pt` files for production. Export the model to CoreML format using `half=True` to enforce FP16 precision. This shifts the compute load entirely away from the CPU/GPU and redirects it to the highly efficient Apple Neural Engine (ANE), driving the system past **100+ FPS**.
  python
  

``` from ultralytics import YOLO model = YOLO("yolo11n.pt") model.export(format="coreml", nms=True, half=True) # Enables FP16 & native ANE pipeline

```
  Use code with caution. 

2. **Utilize Persistent MPS Caching**  
If you must use the PyTorch Metal backend (`device='mps'`), add the following environment variable flags at the top of your Python execution script. This minimizes overhead by forcing graph reuse and disabling fallback memory thrashing:
  python
  

``` import os os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
# Prevents expensive re-allocations on changing frame shapes

```
  Use code with caution. 

3. **Optimize the Image Pre-processing Loop**  
The standard `cv2.imread()` process running inside a single-threaded loop will bottleneck your pipeline long before the model finishes inference. Feed video frames as batches or run image resizing asynchronously on separate CPU threads using `pinned memory` concepts to keep the M3 GPU/ANE fully fed. 
4. **Enforce Lower Input Resolutions**  
If raw processing velocity is more critical to your application than pinpoint precision, drop your input scale argument from `imgsz=640` down to `imgsz=416` or `imgsz=320`. The processing frame rate will scale exponentially higher without destroying the accuracy of standard-sized person detection tasks. 

Would you like help with a **complete Python script** to benchmark these models locally, or do you need assistance configuring the **CoreML model export parameters** for a custom application? 

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

[1] YOLOv8 vs YOLO11 - Ultralytics Docs. Opens in new tab.  
https://docs.ultralytics.com/compare/yolov8-vs-yolo11

[2] YOLO11 vs YOLOv8 - Ultralytics Docs. Opens in new tab.  
https://docs.ultralytics.com/compare/yolo11-vs-yolov8

[3] An Overview of YOLO26, YOLO11, YOLOv8, and YOLOv5 Object .... Opens in new tab.  
https://arxiv.org/html/2510.09653v2

[4] How to Benchmark Ultralytics YOLO26 Models. Opens in new tab.  
https://www.youtube.com/watch?v=UF7pYdLSMng

[5] Running YOLOv8 on Apple Silicon with MPS Backend - Dev Genius. Opens in new tab.  
https://blog.devgenius.io/running-yolov8-on-apple-silicon-with-mps-backend-a-simplified-guide-84b1d382f79c

[6] Clarification regarding mAP discrepancies between official .... Opens in new tab.  
https://github.com/orgs/ultralytics/discussions/24393

[7] YOLOv8 vs YOLO11 - Ultralytics Docs. Opens in new tab.  
https://docs.ultralytics.com/compare/yolov8-vs-yolo11

[8] YOLO11 vs YOLOv8 - Ultralytics Docs. Opens in new tab.  
https://docs.ultralytics.com/compare/yolo11-vs-yolov8

[9] An Overview of YOLO26, YOLO11, YOLOv8, and YOLOv5 Object .... Opens in new tab.  
https://arxiv.org/html/2510.09653v2

[10] How to Benchmark Ultralytics YOLO26 Models. Opens in new tab.  
https://www.youtube.com/watch?v=UF7pYdLSMng

[11] Running YOLOv8 on Apple Silicon with MPS Backend - Dev Genius. Opens in new tab.  
https://blog.devgenius.io/running-yolov8-on-apple-silicon-with-mps-backend-a-simplified-guide-84b1d382f79c

[12] Clarification regarding mAP discrepancies between official .... Opens in new tab.  
https://github.com/orgs/ultralytics/discussions/24393

