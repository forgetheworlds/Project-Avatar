Real-Time Detection & Tracking Performance 

On a standard **[Apple MacBook Pro (M3 Base Chip) Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:16530990147939341246,headlineOfferDocid:3240566647647504081,productDocid:3240566647647504081,rds:PC_1448266432536557262%7CPROD_PC_1448266432536557262&q=product&sa=X&ved=2ahUKEwiLz96LpeyUAxXBm4kEHU2XN38Qxa4PeggIAggACAUQAg)** with **16GB/24GB Unified Memory**, native person detection using CoreML achieves exceptional real-time speeds when utilizing the **Apple Neural Engine (ANE)**. However, tracking performance is heavily dependent on the generational architecture of the model and the choice of post-processing pipeline. 

The baseline performance metrics for a 640x640 resolution input stream break down as follows: 

```
[Camera Stream] ──> [CoreML Inference (ANE)] ──> [Post-Processing (CPU: NMS / Tracker)]

```

| Metric / Pipeline Component `[19][20][21][22][23][24]` | YOLOv8n (CoreML) | YOLO11n (CoreML) | YOLO26n (CoreML) |
| --- | --- | --- | --- |
| **Pure Inference Latency** | ~11–13 ms | ~14–15 ms | **~9–11 ms** |
| **Pure Inference FPS** | ~75–90 FPS | ~70–100+ FPS | **~100–110 FPS** |
| **Post-Processing Bottleneck** | High (CPU NMS) | High (CPU NMS) | **None (NMS-Free)** |
| **Tracking Pipeline (ByteTrack)** | ~45–55 FPS | ~50–60 FPS | **~75–85 FPS** |
| **Tracking Pipeline (Kalman Only)** | ~65–75 FPS | ~65–75 FPS | **~90–95 FPS** |

---

Neural Engine Acceleration & Architecture 

CoreML Layer Execution 

