Direct Benchmarks Summary 

When deployed on an Apple Silicon **[MacBook M3 Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:2454872933540193881,headlineOfferDocid:12640058900463121258,productDocid:12640058900463121258,rds:PC_1448266432536557262%7CPROD_PC_1448266432536557262&q=product&sa=X&ved=2ahUKEwiFqfPMhuWUAxVikokEHW-SPU0Qxa4PeggIAggACAkQAg)**, the **YOLOv11 Nano (yolo11n)** model outperforms **YOLOv8 Nano (yolov8n)** in person detection efficiency. Leveraging **CoreML** utilizes the Apple Neural Engine (ANE) and GPU, allowing

YOLOv11 Nano to achieve approximately **70 to 100+ Frames Per Second (FPS)**. This represents a significant processing speed upgrade over native PyTorch inference via **Metal Performance Shaders (MPS)**. 

---

YOLOv11 Nano vs. YOLOv8 Nano Benchmark Comparison 

The following data reflects normalized benchmarking results for **Person Detection (640px resolution)** on a standard baseline Apple M3 chip: 

| Metric / Environment `[1][2][3][4][5][6]` | YOLOv8 Nano (`yolov8n`) | YOLOv11 Nano (`yolo11n`) | Key Takeaway / Advantage |
| --- | --- | --- | --- |
| **Model Parameters** | ~3.2 Million | **~2.6 Million** | YOLOv11 is **18% lighter**. |
| **COCO mAP (Accuracy)** | 37.3% | **39.4%** | YOLOv11 delivers **+2.1% accuracy**. |
| **CoreML Inference Speed** | ~18–22 ms / frame | **~10–14 ms / frame** | YOLOv11 provides **~40% faster** CoreML. |
| **CoreML Throughput (FPS)** | ~45 – 55 FPS | **~70 – 100+ FPS** | Blazing fast real-time edge processing. |
| **MPS Inference Speed** | ~28–35 ms / frame | **~22–26 ms / frame** | YOLOv11 is more efficient via PyTorch MPS. |
| **MPS Throughput (FPS)** | ~30 – 35 FPS | **~38 – 45 FPS** | Improved attention mechanisms optimize GPU pipelines. |

---

Architectural Performance Breakdown 

Why CoreML Destroys MPS in Speed 

* **Apple Neural Engine (ANE) Target**: Exporting your `.pt` model to `.mlpackage` (CoreML) shifts the computational workload heavily to Apple’s dedicated Neural Engine. 
* **MPS Bottlenecks**: Running natively in PyTorch using `device='mps'` routes operations through the GPU. While functional, it introduces overhead during layer execution and suffers from unoptimized custom layers. 
*

YOLOv11 Nano Design Enhancements 

* **C3k2 Blocks Over C2f**: YOLOv11 swaps out the legacy C2f architecture found in YOLOv8 for C3k2 modules. This extracts features using dual smaller convolutions, heavily reducing overall mathematical operations (GFLOPs). 
* **C2PSA Spatial Attention**: YOLOv11 natively isolates regional features. For person detection tasks, this means the model quickly maps body shapes and bounds while skipping background noise. 
*

---

2025/2026 CoreML Export Workflow 

To maximize your M3 hardware capabilities, do not run standard `.pt` files. Export to CoreML directly using the Ultralytics Framework:  python

``` from ultralytics import YOLO

# Load the optimized YOLOv11 Nano model model = YOLO("yolo11n.pt")

# Export specifically to Apple CoreML format model.export(format="coreml", nms=True)

# Load and run the ultra-fast compiled CoreML package coreml_model = YOLO("yolo11n.mlpackage") results = coreml_model.predict(source="webcam", stream=True)

```

Use code with caution.

*(Note: Setting `nms=True` hardcodes the Non-Maximum Suppression step into the CoreML graph, bypassing Python post-processing bottlenecks for even higher real-time frame rates.)* 

---

Would you like help writing a custom **Python benchmarking script** to test these live on your device, or do you need assistance configuring the **multi-object tracking algorithms** (like BoT-SORT) for your person detection project? 

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

[1] YOLO11 vs YOLOv8, YOLOv9 & YOLOv10: Full Comparison. Opens in new tab.  
https://www.ultralytics.com/blog/comparing-ultralytics-yolo11-vs-previous-yolo-models

[2] Ultralytics YOLO11 | Ultralytics Docs. Opens in new tab.  
https://docs.ultralytics.com/models/yolo11

[3] An Overview of YOLO26, YOLO11, YOLOv8, and YOLOv5 Object .... Opens in new tab.  
https://arxiv.org/html/2510.09653v3

[4] Comparative performance of YOLOv8, YOLOv9, YOLOv10, .... Opens in new tab.  
https://www.sciencedirect.com/science/article/pii/S2772375524002533

[5] Comparing YOLOv11 and YOLOv8 for instance segmentation ... - arXiv. Opens in new tab.  
https://arxiv.org/html/2410.19869v3

[6] YOLOv8 vs YOLOv11: Model Comparison. Opens in new tab.  
https://www.youtube.com/watch?v=sitxMAaeHFE&t=354

