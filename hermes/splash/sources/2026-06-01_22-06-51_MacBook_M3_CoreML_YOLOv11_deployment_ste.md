This step-by-step guide covers how to export an

Ultralytics YOLOv11 model to Apple CoreML and run hardware-accelerated inference natively on your **[MacBook M3 (M3 Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:2454872933540193881,headlineOfferDocid:12640058900463121258,productDocid:12640058900463121258,rds:PC_1448266432536557262%7CPROD_PC_1448266432536557262&q=product&sa=X&ved=2ahUKEwio-puavOeUAxWWNoYAHayBN_0Qxa4PeggIAggACAUQAw)

,

[M3 Pro Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,mid:576462881110899145,imageDocid:12653330392521673882,gpcid:12855319700136315231,headlineOfferDocid:9869116650649472956,catalogid:6764536191104852536,productDocid:3173599942599372331,rds:PC_10962406370348363048%7CPROD_PC_10962406370348363048&q=product&sa=X&ved=2ahUKEwio-puavOeUAxWWNoYAHayBN_0Qxa4PeggIAggACAUQBQ)

, or

[M3 Max) Go to product viewer dialog for this item.](/search?ibp=oshop&prds=pvt:hg,pvo:29,imageDocid:8498403889690231088,headlineOfferDocid:11723625597104317814,productDocid:11723625597104317814,rds:PC_1448266432536557262%7CPROD_PC_1448266432536557262&q=product&sa=X&ved=2ahUKEwio-puavOeUAxWWNoYAHayBN_0Qxa4PeggIAggACAUQBw)**. 

🛠️ Step 1: Prepare the Environment 

Ensure your Python environment is native to Apple Silicon (`arm64`) and fully updated to guarantee native Neural Engine optimization. 

Open your terminal and run:  bash

```
# Create and activate a clean virtual environment python3 -m venv yolo_env source yolo_env/bin/activate

# Install and upgrade the necessary libraries pip install --upgrade pip pip install ultralytics coremltools opencv-python

```

Use code with caution.

📦 Step 2: Export YOLOv11 to CoreML Format `[13][14][15][16][17][18]`

You can convert either a standard pre-trained model or your own custom-trained `.pt` file. Create a Python script named `export.py`:  python

``` from ultralytics import YOLO

# 1. Load your YOLOv11 PyTorch model (e.g., nano, small, medium) model = YOLO("yolo11n.pt")  

# 2. Export to CoreML format optimized for Apple Silicon
# 'nms=True' embeds Non-Maximum Suppression directly into the package model.export(format="coreml", nms=True, imgsz=640)

```

Use code with caution.

Run the export script:  bash

``` python export.py

```

Use code with caution.

* **Result**: This generates a directory named `yolo11n.mlpackage` inside your working folder. 

🚀 Step 3: Run Hardware-Accelerated Inference `[7][8][9][10][11][12]`

The [Ultralytics API](https://docs.ultralytics.com/integrations/coreml) automatically routes your workloads directly through macOS's native framework to target the M3 GPU and Neural Engine. 

Create a script named `inference.py`:  python

``` import cv2 from ultralytics import YOLO

# 1. Load the compiled Apple CoreML package model = YOLO("yolo11n.mlpackage")

# 2. Path to your target source image or video clip source_img = "path/to/your/image.jpg"

# 3. Run hardware-accelerated prediction results = model(source_img, device="mps")

# 4. Process and render results for result in results:
    # Display the visual bounding boxes on screen result.show()
  
    # Optional: Save the annotated image to disk result.save(filename="m3_output.jpg")

```

Use code with caution.

Run your inference engine:  bash

``` python inference.py

```

Use code with caution.

⚡ Optimization Matrix (M3 Best Practices) 

| Parameter Variant `[1][2][3][4][5][6]` | Best Use Case | Performance Trade-off |
| --- | --- | --- |
| **`nms=True`** | Python prototyping & Apple Xcode apps | Faster post-processing on M3. |
| **`half=True`** | Standard FP16 execution | Cuts model size in half; negligible accuracy loss. |
| **`int8=True`** | Ultra-low power / background loops | Maximizes Neural Engine use; requires evaluation validation. |

To include precision optimizations during your export phase, adapt your line to:  python

``` model.export(format="coreml", nms=True, half=True)

```

Use code with caution.

Would you like to explore **converting this into a live webcam inference loop**, or are you looking to integrate this `.mlpackage` **directly into an iOS/macOS Swift application** via Xcode? 

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

[1] CoreML Export for YOLO26 Models - Ultralytics Docs. Opens in new tab.  
https://docs.ultralytics.com/integrations/coreml

[2] Bringing Ultralytics YOLO11 to Apple devices via CoreML. Opens in new tab.  
https://www.ultralytics.com/blog/bringing-ultralytics-yolo11-to-apple-devices-via-coreml

[3] Core ML | Apple Developer Documentation. Opens in new tab.  
https://developer.apple.com/documentation/coreml

[4] How to Export Ultralytics YOLO11 to CoreML for 2x Fast .... Opens in new tab.  
https://www.youtube.com/watch?v=hfSK3Mk5P0I&t=458

[5] Model Export with Ultralytics YOLO. Opens in new tab.  
https://docs.ultralytics.com/modes/export

[6] Exporting YoloV11 Pytorch Model to CoreML #885 - GitHub. Opens in new tab.  
https://github.com/ultralytics/hub/issues/885

[7] CoreML Export for YOLO26 Models - Ultralytics Docs. Opens in new tab.  
https://docs.ultralytics.com/integrations/coreml

[8] Bringing Ultralytics YOLO11 to Apple devices via CoreML. Opens in new tab.  
https://www.ultralytics.com/blog/bringing-ultralytics-yolo11-to-apple-devices-via-coreml

[9] Core ML | Apple Developer Documentation. Opens in new tab.  
https://developer.apple.com/documentation/coreml

[10] How to Export Ultralytics YOLO11 to CoreML for 2x Fast .... Opens in new tab.  
https://www.youtube.com/watch?v=hfSK3Mk5P0I&t=458

[11] Model Export with Ultralytics YOLO. Opens in new tab.  
https://docs.ultralytics.com/modes/export

[12] Exporting YoloV11 Pytorch Model to CoreML #885 - GitHub. Opens in new tab.  
https://github.com/ultralytics/hub/issues/885

[13] CoreML Export for YOLO26 Models - Ultralytics Docs. Opens in new tab.  
https://docs.ultralytics.com/integrations/coreml

[14] Bringing Ultralytics YOLO11 to Apple devices via CoreML. Opens in new tab.  
https://www.ultralytics.com/blog/bringing-ultralytics-yolo11-to-apple-devices-via-coreml

[15] Core ML | Apple Developer Documentation. Opens in new tab.  
https://developer.apple.com/documentation/coreml

[16] How to Export Ultralytics YOLO11 to CoreML for 2x Fast .... Opens in new tab.  
https://www.youtube.com/watch?v=hfSK3Mk5P0I&t=458

[17] Model Export with Ultralytics YOLO. Opens in new tab.  
https://docs.ultralytics.com/modes/export

[18] Exporting YoloV11 Pytorch Model to CoreML #885 - GitHub. Opens in new tab.  
https://github.com/ultralytics/hub/issues/885