When compiling Ultralytics models (`.pt`) via the [Ultralytics CoreML Export Integration](https://github.com/ultralytics/yolo-ios-app), the M3 Neural Engine executes 95%+ of the model graph natively. 

* Convolutions, SiLU activation layers, and C3k2/C2f/C2PSA blocks map perfectly to the ANE's matrix engines.
* The unified memory architecture eliminates GPU-to-CPU memory copying overhead, resulting in a **13× speedup** over unoptimized PyTorch MPS (Metal Performance Shaders) execution paths. 

The NMS Bottleneck & The YOLO26 Paradigm Shift `[13][14][15][16][17][18]`

Prior to recent developments, running YOLOv8n or YOLO11n on Apple Silicon hit a harsh ceiling due to **Non-Maximum Suppression (NMS)**. 

* While the ANE processes the image in under 15ms, standard exports force the bounding box sorting and NMS filtering to run on the Mac's CPU. This introduces a massive latency spike when crowds of people are detected. 
* **YOLO26n** completely redesigns the prediction head by removing NMS entirely (relying on end-to-end bipartite matching). This produces a **completely static graph** with zero dynamic post-processing, allowing the M3 chip to sustain its maximum frame rate regardless of the number of people in the frame. 

---

Tracking Algorithm Performance Overhead 

Integrating multi-object tracking (MOT) layers directly impacts the total pipeline frame rate because tracking algorithms run strictly sequentially on the **M3 CPU Performance Cores**. 

1. ByteTrack Pipeline (High Density / High Accuracy) `[7][8][9][10][11][12]`

* **How it works:** [ByteTrack](https://www.taskmonk.ai/blogs/video-object-tracking-algorithms-guide) matches nearly every detection box, even low-confidence detections, to preserve tracking identities during occlusions (e.g., when a person walks behind a pillar). 
* **M3 Impact:** This requires solving a continuous linear assignment problem via the Hungarian Algorithm alongside a bounding box Kalman filter. 
* **Performance:** It reduces pure inference speed by **30–40%**. When paired with YOLO11n, expect **50–60 FPS**. When paired with the NMS-free YOLO26n, it holds a steady **~80 FPS**. 

2. Pure Kalman Filter / DeepSORT variants (Low Overhead) 

* **How it works:** A basic IoU-tracker backed strictly by a linear Kalman filter ignores low-confidence detections and skips complex feature embedding matches. 
* **M3 Impact:** Extremely lightweight on CPU compute. 
* **Performance:** It incurs less than a **10% frame rate penalty**, letting YOLO26n tracking run near the **~95 FPS** threshold. However, tracking identities will frequently break or switch in crowded areas. 

---

Thermal Throttling & Sustained Workloads 

The baseline

[M3 MacBook Pro Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:3885587555398362089,headlineOfferDocid:11114973588168624877,productDocid:11114973588168624877,rds:PC_1448266432536557262%7CPROD_PC_1448266432536557262&q=product&sa=X&ved=2ahUKEwiLz96LpeyUAxXBm4kEHU2XN38Qxa4PeggIAggACDgQAg) utilizes an active single-fan thermal solution. 

* **Initial Burst (0-3 minutes):** The system easily delivers peak performance (>90 FPS pure inference).
* **Sustained Load (10+ minutes):** Continuous execution of both the ANE (at 100% capacity) and CPU performance cores (handling trackers) generates significant heat. The macOS kernel will throttle the ANE clock speeds slightly to manage thermals.
* **Sustained Performance:** Frame rates typically level off and stabilize at **15–20% below peak speeds** to prevent overheating. 

---

Optimization Workflow 

To maximize tracking performance on an M3 Mac, execute your export with a fixed, static input size and leverage FP16 half-precision formatting: `[1][2][3][4][5][6]` python

``` from ultralytics import YOLO

# Load the desired model (YOLO11 or YOLO26 recommended for M3) model = YOLO("yolo11n.pt")

# Export explicitly targeting CoreML with static shapes for Apple Silicon optimization model.export(format="coreml", nms=False, half=True, int8=False)

```

Use code with caution.

*(Note: Keep `int8=False` unless deploying on low-power iOS hardware; M3 unified memory handles FP16 at full hardware speed without the accuracy drops or quantization artifacts associated with INT8 conversion).* 

If you would like to implement this pipeline, let me know: 

* Your preferred **deployment language** (Python or native Swift/C++)
* The average **density of people** expected in the video frames
* Whether your application prioritizes **identity permanence** or maximum possible **processing speed** 

I can provide the exact code wrapper needed to couple the CoreML model with a ByteTrack implementation. 

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

[1] YOLO26: Key Architectural Enhancements and Performance ... - arXiv. Opens in new tab.  
https://arxiv.org/html/2509.25164v5

[2] YOLO26 vs YOLO11: A Generational Leap in Vision AI | Ultralytics Docs. Opens in new tab.  
https://docs.ultralytics.com/compare/yolo26-vs-yolo11

[3] Ultralytics YOLO for iOS: App and Swift Package - GitHub. Opens in new tab.  
https://github.com/ultralytics/yolo-ios-app

[4] Is YOLOv26 Actually Better? - Medium. Opens in new tab.  
https://medium.com/@mhuzaifadev/is-yolov26-actually-better-40527d2b95d7

[5] How to Export Ultralytics YOLO11 to CoreML for 2x Fast .... Opens in new tab.  
https://www.youtube.com/watch?v=hfSK3Mk5P0I

[6] 70 FPS on Apple MacBook with Ultralytics YOLO11 + CoreML .... Opens in new tab.  
https://www.linkedin.com/posts/muhammadrizwanmunawar_70-fps-on-apple-macbook-with-ultralytics-activity-7350777617513410560-tYO7

[7] YOLO26: Key Architectural Enhancements and Performance ... - arXiv. Opens in new tab.  
https://arxiv.org/html/2509.25164v5

[8] YOLO26 vs YOLO11: A Generational Leap in Vision AI | Ultralytics Docs. Opens in new tab.  
https://docs.ultralytics.com/compare/yolo26-vs-yolo11

[9] Ultralytics YOLO for iOS: App and Swift Package - GitHub. Opens in new tab.  
https://github.com/ultralytics/yolo-ios-app

[10] Is YOLOv26 Actually Better? - Medium. Opens in new tab.  
https://medium.com/@mhuzaifadev/is-yolov26-actually-better-40527d2b95d7

[11] How to Export Ultralytics YOLO11 to CoreML for 2x Fast .... Opens in new tab.  
https://www.youtube.com/watch?v=hfSK3Mk5P0I

[12] 70 FPS on Apple MacBook with Ultralytics YOLO11 + CoreML .... Opens in new tab.  
https://www.linkedin.com/posts/muhammadrizwanmunawar_70-fps-on-apple-macbook-with-ultralytics-activity-7350777617513410560-tYO7

[13] YOLO26: Key Architectural Enhancements and Performance ... - arXiv. Opens in new tab.  
https://arxiv.org/html/2509.25164v5

[14] YOLO26 vs YOLO11: A Generational Leap in Vision AI | Ultralytics Docs. Opens in new tab.  
https://docs.ultralytics.com/compare/yolo26-vs-yolo11

[15] Ultralytics YOLO for iOS: App and Swift Package - GitHub. Opens in new tab.  
https://github.com/ultralytics/yolo-ios-app

[16] Is YOLOv26 Actually Better? - Medium. Opens in new tab.  
https://medium.com/@mhuzaifadev/is-yolov26-actually-better-40527d2b95d7

[17] How to Export Ultralytics YOLO11 to CoreML for 2x Fast .... Opens in new tab.  
https://www.youtube.com/watch?v=hfSK3Mk5P0I

[18] 70 FPS on Apple MacBook with Ultralytics YOLO11 + CoreML .... Opens in new tab.  
https://www.linkedin.com/posts/muhammadrizwanmunawar_70-fps-on-apple-macbook-with-ultralytics-activity-7350777617513410560-tYO7

[19] YOLO26: Key Architectural Enhancements and Performance ... - arXiv. Opens in new tab.  
https://arxiv.org/html/2509.25164v5

[20] YOLO26 vs YOLO11: A Generational Leap in Vision AI | Ultralytics Docs. Opens in new tab.  
https://docs.ultralytics.com/compare/yolo26-vs-yolo11

[21] Ultralytics YOLO for iOS: App and Swift Package - GitHub. Opens in new tab.  
https://github.com/ultralytics/yolo-ios-app

[22] Is YOLOv26 Actually Better? - Medium. Opens in new tab.  
https://medium.com/@mhuzaifadev/is-yolov26-actually-better-40527d2b95d7

[23] How to Export Ultralytics YOLO11 to CoreML for 2x Fast .... Opens in new tab.  
https://www.youtube.com/watch?v=hfSK3Mk5P0I

[24] 70 FPS on Apple MacBook with Ultralytics YOLO11 + CoreML .... Opens in new tab.  
https://www.linkedin.com/posts/muhammadrizwanmunawar_70-fps-on-apple-macbook-with-ultralytics-activity-7350777617513410560-tYO7

