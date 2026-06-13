To achieve **real-time monocular depth estimation** for drone-to-person distance measurement on an Apple Silicon **[M3 MacBook Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:16530990147939341246,headlineOfferDocid:3240566647647504081,productDocid:3240566647647504081,rds:PC_1448266432536557262%7CPROD_PC_1448266432536557262&q=product&sa=X&ved=2ahUKEwiY08XYt-KUAxU8lSsGHV7DCO4Qxa4PeggIAggACAcQAg)**, **Depth Anything V2 (Small)** is the optimal choice, delivering true real-time performance of **25–35 FPS** when utilizing the native Metal Performance Shaders (MPS) backend or Core ML. Intel’s **MiDaS** (DPT-Hybrid) is faster but lacks the geometric precision, edge sharpness, and structural reliability needed for safe drone distance tracking. 

---

Model Comparison & Benchmarks 

| Metric `[13][14][15][16][17][18]` | Depth Anything V2 (Small) | MiDaS (v3.1 DPT-Hybrid) |
| --- | --- | --- |
| **M3 MacBook FPS** | **~25 – 35 FPS** (At<br><br> via MPS) | **~45 – 60 FPS** (At<br><br>) |
| **Real-Time Viability** | **Yes** (Meets the standard<br><br><!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mo>≥</mo><mn>24</mn></mrow><annotation encoding="text/plain">is greater than or equal to 24</annotation></semantics></math> --> ≥24is greater than or equal to 24 FPS) | **Yes** (Highly lightweight) |
| **Drone Tracking Accuracy** | **High** (Fine person contours, stable boundaries) | **Low-Medium** (Suffers from edge-blur and flickering) |
| **Metric Depth Capability** | **Yes** (Available via fine-tuned metric checkpoints) | **No** (Strictly relative depth map; requires custom scaling) |
| **Handling Backgrounds** | Exceptional across complex outdoor/aerial scenes | Prone to severe blending in dense outdoor environments |

---

Core Hardware & Software Optimization for M3 MacBooks 

* **Native Backend Support**: Do not run the model via standard CPU execution, which tanks performance down to single-digit frames. Depth Anything V2 supports Apple's PyTorch `mps` device natively. 
* **Core ML Conversion**: For peak power savings and thermal efficiency on an M3 chip during a drone video stream, leverage the official Apple [Core ML model exports](https://github.com/DepthAnything/Depth-Anything-V2). This maximizes utilization of the Apple Neural Engine (ANE) and keeps the M3 GPU free for other drone tasks (like object tracking or localization). 
*

---

Implementing Drone-to-Person Metric Distance Measurement 

Monocular depth models initially output a **relative depth map** (gray values indicating closer vs. farther). To transform this relative structure into actual physical meters for drone navigation, you must implement one of two methodologies: 

1. Use the Pre-trained Metric Depth Checkpoint 

The creators of Depth Anything V2 fine-tuned a specific "Metric Depth" variant of their architecture using synthetic data combined with spatial priors. You can download the **Depth-Anything-V2-Metric-Small** model checkpoint. This natively predicts scale-aware metric depth instead of simple comparative depth. 

2. Cross-Reference with Reference Targets (Bounding Boxes) `[7][8][9][10][11][12]`

If you utilize the standard relative model, you can map relative depth values to physical distances by tracking the person’s bounding box via an object detection model (such as YOLOv8): `[1][2][3][4][5][6]` python

```
# Conceptual extraction workflow for your M3 pipeline import torch import cv2

# Initialize depth network on Apple Silicon GPU device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
# Load your small optimized model onto the device...

# 1. Get Depth Array
# depth_map = model(frame) # Matrix of relative depths

# 2. Extract bounding box from person detector (YOLO)
# x1, y1, x2, y2 = person_bounding_box

# 3. Calculate median depth of the person to eliminate boundary noise
# person_depth_crop = depth_map[y1:y2, x1:x2]
# relative_distance = torch.median(person_depth_crop)

```

Use code with caution.

*Note: Using a **median-based depth extraction** over the target's bounding box is highly proven to dramatically reduce noise caused by background edge bleed during drone motion.* 

3. Mathematical Camera Focal-Length Rescaling 

If tracking relative depth, you convert the calculated relative distance value (

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>D</mi><mtext>rel</mtext></msub><annotation encoding="text/plain">cap D sub rel end-sub</annotation></semantics></math> --> Drelcap D sub rel end-sub

) into a physical distance in meters (

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>Z</mi><annotation encoding="text/plain">cap Z</annotation></semantics></math> --> Zcap Z

) by incorporating the known physical height of an average human ( meters), the pixel height of the bounding box (

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>h</mi><annotation encoding="text/plain">h</annotation></semantics></math> --> hh

), and the drone camera's calibrated focal length (

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>f</mi><annotation encoding="text/plain">f</annotation></semantics></math> --> ff

): 

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mi>Z</mi><mo>=</mo><mfrac><mrow><mi>H</mi><mo>×</mo><mi>f</mi></mrow><mi>h</mi></mfrac></mrow><annotation encoding="text/plain">cap Z equals the fraction with numerator cap H cross f and denominator h end-fraction</annotation></semantics></math> --> Z=H×fhcap Z equals the fraction with numerator cap H cross f and denominator h end-fraction

You can then establish a linear transformation scale factor (

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>S</mi><annotation encoding="text/plain">cap S</annotation></semantics></math> --> Scap S

) by matching your computed

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>Z</mi><annotation encoding="text/plain">cap Z</annotation></semantics></math> --> Zcap Z with the model's relative output (

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><msub><mi>D</mi><mtext>rel</mtext></msub><annotation encoding="text/plain">cap D sub rel end-sub</annotation></semantics></math> --> Drelcap D sub rel end-sub

): 

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mi>S</mi><mo>=</mo><mfrac><mi>Z</mi><msub><mi>D</mi><mtext>rel</mtext></msub></mfrac></mrow><annotation encoding="text/plain">cap S equals the fraction with numerator cap Z and denominator cap D sub rel end-sub end-fraction</annotation></semantics></math> --> S=ZDrelcap S equals the fraction with numerator cap Z and denominator cap D sub rel end-sub end-fraction

Multiplying your depth map array by

<!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mi>S</mi><annotation encoding="text/plain">cap S</annotation></semantics></math> --> Scap S scales your frame's depth stream into true physical meters. 

---

If you want to move forward with the implementation, tell me: 

* Will you be running this code **directly on the MacBook** using a live RTSP drone stream feed, or will you be **deploying it to an onboard drone computer**?
* Are you planning to pair the depth map with a bounding box tracker like **YOLO**?
* Do you need assistance generating the **Core ML export script** for the M3 Neural Engine? 
*

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

[1] Depth Anything V2 Monocular Depth Estimation .... Opens in new tab.  
https://www.youtube.com/watch?v=fs0jZx9o9rc

[2] DepthAnything/Depth-Anything-V2: [NeurIPS 2024 ... - GitHub. Opens in new tab.  
https://github.com/DepthAnything/Depth-Anything-V2

[3] What is Depth Estimation & How to Implement It .... Opens in new tab.  
https://www.youtube.com/watch?v=WsCUPg_TxwI&vl=en&t=266

[4] Depth Anything V2 - arXiv. Opens in new tab.  
https://arxiv.org/html/2406.09414v1

[5] We Tested 5 Depth Estimation Models So You Don't Have To ..... Opens in new tab.  
https://www.youtube.com/watch?v=WQTadQi0MCg

[6] Getting Started with Depth Estimation using MiDaS and Python - Medium. Opens in new tab.  
https://medium.com/@nbeel.original/getting-started-with-depth-estimation-using-midas-and-python-d0119bfe1159

[7] Depth Anything V2 Monocular Depth Estimation .... Opens in new tab.  
https://www.youtube.com/watch?v=fs0jZx9o9rc

[8] DepthAnything/Depth-Anything-V2: [NeurIPS 2024 ... - GitHub. Opens in new tab.  
https://github.com/DepthAnything/Depth-Anything-V2

[9] What is Depth Estimation & How to Implement It .... Opens in new tab.  
https://www.youtube.com/watch?v=WsCUPg_TxwI&vl=en&t=266

[10] Depth Anything V2 - arXiv. Opens in new tab.  
https://arxiv.org/html/2406.09414v1

[11] We Tested 5 Depth Estimation Models So You Don't Have To ..... Opens in new tab.  
https://www.youtube.com/watch?v=WQTadQi0MCg

[12] Getting Started with Depth Estimation using MiDaS and Python - Medium. Opens in new tab.  
https://medium.com/@nbeel.original/getting-started-with-depth-estimation-using-midas-and-python-d0119bfe1159

[13] Depth Anything V2 Monocular Depth Estimation .... Opens in new tab.  
https://www.youtube.com/watch?v=fs0jZx9o9rc

[14] DepthAnything/Depth-Anything-V2: [NeurIPS 2024 ... - GitHub. Opens in new tab.  
https://github.com/DepthAnything/Depth-Anything-V2

[15] What is Depth Estimation & How to Implement It .... Opens in new tab.  
https://www.youtube.com/watch?v=WsCUPg_TxwI&vl=en&t=266

[16] Depth Anything V2 - arXiv. Opens in new tab.  
https://arxiv.org/html/2406.09414v1

[17] We Tested 5 Depth Estimation Models So You Don't Have To ..... Opens in new tab.  
https://www.youtube.com/watch?v=WQTadQi0MCg

[18] Getting Started with Depth Estimation using MiDaS and Python - Medium. Opens in new tab.  
https://medium.com/@nbeel.original/getting-started-with-depth-estimation-using-midas-and-python-d0119bfe1159

